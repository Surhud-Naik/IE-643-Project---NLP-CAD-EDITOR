"""
Metric aggregation and report table generation (Markdown & CSV).
"""

from typing import List, Dict, Any
import pandas as pd


def aggregate_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Computes mean for each numerical metric."""
    if not results:
        return {}

    metric_keys = [
        "patch_apply_success",
        "exec_valid",
        "exact_match",
        "norm_edit_distance",
        "patch_token_f1",
        "correct_param_modified",
        "unintended_change_rate",
        "token_ratio",
        "chamfer_dist_norm",
        "volumetric_iou",
        "volume_rel_error",
        "bbox_rel_error",
        "geometry_exact",
    ]

    agg = {}
    for k in metric_keys:
        vals = [r[k] for r in results if k in r]
        agg[k] = float(sum(vals) / len(vals)) if vals else 0.0

    return agg


def create_summary_dataframe(results: List[Dict[str, Any]], group_by: str = "template") -> pd.DataFrame:
    """Creates a aggregated summary dataframe grouped by a specified attribute."""
    df = pd.DataFrame(results)
    if df.empty or group_by not in df.columns:
        return pd.DataFrame()

    num_cols = [
        "patch_apply_success",
        "exec_valid",
        "exact_match",
        "correct_param_modified",
        "unintended_change_rate",
        "token_ratio",
        "chamfer_dist_norm",
        "volumetric_iou",
        "geometry_exact",
    ]
    avail_cols = [c for c in num_cols if c in df.columns]
    summary = df.groupby(group_by)[avail_cols].mean().reset_index()
    return summary


def format_markdown_table(model_results_map: Dict[str, Dict[str, float]]) -> str:
    """
    Formats a comparative benchmark Markdown table comparing multiple models/baselines.
    model_results_map: { "Model Name": aggregated_metrics_dict, ... }
    """
    rows = []
    for model_name, m in model_results_map.items():
        rows.append({
            "Method": model_name,
            "Patch Apply (%)": f"{m.get('patch_apply_success', 0)*100:.1f}%",
            "Exec Valid (%)": f"{m.get('exec_valid', 0)*100:.1f}%",
            "Exact Match (%)": f"{m.get('exact_match', 0)*100:.1f}%",
            "Param Correct (%)": f"{m.get('correct_param_modified', 0)*100:.1f}%",
            "Unintended Change (%)": f"{m.get('unintended_change_rate', 0)*100:.1f}%",
            "Norm Chamfer": f"{m.get('chamfer_dist_norm', 1.0):.4f}",
            "Volumetric IoU": f"{m.get('volumetric_iou', 0.0):.3f}",
            "Geo Exact (%)": f"{m.get('geometry_exact', 0)*100:.1f}%",
            "Token Ratio": f"{m.get('token_ratio', 1.0):.2f}",
        })

    df = pd.DataFrame(rows)
    return df.to_markdown(index=False)
