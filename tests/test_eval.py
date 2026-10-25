import pytest
import io
import trimesh
from cadpatch.eval import (
    evaluate_program,
    compute_geometry_metrics,
    compute_chamfer_distance,
    evaluate_dataset,
)
from cadpatch.baselines import OracleGroundTruth, OracleNoOp, OracleRandomPerturbation

SAMPLE_ORIG = """import cadquery as cq
LENGTH = 40.0
WIDTH = 20.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, 10.0)
"""

SAMPLE_GT = """import cadquery as cq
LENGTH = 50.0
WIDTH = 20.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, 10.0)
"""

SAMPLE_PATCH = """<<<<<<< SEARCH
LENGTH = 40.0
=======
LENGTH = 50.0
>>>>>>> REPLACE"""


def test_program_metrics_perfect_match():
    metrics = evaluate_program(
        orig_code=SAMPLE_ORIG,
        pred_code=SAMPLE_GT,
        gt_code=SAMPLE_GT,
        pred_patch=SAMPLE_PATCH,
        gt_patch=SAMPLE_PATCH,
        intended_params=["LENGTH"],
        patch_apply_success=True,
        exec_valid=True
    )
    assert metrics["exact_match"] == 1.0
    assert metrics["norm_edit_distance"] == 0.0
    assert metrics["patch_token_f1"] == 1.0
    assert metrics["correct_param_modified"] == 1.0
    assert metrics["unintended_change_rate"] == 0.0


def test_geometry_metrics_identical_mesh():
    # Box mesh
    mesh = trimesh.creation.box((10.0, 10.0, 10.0))
    stl_bytes = mesh.export(file_type="stl")
    vol = float(mesh.volume)
    bbox = {"xlen": 10.0, "ylen": 10.0, "zlen": 10.0, "diagonal": 17.32}

    metrics = compute_geometry_metrics(
        pred_stl_bytes=stl_bytes,
        gt_stl_bytes=stl_bytes,
        pred_vol=vol,
        gt_vol=vol,
        pred_bbox=bbox,
        gt_bbox=bbox,
        n_samples=2000
    )
    assert metrics["chamfer_dist_norm"] < 1e-4
    assert metrics["geometry_exact"] == 1.0
    assert metrics["volume_rel_error"] == 0.0
    assert metrics["volumetric_iou"] > 0.90


def test_oracle_sanity_checks():
    samples = [{
        "id": "test_1",
        "template": "box_plate",
        "category": "extrude",
        "edit_type": "single_param_abs",
        "original": SAMPLE_ORIG,
        "instruction": "Increase length to 50 mm.",
        "edited": SAMPLE_GT,
        "patch": SAMPLE_PATCH,
        "params_changed": ["LENGTH"]
    }]

    # 1. Oracle Ground Truth must score 100% exact match
    gt_oracle = OracleGroundTruth()
    _, gt_metrics = evaluate_dataset(samples, gt_oracle)
    assert gt_metrics["exact_match"] == 1.0
    assert gt_metrics["geometry_exact"] == 1.0
    assert gt_metrics["volumetric_iou"] > 0.85

    # 2. Oracle No-Op must score 0% exact match and low geometry fidelity
    noop_oracle = OracleNoOp()
    _, noop_metrics = evaluate_dataset(samples, noop_oracle)
    assert noop_metrics["exact_match"] == 0.0
    assert noop_metrics["geometry_exact"] == 0.0
    assert noop_metrics["volume_rel_error"] > 0.1
