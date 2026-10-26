"""
CAD Patch Editor - Localhost POC Launcher.
Runs the complete production website (FastAPI backend + React frontend) on http://localhost:8000.
"""

import os
import sys
import subprocess

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(root_dir, "src")

    # Ensure virtualenv python is used
    venv_python = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    env = os.environ.copy()
    env["PYTHONPATH"] = src_dir

    port = 8000
    host = "127.0.0.1"

    print("=" * 60)
    print("  CAD Patch Editor - Localhost POC")
    print(f"  Serving at: http://localhost:{port}")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        subprocess.run(
            [venv_python, "-m", "uvicorn", "cadpatch.web.app:app", "--host", host, "--port", str(port)],
            cwd=root_dir,
            env=env
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
