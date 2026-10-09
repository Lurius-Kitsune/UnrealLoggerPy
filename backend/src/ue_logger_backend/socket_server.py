"""Reusable local TCP server for receiving Unreal Engine logs."""

import json
import logging
import socket
import threading
from collections.abc import Callable


Callback = Callable[..., None]
_LOGGER = logging.getLogger(__name__)


def _notify(callback: Callback | None, *args) -> None:
    """Call a user callback without interrupting the network thread."""
    if callback is None:
        return
    try:
        callback(*args)
    except Exception:
        _LOGGER.exception("UE Logger callback failed.")


class _ServerWorker(threading.Thread):
    """Accept Unreal Editors and handle each connection in its own thread."""

    def __init__(self, server: "LogSocketServer") -> None:
        """Prepare the listener thread and client registry."""
        super().__init__(name="ue-logger-socket", daemon=True)
        self.server = server
        self.stop_event = threading.Event()
        self.listener: socket.socket | None = None
        self.clients: set[socket.socket] = set()
        self.clients_lock = threading.Lock()
        self.client_threads: list[threading.Thread] = []

    def run(self) -> None:
        """Listen for incoming connections and invoke status callbacks."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                self.listener = listener
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind((self.server.host, self.server.port))
                listener.listen(8)
                listener.settimeout(0.4)
                _notify(
                    self.server.on_server_status,
                    f"Unreal listener active on {self.server.host}:{self.server.port}.",
                )
                while not self.stop_event.is_set():
                    try:
                        client, _address = listener.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    self.client_threads = [thread for thread in self.client_threads if thread.is_alive()]
                    with self.clients_lock:
                        self.clients.add(client)
                    client_thread = threading.Thread(
                        target=self._read_client,
                        args=(client,),
                        name="ue-logger-client",
                        daemon=True,
                    )
                    self.client_threads.append(client_thread)
                    client_thread.start()
        except OSError as error:
            if not self.stop_event.is_set():
                _notify(self.server.on_server_status, f"Unable to open socket: {error}")
        finally:
            self.listener = None
            self._close_clients()
            _notify(self.server.on_server_stopped)

    def _read_client(self, client: socket.socket) -> None:
        """Read NDJSON frames and notify the application about received events."""
        buffer = bytearray()
        project_id = ""
        project_name = "Connexion Unreal"
        client.settimeout(0.4)
        try:
            while not self.stop_event.is_set():
                try:
                    chunk = client.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    newline = buffer.find(b"\n")
                    if newline < 0:
                        break
                    raw_record = bytes(buffer[:newline]).rstrip(b"\r")
                    del buffer[:newline + 1]
                    if not raw_record:
                        continue
                    try:
                        record = json.loads(raw_record.decode("utf-8", errors="replace"))
                    except (ValueError, UnicodeDecodeError):
                        _notify(
                            self.server.on_lines,
                            project_id,
                            project_name,
                            [raw_record.decode("utf-8", errors="replace")],
                        )
                        continue
                    if not isinstance(record, dict):
                        continue
                    record_type = record.get("type")
                    if record_type == "health_check":
                        response = json.dumps({"status": "ok"}, separators=(",", ":"))
                        client.sendall(response.encode("utf-8") + b"\n")
                    elif record_type == "hello":
                        project_id = str(record.get("project_id") or "unknown")
                        project_name = str(record.get("project_name") or "Unreal Project")
                        _notify(self.server.on_project_connected, project_id, project_name)
                    elif record_type == "log":
                        line = record.get("line")
                        if isinstance(line, str) and line.strip():
                            _notify(self.server.on_lines, project_id, project_name, [line])
        except OSError:
            pass
        finally:
            with self.clients_lock:
                self.clients.discard(client)
            try:
                client.close()
            except OSError:
                pass
            if project_id:
                _notify(self.server.on_project_disconnected, project_id)

    def _close_clients(self) -> None:
        """Close client sockets to unblock their reader threads."""
        with self.clients_lock:
            clients = list(self.clients)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass

    def stop(self) -> None:
        """Signal shutdown and close all currently open sockets."""
        self.stop_event.set()
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
        self._close_clients()
        for thread in self.client_threads:
            if thread is not threading.current_thread():
                thread.join(timeout=0.5)


class LogSocketServer:
    """Receive logs from multiple Unreal projects using standard Python callbacks."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        on_lines: Callback | None = None,
        on_project_connected: Callback | None = None,
        on_project_disconnected: Callback | None = None,
        on_server_status: Callback | None = None,
        on_server_stopped: Callback | None = None,
    ) -> None:
        """Configure the server and its callbacks without a user-interface framework."""
        self.host = host
        self.port = port
        self.on_lines = on_lines
        self.on_project_connected = on_project_connected
        self.on_project_disconnected = on_project_disconnected
        self.on_server_status = on_server_status
        self.on_server_stopped = on_server_stopped
        self._worker: _ServerWorker | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """Return whether the server thread is currently running."""
        return self._worker is not None and self._worker.is_alive()

    def start(self) -> None:
        """Start the TCP listener in the background if it is not already active."""
        with self._lock:
            if self.is_running:
                return
            self._worker = _ServerWorker(self)
            self._worker.start()

    def stop(self) -> None:
        """Stop the server and briefly wait for its threads to close."""
        with self._lock:
            worker = self._worker
        if worker is None:
            return
        worker.stop()
        if worker is not threading.current_thread():
            worker.join(timeout=1.0)
        with self._lock:
            if self._worker is worker:
                self._worker = None
