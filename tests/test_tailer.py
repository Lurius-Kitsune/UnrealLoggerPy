"""Unit tests for incremental log file reading."""

import os
from pathlib import Path
import tempfile
import time
import unittest

from ue_logger_backend import LogTailer


class LogTailerTests(unittest.TestCase):
    """Test partial and incremental reads as well as log rotation."""

    def test_keeps_partial_line_until_newline_arrives(self):
        """Do not return a line until its line terminator has been written."""
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory) / "Project.log"
            path.write_bytes(b"premiere\npartielle")
            tailer = LogTailer()
            tailer.set_file(path)

            self.assertEqual(tailer.poll(), (["premiere"], False))
            with path.open("ab") as log_file:
                log_file.write(b"-terminee\nseconde\n")

            self.assertEqual(tailer.poll(), (["partielle-terminee", "seconde"], False))

    def test_switches_to_newest_file_in_directory(self):
        """Report rotation and start reading the newly selected file."""
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            folder = Path(directory)
            first = folder / "Project.log"
            first.write_text("ancien\n", encoding="utf-8")
            tailer = LogTailer()
            tailer.set_directory(folder)

            lines, switched = tailer.poll()
            self.assertEqual(lines, ["ancien"])
            self.assertTrue(switched)

            second = folder / "Project-2.log"
            second.write_text("nouveau\n", encoding="utf-8")
            future = time.time() + 2
            os.utime(second, (future, future))

            lines, switched = tailer.poll()
            self.assertEqual(lines, ["nouveau"])
            self.assertTrue(switched)
            self.assertEqual(tailer.path, second)


if __name__ == "__main__":
    unittest.main()
