"""Initialize Qt and start the application."""

import sys

from PySide6.QtWidgets import QApplication

from .theme import apply_dark_theme
from .window import MainWindow


def _acquire_windows_instance_guard():
    """Prevent multiple automatic launches from opening multiple windows on Windows."""
    if sys.platform != "win32":
        return None, False

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.CreateMutexW(None, 1, "Local\\UnrealLoggerPy.Singleton")
    if not handle:
        return None, False
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return None, True
    return (kernel32, handle), False


def main() -> None:
    """Start the user interface with an optional log path argument."""
    mutex, already_open = _acquire_windows_instance_guard()
    if already_open:
        return
    application = QApplication(sys.argv)
    try:
        apply_dark_theme(application)
        start_path = sys.argv[1] if len(sys.argv) > 1 else None
        window = MainWindow(start_path)
        window.show()
        sys.exit(application.exec())
    finally:
        if mutex is not None:
            kernel32, handle = mutex
            kernel32.CloseHandle(handle)
