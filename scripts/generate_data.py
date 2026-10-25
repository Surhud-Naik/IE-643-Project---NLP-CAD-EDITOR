#!/usr/bin/env python3
"""
CLI entry point to generate the synthetic CAD editing dataset.
Usage: python scripts/generate_data.py --config configs/data.yaml
"""

import argparse
import yaml
import sys
import os
from cadpatch.data import generate_dataset


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic CAD edit dataset")
    parser.add_argument("--config", type=str, default="configs/data.yaml", help="Path to config YAML")
    parser.add_argument("--count", type=int, default=None, help="Override target count")
    args = parser.parse_args()

    if os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    else:
        cfg = {}

    target_count = args.count or cfg.get("target_count", 1000)
    seed = cfg.get("seed", 42)
    held_out = cfg.get("held_out_templates", ["shelled_box", "revolve_pulley"])
    output_dir = cfg.get("output_dir", "data")

    print(f"=== Starting CAD Edit Dataset Generation ===")
    print(f"Target Count: {target_count}")
    print(f"Seed: {seed}")
    print(f"Held-Out Templates: {held_out}")
    print(f"Output Directory: {output_dir}")

    stats = generate_dataset(
        target_count=target_count,
        held_out_templates=held_out,
        seed=seed,
        output_dir=output_dir
    )

    print("\n=== Dataset Generation Completed Successfully! ===")
    print(f"Total Triplets:        {stats['total_count']}")
    print(f"Train Triplets:        {stats['train_count']}")
    print(f"Val Triplets:          {stats['val_count']}")
    print(f"Test (In-Dist):        {stats['test_id_count']}")
    print(f"Test (Held-Out):       {stats['test_heldout_count']}")
    print(f"Avg Program Lines:     {stats['avg_program_lines']:.1f}")
    print(f"Avg Patch Lines:       {stats['avg_patch_lines']:.1f}")
    print(f"Patch-to-Full Ratio:   {stats['patch_to_full_token_ratio']:.3f} (Patch is {100*(1-stats['patch_to_full_token_ratio']):.1f}% more compact)")


if __name__ == "__main__":
    main()
