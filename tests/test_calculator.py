"""Tests for calculator module."""

from voice_assistant.calculator import calculate, _normalize_expression


class TestNormalizeExpression:
    """Test normalization of voice input to math expressions."""

    def test_simple_plus(self):
        assert "+" in _normalize_expression("5 plus 3")

    def test_times_word(self):
        assert "*" in _normalize_expression("4 times 6")

    def test_divided_by(self):
        assert "/" in _normalize_expression("10 divided by 2")

    def test_minus_word(self):
        assert "-" in _normalize_expression("10 minus 3")

    def test_x_as_multiply(self):
        result = _normalize_expression("3 x 4")
        assert "*" in result


class TestCalculate:
    """Test suite for calculate function."""

    def test_simple_addition(self):
        result = calculate("5 plus 3")
        assert "8" in result

    def test_simple_subtraction(self):
        result = calculate("10 minus 3")
        assert "7" in result

    def test_multiplication(self):
        result = calculate("4 times 6")
        assert "24" in result

    def test_division(self):
        result = calculate("10 divided by 2")
        assert "5" in result

    def test_numeric_expression(self):
        result = calculate("3 + 7")
        assert "10" in result

    def test_division_by_zero(self):
        result = calculate("5 / 0")
        assert "zero" in result.lower() or "can't" in result.lower()

    def test_empty_expression(self):
        result = calculate("")
        assert "please" in result.lower() or "tell" in result.lower()

    def test_invalid_expression(self):
        result = calculate("hello world")
        assert "couldn't" in result.lower() or "try" in result.lower()

    def test_power(self):
        result = calculate("2 to the power of 3")
        assert "8" in result

    def test_complex_expression(self):
        result = calculate("(2 + 3) * 4")
        assert "20" in result

