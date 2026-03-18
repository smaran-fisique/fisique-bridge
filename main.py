"""
Entry point for the packaged desktop application.
PyInstaller targets this file.
"""
from bridge.tray import run

if __name__ == "__main__":
    run()
