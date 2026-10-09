"""Unit tests for parsing Unreal log lines."""

import unittest

from ue_logger_backend import parse_line


class ParseLineTests(unittest.TestCase):
    """Test the timestamped and short formats supported by the parser."""

    def test_parses_timestamped_line_and_project_metadata(self):
        """Keep the date, time, frame, category, and verbosity as separate fields."""
        entry = parse_line(
            "[2026.10.09-10.15.30:123][  5]LogTemp: Warning: Example",
            "project-1",
            "Demo",
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.date, "2026-10-09")
        self.assertEqual(entry.time, "10:15:30")
        self.assertEqual(entry.frame, "5")
        self.assertEqual(entry.category, "LogTemp")
        self.assertEqual(entry.verbosity, "Warning")
        self.assertEqual(entry.message, "Example")
        self.assertEqual(entry.project_id, "project-1")
        self.assertEqual(entry.project_name, "Demo")

    def test_defaults_missing_verbosity_to_log(self):
        """Treat entries without an explicit verbosity as standard logs."""
        entry = parse_line("[2026.10.09-10.15.30:123][5]LogTemp: Example")

        self.assertIsNotNone(entry)
        self.assertEqual(entry.verbosity, "Log")
        self.assertEqual(entry.message, "Example")

    def test_parses_short_startup_line(self):
        """Accept the short format used by some startup log lines."""
        entry = parse_line("LogInit: Display: Initialization")

        self.assertIsNotNone(entry)
        self.assertEqual(entry.date, "")
        self.assertEqual(entry.category, "LogInit")
        self.assertEqual(entry.verbosity, "Display")
        self.assertEqual(entry.message, "Initialization")

    def test_returns_none_for_unrecognized_line(self):
        """Ignore text that does not match a known Unreal log prefix."""
        self.assertIsNone(parse_line("arbitrary text without a category"))


if __name__ == "__main__":
    unittest.main()
