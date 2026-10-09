# UE Logger Backend

A standalone Python library for parsing Unreal Engine logs, following log files, and receiving streamed log records. It depends only on the Python standard library and can be embedded in other Python applications.

## Installation

From the repository root:

```powershell
python -m pip install .\backend
```

For development, install the package in editable mode:

```powershell
python -m pip install -e .\backend
```

## Example

```python
from ue_logger_backend import LogSocketServer, LogTailer, parse_line

entry = parse_line("[2026.10.09-10.15.30:123][  5]LogTemp: Warning: Example")
print(entry.verbosity, entry.category, entry.message)

tailer = LogTailer()
tailer.set_file("C:/Project/Saved/Logs/Project.log")
new_lines, changed_file = tailer.poll()

server = LogSocketServer(
    on_lines=lambda project_id, project_name, lines: print(project_name, lines),
    on_project_connected=lambda project_id, name: print("Connected:", name),
)
server.start()
```

The server accepts the Unreal bridge's NDJSON protocol on `127.0.0.1:8765`. Its callbacks run on network threads; GUI applications should forward callback results to their UI thread.
