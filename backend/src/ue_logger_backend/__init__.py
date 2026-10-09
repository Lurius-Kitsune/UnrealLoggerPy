"""Reusable, Qt-free API for Unreal Engine logs."""

from .parser import LogEntry, VERBOSITIES, VERBOSITY_RANK, parse_line
from .socket_server import LogSocketServer
from .tailer import LogTailer

__all__ = [
    "LogEntry",
    "LogSocketServer",
    "LogTailer",
    "VERBOSITIES",
    "VERBOSITY_RANK",
    "parse_line",
]

__version__ = "1.0.0"
