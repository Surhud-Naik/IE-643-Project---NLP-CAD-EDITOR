#!/usr/bin/env python3
"""
CLI entry point to launch the interactive Gradio demo.
Usage: python scripts/run_demo.py --port 7860
"""

import argparse
from cadpatch.demo import build_demo_app


def main():
    parser = argparse.ArgumentParser(description="Launch Gradio CAD Patch Demo")
    parser.add_argument("--port", type=int, default=7860, help="Server port")
    parser.add_argument("--share", action="store_true", help="Create public share link")
    args = parser.parse_args()

    app = build_demo_app()
    print(f"Launching CAD-Patch-Editor Gradio App on port {args.port}...")
    app.launch(server_name="0.0.0.0", server_port=args.port, share=args.share)


if __name__ == "__main__":
    main()
