"""Incrementally read log files without a user-interface dependency."""

from pathlib import Path


class LogTailer:
    """Read appended file bytes and retain incomplete lines."""

    def __init__(self) -> None:
        """Initialize the reader without a selected file or directory."""
        self.path: Path | None = None
        self.directory: Path | None = None
        self.position = 0
        self._buffer = b""

    def set_file(self, path: str | Path) -> None:
        """Follow a specific file and start reading from its beginning."""
        self.path = Path(path)
        self.directory = None
        self.position = 0
        self._buffer = b""

    def set_directory(self, directory: str | Path) -> None:
        """Follow the newest log file in the selected directory."""
        self.directory = Path(directory)
        self.path = None
        self.position = 0
        self._buffer = b""

    def _newest_log(self) -> Path | None:
        """Return the newest log file, ignoring backup files."""
        if self.directory is None or not self.directory.is_dir():
            return None
        candidates = [
            path for pattern in ("*.log", "*.txt")
            for path in self.directory.glob(pattern)
            if path.is_file() and "-backup-" not in path.name.lower()
        ]
        newest = None
        newest_time = -1.0
        for path in candidates:
            try:
                modified = path.stat().st_mtime
            except OSError:
                continue
            if modified > newest_time:
                newest, newest_time = path, modified
        return newest

    def poll(self) -> tuple[list[str], bool]:
        """Return complete new lines and indicate whether the file rotated."""
        switched = False
        newest = self._newest_log()
        if newest is not None and newest != self.path:
            self.set_file(newest)
            self.directory = newest.parent
            switched = True

        if self.path is None or not self.path.is_file():
            return [], switched
        size = self.path.stat().st_size
        if size < self.position:
            self.position = 0
            self._buffer = b""
            switched = True
        if size == self.position:
            return [], switched

        with self.path.open("rb") as log_file:
            log_file.seek(self.position)
            data = log_file.read()
            self.position = log_file.tell()
        parts = (self._buffer + data).split(b"\n")
        self._buffer = parts.pop()
        lines = [part.decode("utf-8", errors="replace").rstrip("\r") for part in parts]
        return [line for line in lines if line.strip()], switched
