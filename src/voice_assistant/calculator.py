"""
Calculator module for Voice Assistant.

Safely evaluates basic math expressions from voice input.
No external API required — uses Python's ast module for safe parsing.
"""

import ast
import math
import operator
import re
from typing import Union

from voice_assistant.logging_config import get_logger

logger = get_logger("calculator")

# Supported binary operators
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

# Supported unary operators
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Word-to-symbol mappings for voice input
_WORD_MAP = {
    "plus": "+",
    "add": "+",
    "added to": "+",
    "minus": "-",
    "subtract": "-",
    "times": "*",
    "multiplied by": "*",
    "divided by": "/",
    "over": "/",
    "to the power of": "**",
    "power": "**",
    "mod": "%",
    "modulo": "%",
    "percent of": "* 0.01 *",
}


def _safe_eval(node: ast.AST) -> Union[int, float]:
    """Safely evaluate an AST math expression node."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type == ast.Div and right == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return _OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _UNARY_OPS[op_type](_safe_eval(node.operand))
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def _normalize_expression(text: str) -> str:
    """Convert voice-style math text to a computable expression."""
    expr = text.lower().strip()

    # Sort by length (longest first) to avoid partial replacements
    for word, symbol in sorted(_WORD_MAP.items(), key=lambda x: -len(x[0])):
        expr = expr.replace(word, f" {symbol} ")

    # Replace 'x' used as multiplication (but not in words)
    expr = re.sub(r"(\d)\s*x\s*(\d)", r"\1 * \2", expr)

    # Remove non-math characters
    expr = re.sub(r"[^0-9+\-*/().%\s]", "", expr)
    expr = re.sub(r"\s+", " ", expr).strip()

    return expr


def calculate(expression: str) -> str:
    """
    Safely evaluate a math expression from voice input.

    Supports: +, -, *, /, **, %, and natural language like
    "5 plus 3", "10 divided by 2", "what is 15 times 4".

    Args:
        expression: Math expression as text (natural language or symbolic).

    Returns:
        Result string, or error message if evaluation fails.
    """
    if not expression or not expression.strip():
        return "Please tell me a math problem to solve."

    normalized = _normalize_expression(expression)
    logger.debug("Normalized expression: '%s' -> '%s'", expression, normalized)

    if not normalized:
        return "I couldn't understand that math expression. Try something like '5 plus 3'."

    try:
        tree = ast.parse(normalized, mode="eval")
        result = _safe_eval(tree)

        # Format nicely
        if isinstance(result, float) and result == int(result):
            result = int(result)

        logger.info("Calculated: %s = %s", normalized, result)
        return f"The answer is {result}."

    except ZeroDivisionError:
        return "You can't divide by zero!"
    except (ValueError, SyntaxError) as e:
        logger.warning("Could not evaluate '%s': %s", expression, e)
        return "I couldn't calculate that. Try a simpler expression like '5 plus 3'."
    except Exception as e:
        logger.error("Calculator error for '%s': %s", expression, e)
        return "Something went wrong with that calculation. Please try again."

