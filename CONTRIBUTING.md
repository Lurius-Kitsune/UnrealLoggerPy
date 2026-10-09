# Contributing

Thank you for considering a contribution to UE Logger.

## Set up the development environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The backend is a separate package in `backend/` and does not depend on Qt. Unit tests use Python's built-in `unittest` framework.

## Checks before opening a pull request

```powershell
python -m unittest discover -s tests -v
```

Keep changes focused, document public functions, and add tests for new backend behavior. For UI changes, describe the interactions you checked and include a screenshot when it helps explain the change.

## Pull requests

- Describe the problem and the proposed solution.
- Report which checks you ran and their results.
- Call out configuration or protocol changes.
- Do not include Unreal logs, secrets, or private project files.
