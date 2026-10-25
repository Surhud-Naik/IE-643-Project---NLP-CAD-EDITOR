#!/usr/bin/env python3
"""
CLI entry point to evaluate baseline models and oracle sanity checks.
Usage: python scripts/run_baselines.py --config configs/eval.yaml
"""

import argparse
import yaml
import json
import os
import pandas as pd
from cadpatch.sandbox import CadQueryDaemonSandbox
from cadpatch.eval import evaluate_dataset, format_markdown_table, create_summary_dataframe
from cadpatch.baselines import (
    OracleGroundTruth,
    OracleNoOp,
    OracleRandomPerturbation,
    PromptedFewShotPatch,
    PromptedFullRegeneration,
)


def load_jsonl(path: str):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def main():
    parser = argparse.ArgumentParser(description="Run baseline evaluation")
    parser.add_argument("--config", type=str, default="configs/eval.yaml")
    parser.add_argument("--samples", type=int, default=None)
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    test_id_path = cfg.get("test_id_path", "data/test_id.jsonl")
    output_dir = cfg.get("output_dir", "outputs/eval")
    max_samples = args.samples or cfg.get("max_eval_samples", 80)

    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading test dataset from: {test_id_path}")
    test_samples = load_jsonl(test_id_path)
    eval_subset = test_samples[:max_samples]
    print(f"Evaluating on {len(eval_subset)} test samples...")

    baselines = {
        "Oracle Ground Truth (Upper Bound)": OracleGroundTruth(),
        "Oracle No-Op (Identity Lower Bound)": OracleNoOp(),
        "Oracle Random Perturbation": OracleRandomPerturbation(seed=42),
        "Prompted Few-Shot Patch (Baseline)": PromptedFewShotPatch(rng_seed=42),
        "Prompted Full Regeneration (Baseline)": PromptedFullRegeneration(noise_prob=0.10, rng_seed=42),
    }

    results_map = {}

    with CadQueryDaemonSandbox() as daemon_sb:
        for name, model in baselines.items():
            print(f"--> Running baseline: {name} ...")
            sample_res, agg = evaluate_dataset(eval_subset, model, sandbox=daemon_sb)
            results_map[name] = agg

            # Save detailed per-sample CSV
            safe_name = name.lower().replace(" ", "_").replace("(", "").replace(")", "")
            csv_path = os.path.join(output_dir, f"{safe_name}_samples.csv")
            pd.DataFrame(sample_res).to_csv(csv_path, index=False)

    md_table = format_markdown_table(results_map)
    print("\n=== Baseline Evaluation Results (In-Distribution Test Set) ===")
    print(md_table)

    table_path = os.path.join(output_dir, "baseline_results.md")
    with open(table_path, "w", encoding="utf-8") as f:
        f.write("# Baseline Evaluation Results\n\n")
        f.write(md_table + "\n")

    print(f"\nSaved baseline summary table to: {table_path}")


if __name__ == "__main__":
    main()
