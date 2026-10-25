"""
Core evaluation pipeline: evaluates a model/baseline across a dataset split.
"""

from typing import List, Dict, Any, Optional, Tuple
import json
import os
import tempfile
from cadpatch.patching import apply_patch, STATUS_SUCCESS
from cadpatch.sandbox import CadQueryDaemonSandbox, execute_cadquery_sandbox
from .program_metrics import evaluate_program
from .geometry_metrics import compute_geometry_metrics
from .aggregator import aggregate_metrics


def evaluate_dataset(
    samples: List[Dict[str, Any]],
    predictor: Any,
    sandbox: Optional[Any] = None,
    max_samples: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Evaluates a predictor across a list of dataset samples.
    Returns (per_sample_results, aggregated_metrics).
    """
    eval_samples = samples[:max_samples] if max_samples else samples
    results: List[Dict[str, Any]] = []

    own_sandbox = False
    if sandbox is None:
        sandbox = CadQueryDaemonSandbox()
        own_sandbox = True

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, sample in enumerate(eval_samples):
                orig_code = sample["original"]
                gt_code = sample["edited"]
                gt_patch = sample["patch"]
                intended_params = sample.get("params_changed", [])

                # 1. Prediction
                pred_patch, pred_code = predictor.predict(sample)

                # 2. Patch application check
                if pred_patch:
                    applied_code, patch_status = apply_patch(orig_code, pred_patch)
                    patch_apply_success = (patch_status == STATUS_SUCCESS)
                    # Use applied code if patch succeeded
                    if patch_apply_success:
                        code_to_run = applied_code
                    else:
                        code_to_run = pred_code or orig_code
                else:
                    code_to_run = pred_code or orig_code
                    patch_apply_success = False

                # 3. Sandboxed execution of predicted program
                pred_stl = os.path.join(tmpdir, f"pred_{idx}.stl")
                exec_res = sandbox.execute(code_to_run, export_stl=True, stl_path=pred_stl)
                exec_valid = (exec_res.get("status") == "SUCCESS" and exec_res.get("volume", 0) > 1e-4)

                pred_vol = exec_res.get("volume", 0.0)
                pred_bbox = exec_res.get("bbox")
                pred_stl_bytes = None
                if exec_valid and os.path.exists(pred_stl):
                    with open(pred_stl, "rb") as f:
                        pred_stl_bytes = f.read()

                # 4. Ground truth solid execution for exact mesh comparison
                gt_stl = os.path.join(tmpdir, f"gt_{idx}.stl")
                gt_exec = sandbox.execute(gt_code, export_stl=True, stl_path=gt_stl)
                gt_vol = gt_exec.get("volume", sample.get("edited_volume", 1.0))
                gt_bbox = gt_exec.get("bbox", sample.get("edited_bbox"))
                gt_stl_bytes = None
                if os.path.exists(gt_stl):
                    with open(gt_stl, "rb") as f:
                        gt_stl_bytes = f.read()

                # 5. Program metrics
                prog_metrics = evaluate_program(
                    orig_code=orig_code,
                    pred_code=code_to_run,
                    gt_code=gt_code,
                    pred_patch=pred_patch,
                    gt_patch=gt_patch,
                    intended_params=intended_params,
                    patch_apply_success=patch_apply_success,
                    exec_valid=exec_valid
                )

                # 6. Geometry metrics
                geo_metrics = compute_geometry_metrics(
                    pred_stl_bytes=pred_stl_bytes,
                    gt_stl_bytes=gt_stl_bytes,
                    pred_vol=pred_vol,
                    gt_vol=gt_vol,
                    pred_bbox=pred_bbox,
                    gt_bbox=gt_bbox
                )

                sample_record = {
                    "id": sample.get("id", f"sample_{idx}"),
                    "template": sample.get("template", "unknown"),
                    "category": sample.get("category", "unknown"),
                    "edit_type": sample.get("edit_type", "unknown"),
                    **prog_metrics,
                    **geo_metrics
                }
                results.append(sample_record)

    finally:
        if own_sandbox:
            sandbox.close()

    aggregated = aggregate_metrics(results)
    return results, aggregated
