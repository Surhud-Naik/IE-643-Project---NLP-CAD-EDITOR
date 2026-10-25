#!/usr/bin/env python3
"""
CLI entry point to fine-tune a model with LoRA on the CAD editing dataset.
Usage: python scripts/train.py --config configs/train_patch.yaml
"""

import argparse
import yaml
import sys
import os
from cadpatch.models import train_lora_model


def main():
    parser = argparse.ArgumentParser(description="LoRA Fine-Tuning for CAD Editing")
    parser.add_argument("--config", type=str, default="configs/train_patch.yaml")
    parser.add_argument("--task", type=str, default=None, choices=["patch", "full"])
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    task = args.task or cfg.get("task", "patch")
    if args.epochs is not None:
        cfg["epochs"] = args.epochs
    if args.samples is not None:
        cfg["max_samples"] = args.samples

    print(f"=== Fine-Tuning CAD Model: Task = {task.upper()} ===")
    history = train_lora_model(cfg, task=task)
    print("=== Training completed successfully! ===")


if __name__ == "__main__":
    main()
