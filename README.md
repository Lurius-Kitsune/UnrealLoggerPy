# UE Logger

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-2ea44f.svg)](LICENSE)
[![Tests](https://github.com/Lurius-Kitsune/UnrealLoggerPy/actions/workflows/tests.yml/badge.svg)](https://github.com/Lurius-Kitsune/UnrealLoggerPy/actions/workflows/tests.yml)

**UE Logger** is a desktop application for monitoring Unreal Engine logs in real time. It combines a Qt interface for filtering and analysis with a standalone, reusable Python backend.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation and launch](#installation-and-launch)
- [Automatic Unreal connection](#automatic-unreal-connection)
- [Architecture](#architecture)
- [Use the backend as a library](#use-the-backend-as-a-library)
- [Tests](#tests)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)

## Features

- Incrementally follows a `.log` or `.txt` file, or a `Saved/Logs` directory.
- Receives logs in real time from multiple Unreal Editor instances over local TCP.
- Automatically starts the application and reconnects the Unreal bridge.
- Combines filters by project, verbosity, category, time range, and search text.
- Sortable table, full message details, pause, copy, and automatic scrolling.
- Interactive vertical time histogram with verbosity colors, hover details, and range selection.
- Separate backend with no Qt dependency, installable as a Python package.

## Requirements

- Python 3.10 or newer.
- Windows for the desktop application and automatic Unreal startup.
- Unreal Engine with the **Python Editor Script Plugin** for automatic connection.

The backend only uses the Python standard library and can run on other platforms.

## Installation and launch

From the repository root, create a virtual environment and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Launch the application:

```powershell
python main.py
```

You can also open a log file or directory directly:

```powershell
python main.py "C:\Project\Saved\Logs\Project.log"
python main.py "C:\Project\Saved\Logs"
```

## Automatic Unreal connection

UE Logger starts its local TCP server on `127.0.0.1:8765`. The Unreal script starts the application if it is not already running, then forwards new log lines. The server and bridge support multiple projects at the same time.

1. Enable the **Python Editor Script Plugin** in Unreal and restart the editor.
2. Under **Edit → Project Settings → Plugins → Python → Startup Scripts**, add the path to `unreal_bridge/ue_logger_bridge.py`.
3. Start the Unreal project. The bridge starts UE Logger if needed and reconnects until the server is available.

For a local setup, the launcher prefers `.venv/Scripts/pythonw.exe` at the repository root. If Python is installed elsewhere, set the `UE_LOGGER_PYTHON` environment variable to its executable path, then restart Unreal.

The bridge follows the active log file in `Saved/Logs`. To start it manually, use **Copy UE Command** in the toolbar, then run the command in **Window → Output Log** with **Cmd** mode selected.

## Architecture

```text
UnrealLoggerPy/
├── backend/                         # Standalone Python library
│   ├── pyproject.toml               # Installable ue-logger-backend package
│   └── src/ue_logger_backend/
│       ├── parser.py                # Log parsing and LogEntry model
│       ├── tailer.py                # Incremental file reader
│       └── socket_server.py         # TCP server with Python callbacks
├── ue_logger/                       # Qt desktop application
│   ├── app.py                       # Startup and Windows single-instance guard
│   ├── window.py                    # Main window and user interactions
│   ├── models.py                    # Table, filters, and sorting
│   ├── charts.py                    # Time histogram
│   ├── delegates.py                 # Display badges
│   ├── socket_server.py             # Backend adapter for Qt signals
│   ├── theme.py                     # Application theme
│   ├── parser.py                    # Compatibility re-export
│   └── tailer.py                    # Compatibility re-export
├── unreal_bridge/
│   └── ue_logger_bridge.py          # Bridge launched by Unreal Editor
├── tests/                            # Backend unit tests
├── .github/workflows/tests.yml       # GitHub Actions test workflow
├── main.py                           # Application entry point
└── requirements.txt                  # Application dependencies
```

## Use the backend as a library

Install only the backend in another Python project:

```powershell
python -m pip install .\backend
```

Example:

```python
from ue_logger_backend import LogSocketServer, LogTailer, parse_line

entry = parse_line(
    "[2026.10.09-10.15.30:123][  5]LogTemp: Warning: Example",
    project_id="my-project",
    project_name="My Project",
)
print(entry.verbosity, entry.category, entry.message)

tailer = LogTailer()
tailer.set_file("C:/Project/Saved/Logs/Project.log")
new_lines, file_changed = tailer.poll()

server = LogSocketServer(
    on_lines=lambda project_id, name, lines: print(name, lines),
    on_project_connected=lambda project_id, name: print("Connected:", name),
)
server.start()
# Call server.stop() when your application shuts down.
```

TCP server callbacks run on network threads. A graphical application should forward callback results to its UI thread. The Qt adapter in this application demonstrates how to connect callbacks to signals.

## Tests

Tests use `unittest` and cover the parser, incremental file reader, and TCP protocol:

```powershell
python -m unittest discover -s tests -v
```

The same suite runs automatically on Python 3.10 through 3.13 for pushes and pull requests.

## Limitations

The Python bridge requires Unreal Editor and the **Python Editor Script Plugin**. It does not run in a standalone or packaged game. Capturing `UE_LOG` calls directly from a packaged executable requires an Unreal C++ plugin.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup and pull request guidelines. For vulnerabilities, follow the [security policy](SECURITY.md). Do not submit Unreal logs containing sensitive data.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).
