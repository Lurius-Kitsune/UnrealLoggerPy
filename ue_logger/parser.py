"""Backward-compatible re-export of the backend library parser."""

from ue_logger_backend.parser import LogEntry, VERBOSITIES, VERBOSITY_RANK, parse_line

__all__ = ["LogEntry", "VERBOSITIES", "VERBOSITY_RANK", "parse_line"]
