"""Qt adapter for the user-interface-independent network server."""

from PySide6.QtCore import QObject, Signal

from ue_logger_backend import LogSocketServer as BackendLogSocketServer


class LogSocketServer(QObject):
    """Expose backend library callbacks as Qt signals."""

    lines_received = Signal(str, str, list)
    project_connected = Signal(str, str)
    project_disconnected = Signal(str)
    server_status = Signal(str)
    server_stopped = Signal()

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Create the standard backend and connect its callbacks to UI signals."""
        super().__init__()
        self._backend = BackendLogSocketServer(
            host,
            port,
            on_lines=self.lines_received.emit,
            on_project_connected=self.project_connected.emit,
            on_project_disconnected=self.project_disconnected.emit,
            on_server_status=self.server_status.emit,
            on_server_stopped=self.server_stopped.emit,
        )

    @property
    def is_running(self) -> bool:
        """Return whether the library's network thread is active."""
        return self._backend.is_running

    def start(self) -> None:
        """Start listening without blocking the Qt event loop."""
        self._backend.start()

    def stop(self) -> None:
        """Stop the backend and close all accepted connections."""
        self._backend.stop()
