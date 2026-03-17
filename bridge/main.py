"""
Entry point for the packaged desktop app.
PyInstaller calls this directly — no CLI involved.
"""

import multiprocessing

if __name__ == "__main__":
    # Required on Windows for PyInstaller + multiprocessing
    multiprocessing.freeze_support()

    from bridge.tray import run
    run()
