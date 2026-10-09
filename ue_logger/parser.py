"""Compatibilité historique vers le parseur de la bibliothèque backend."""

from ue_logger_backend.parser import LogEntry, VERBOSITIES, VERBOSITY_RANK, parse_line

__all__ = ["LogEntry", "VERBOSITIES", "VERBOSITY_RANK", "parse_line"]
