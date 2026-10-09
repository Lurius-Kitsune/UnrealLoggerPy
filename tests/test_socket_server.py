"""Tests for the backend library's public TCP protocol."""

import json
import queue
import socket
import threading
import unittest

from ue_logger_backend import LogSocketServer


class LogSocketServerTests(unittest.TestCase):
    """Test the health check and receipt of an Unreal project stream."""

    def test_health_check_and_project_log_callbacks(self):
        """Reply to a ping, then relay the hello, log line, and disconnect events."""
        events = queue.Queue()
        listening = threading.Event()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]

        server = LogSocketServer(
            port=port,
            on_server_status=lambda message: listening.set(),
            on_lines=lambda project_id, name, lines: events.put(
                ("lines", project_id, name, lines)
            ),
            on_project_connected=lambda project_id, name: events.put(
                ("connected", project_id, name)
            ),
            on_project_disconnected=lambda project_id: events.put(
                ("disconnected", project_id)
            ),
        )
        server.start()
        self.assertTrue(listening.wait(2), "The server did not start listening.")

        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                client.settimeout(2)
                client.sendall(b'{"type":"health_check"}\n')
                response = client.recv(1024).split(b"\n", 1)[0]
                self.assertEqual(json.loads(response), {"status": "ok"})

                client.sendall(
                    b'{"type":"hello","project_id":"sample","project_name":"Sample"}\n'
                    b'{"type":"log","line":"LogTemp: Warning: Test"}\n'
                )
                received = [events.get(timeout=2), events.get(timeout=2)]
                self.assertIn(("connected", "sample", "Sample"), received)
                self.assertIn(("lines", "sample", "Sample", ["LogTemp: Warning: Test"]), received)

            disconnected = events.get(timeout=2)
            self.assertEqual(disconnected, ("disconnected", "sample"))
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
