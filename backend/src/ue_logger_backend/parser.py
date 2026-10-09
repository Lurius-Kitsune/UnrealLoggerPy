"""Parse Unreal log lines into events independent of the user interface."""

from dataclasses import dataclass
import re


# Verbosity levels are ordered from most severe to most detailed.
VERBOSITIES = ("Fatal", "Error", "Warning", "Display", "Log", "Verbose", "VeryVerbose")
VERBOSITY_RANK = {level: rank for rank, level in enumerate(VERBOSITIES)}
_LEVEL_PATTERN = "|".join(VERBOSITIES)
_FULL_LINE = re.compile(
    r"^\[(\d{4}\.\d{2}\.\d{2})-(\d{2})\.(\d{2})\.(\d{2}):\d{3}\]"
    r"\[\s*(\d+)\](\w+): (?:((?:" + _LEVEL_PATTERN + r")): )?(.*)$"
)
_SHORT_LINE = re.compile(r"^(\w+): (?:((?:" + _LEVEL_PATTERN + r")): )?(.*)$")


@dataclass(slots=True)
class LogEntry:
    """Represent a parsed log entry without a Qt dependency."""

    date: str
    time: str
    frame: str
    category: str
    verbosity: str
    message: str
    project_id: str = ""
    project_name: str = ""


def parse_line(line: str, project_id: str = "", project_name: str = "") -> LogEntry | None:
    """Convert a recognized Unreal log line into an event, or return ``None``."""
    match = _FULL_LINE.match(line)
    if match:
        date, hour, minute, second, frame, category, level, message = match.groups()
        return LogEntry(
            date.replace(".", "-"), f"{hour}:{minute}:{second}", frame,
            category, level or "Log", message, project_id, project_name,
        )

    match = _SHORT_LINE.match(line)
    if match:
        category, level, message = match.groups()
        return LogEntry("", "", "", category, level or "Log", message, project_id, project_name)
    return None
