"""
Development entry point for the Fisique Bridge GUI.
Usage: python -m bridge.app

In production the packaged .exe calls bridge/main.py directly.
"""

import multiprocessing

if __name__ == "__main__":
    # Required on Windows for PyInstaller + multiprocessing
    multiprocessing.freeze_support()

    from bridge.tray import run
    run()
