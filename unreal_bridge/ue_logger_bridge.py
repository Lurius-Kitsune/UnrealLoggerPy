"""Send new lines from Unreal Editor's active log over a socket.

Run this script in Unreal from the Output Log in Cmd mode:
    py "C:/chemin/vers/UnrealLoggerPy/unreal_bridge/ue_logger_bridge.py"
"""

import builtins
import glob
import json
import os
import shutil
import socket
import subprocess
import threading
import time

from pathlib import Path

import unreal


# The UE Logger server only listens on this machine's loopback interface.
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765
RECONNECT_SECONDS = 1.0
POLL_SECONDS = 0.05
MAX_PENDING_LINES = 5000
HEALTH_TIMEOUT_SECONDS = 0.6


class UnrealLogBridge:
    """Follow the project log and forward new lines to the TCP server."""

    def __init__(self, log_directory, project_id, project_name):
        """Initialize paths and relay shutdown controls."""
        self.log_directory = log_directory
        self.project_id = project_id
        self.project_name = project_name
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="UELoggerBridge", daemon=True)
        self.current_path = None
        self.position = 0
        self.partial_line = b""
        self.pending_lines = []

    def start(self):
        """Start the relay in a thread so the editor remains responsive."""
        self.thread.start()

    def stop(self):
        """Ask the thread to exit and close any pending wait operations."""
        self.stop_event.set()

    def _find_latest_log(self):
        """Return the newest active Unreal log file, excluding backups."""
        matches = glob.glob(os.path.join(self.log_directory, "*.log"))
        matches += glob.glob(os.path.join(self.log_directory, "*.txt"))
        candidates = [path for path in matches
                      if os.path.isfile(path) and "-backup-" not in os.path.basename(path).lower()]
        if not candidates:
            return None
        newest = None
        newest_time = -1.0
        for path in candidates:
            try:
                modified = os.path.getmtime(path)
            except OSError:
                continue
            if modified > newest_time:
                newest, newest_time = path, modified
        return newest

    def _read_new_lines(self):
        """Read appended bytes and retain any incomplete line."""
        latest = self._find_latest_log()
        if latest is None:
            return
        if latest != self.current_path:
            try:
                self.position = os.path.getsize(latest)
            except OSError:
                return
            self.current_path = latest
            self.partial_line = b""
            return

        try:
            size = os.path.getsize(self.current_path)
            if size < self.position:
                self.position = 0
                self.partial_line = b""
            if size == self.position:
                return
            with open(self.current_path, "rb") as log_file:
                log_file.seek(self.position)
                data = log_file.read()
                self.position = log_file.tell()
        except OSError:
            return

        parts = (self.partial_line + data).split(b"\n")
        self.partial_line = parts.pop()
        for line in parts:
            cleaned = line.rstrip(b"\r")
            if cleaned.strip():
                self.pending_lines.append(cleaned)
        if len(self.pending_lines) > MAX_PENDING_LINES:
            del self.pending_lines[:-MAX_PENDING_LINES]

    def _send_pending(self, connection):
        """Send queued lines as UTF-8, one line per frame."""
        while self.pending_lines and not self.stop_event.is_set():
            record = {
                "type": "log",
                "line": self.pending_lines[0].decode("utf-8", errors="replace"),
            }
            payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            connection.sendall(payload.encode("utf-8") + b"\n")
            del self.pending_lines[0]

    def _run(self):
        """Maintain the connection and collect new log lines."""
        connection = None
        next_connection_attempt = 0.0
        while not self.stop_event.is_set():
            now = time.monotonic()
            if connection is None and now >= next_connection_attempt:
                candidate = None
                try:
                    candidate = socket.create_connection(
                        (SERVER_HOST, SERVER_PORT), timeout=0.5
                    )
                    candidate.settimeout(0.5)
                    hello = {
                        "type": "hello",
                        "project_id": self.project_id,
                        "project_name": self.project_name,
                    }
                    candidate.sendall(
                        json.dumps(hello, ensure_ascii=False).encode("utf-8") + b"\n"
                    )
                    connection = candidate
                except OSError:
                    if candidate is not None:
                        try:
                            candidate.close()
                        except OSError:
                            pass
                    connection = None
                    next_connection_attempt = now + RECONNECT_SECONDS

            self._read_new_lines()
            if connection is not None:
                try:
                    self._send_pending(connection)
                except OSError:
                    try:
                        connection.close()
                    except OSError:
                        pass
                    connection = None
                    next_connection_attempt = time.monotonic() + RECONNECT_SECONDS
            self.stop_event.wait(POLL_SECONDS)

        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def start_bridge():
    """Start UE Logger if needed, then launch the current project's bridge."""
    _ensure_logger_running()
    previous = getattr(builtins, "_ue_logger_bridge", None)
    if previous is not None:
        previous.stop()

    log_directory = unreal.Paths.project_log_dir()
    project_directory = os.path.normcase(os.path.abspath(unreal.Paths.project_dir()))
    project_name = os.path.basename(os.path.normpath(project_directory))
    bridge = UnrealLogBridge(log_directory, project_directory, project_name)
    builtins._ue_logger_bridge = bridge
    bridge.start()
    unreal.log("UE Logger: bridge started for %s" % log_directory)
    return bridge


def _server_is_healthy():
    """Check server availability without creating a false connected project."""
    try:
        with socket.create_connection(
            (SERVER_HOST, SERVER_PORT), timeout=HEALTH_TIMEOUT_SECONDS
        ) as connection:
            connection.settimeout(HEALTH_TIMEOUT_SECONDS)
            request = {"type": "health_check"}
            connection.sendall(json.dumps(request).encode("utf-8") + b"\n")
            response = connection.recv(1024).split(b"\n", 1)[0]
            return json.loads(response.decode("utf-8")).get("status") == "ok"
    except (OSError, ValueError, UnicodeDecodeError):
        return False


def _logger_python_command(logger_root):
    """Find the Python executable used by UE Logger, with an environment override."""
    configured = os.environ.get("UE_LOGGER_PYTHON")
    if configured:
        executable = shutil.which(configured) or configured
        if os.path.isfile(executable):
            return [executable]
        unreal.log_warning("UE Logger: UE_LOGGER_PYTHON interpreter not found: %s" % configured)

    virtual_environment = logger_root / ".venv" / "Scripts"
    for name in ("pythonw.exe", "python.exe"):
        candidate = virtual_environment / name
        if candidate.is_file():
            return [str(candidate)]

    for name in ("pythonw", "python"):
        executable = shutil.which(name)
        if executable:
            return [executable]
    for name in ("pyw", "py"):
        executable = shutil.which(name)
        if executable:
            return [executable] + (["-3"] if name == "py" else [])
    return []


def _ensure_logger_running():
    """Start the UE Logger interface if its TCP server is not already active."""
    if _server_is_healthy():
        unreal.log("UE Logger: TCP server is already active.")
        return True

    logger_root = Path(__file__).resolve().parent.parent
    entry_point = logger_root / "main.py"
    if not entry_point.is_file():
        unreal.log_error("UE Logger: main.py was not found at %s" % logger_root)
        return False

    command = _logger_python_command(logger_root)
    if not command:
        unreal.log_error(
            "UE Logger: Python was not found. Install Python and the required dependencies, "
            "or set the UE_LOGGER_PYTHON environment variable."
        )
        return False

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            command + [str(entry_point)],
            cwd=str(logger_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creation_flags,
        )
    except OSError as error:
        unreal.log_error("UE Logger: unable to launch the interface: %s" % error)
        return False

    unreal.log("UE Logger: interface started; waiting for the TCP connection.")
    return True


start_bridge()
