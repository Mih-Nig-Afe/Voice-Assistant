"""
System Information module for Voice Assistant.

Reports system details like platform, uptime, CPU, memory.
No external API required — uses Python's built-in modules.
"""

import os
import platform
import sys
from datetime import datetime

from voice_assistant.logging_config import get_logger

logger = get_logger("system_info")


def get_system_info() -> str:
    """
    Get a summary of system information.

    Returns:
        Formatted string with OS, Python version, processor, and hostname.
    """
    info_parts = [
        f"Operating System: {platform.system()} {platform.release()}",
        f"Machine: {platform.machine()}",
        f"Python Version: {sys.version.split()[0]}",
        f"Hostname: {platform.node()}",
    ]

    # Try to get processor info
    proc = platform.processor()
    if proc:
        info_parts.append(f"Processor: {proc}")

    logger.debug("System info requested")
    return "System Information:\n" + "\n".join(info_parts)


def get_battery_status() -> str:
    """
    Get battery status if available.

    Returns:
        Battery status string or a message if unavailable.
    """
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected. This appears to be a desktop system."

        percent = battery.percent
        plugged = "plugged in" if battery.power_plugged else "on battery"
        time_left = ""
        if battery.secsleft > 0 and not battery.power_plugged:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            time_left = f" with about {hours} hours and {minutes} minutes remaining"

        return f"Battery is at {percent}%, currently {plugged}{time_left}."

    except ImportError:
        return "Battery monitoring is not available. Install psutil for this feature."
    except Exception as e:
        logger.error("Error getting battery status: %s", e)
        return "I couldn't check the battery status right now."


def get_platform_summary() -> str:
    """
    Get a brief one-line platform summary for voice output.

    Returns:
        Short platform description.
    """
    os_name = platform.system()
    os_version = platform.release()
    machine = platform.machine()
    return f"You're running {os_name} {os_version} on a {machine} machine."

