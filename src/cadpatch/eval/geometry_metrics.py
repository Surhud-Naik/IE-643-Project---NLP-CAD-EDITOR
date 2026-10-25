"""
Geometry-level evaluation metrics: point cloud Chamfer distance, volumetric IoU,
bounding box error, and relative volume divergence.
"""

from typing import Dict, Any, Optional
import io
import math
import numpy as np
from scipy.spatial import cKDTree
import trimesh


def compute_chamfer_distance(pts_a: np.ndarray, pts_b: np.ndarray) -> float:
    """
    Computes two-way symmetric Chamfer Distance between two 3D point clouds.
    CD(A, B) = mean_{a in A} min_{b in B} ||a - b|| + mean_{b in B} min_{a in A} ||b - a||
    """
    if len(pts_a) == 0 or len(pts_b) == 0:
        return 1e6

    tree_b = cKDTree(pts_b)
    dist_a_to_b, _ = tree_b.query(pts_a, k=1)

    tree_a = cKDTree(pts_a)
    dist_b_to_a, _ = tree_a.query(pts_b, k=1)

    return float(np.mean(dist_a_to_b) + np.mean(dist_b_to_a))


def compute_geometry_metrics(
    pred_stl_bytes: Optional[bytes],
    gt_stl_bytes: Optional[bytes],
    pred_vol: float,
    gt_vol: float,
    pred_bbox: Optional[Dict[str, float]],
    gt_bbox: Optional[Dict[str, float]],
    n_samples: int = 2000
) -> Dict[str, Any]:
    """
    Evaluates 3D geometric fidelity between predicted and ground-truth solids.
    """
    # 1. Byte identity shortcut
    if pred_stl_bytes and gt_stl_bytes and pred_stl_bytes == gt_stl_bytes:
        return {
            "chamfer_dist_norm": 0.0,
            "volumetric_iou": 1.0,
            "volume_rel_error": 0.0,
            "bbox_rel_error": 0.0,
            "geometry_exact": 1.0,
        }

    # 2. Volume relative error
    vol_rel_err = abs(pred_vol - gt_vol) / max(gt_vol, 1e-6)

    # 3. Bounding box relative error
    if pred_bbox and gt_bbox:
        pred_extents = np.array([pred_bbox["xlen"], pred_bbox["ylen"], pred_bbox["zlen"]])
        gt_extents = np.array([gt_bbox["xlen"], gt_bbox["ylen"], gt_bbox["zlen"]])
        diag = max(gt_bbox.get("diagonal", 1.0), 1e-4)
        bbox_err = float(np.linalg.norm(pred_extents - gt_extents) / diag)
    else:
        diag = 1.0
        bbox_err = 1.0

    # 4. Chamfer Distance on sampled points
    cd_norm = 1.0
    iou = 0.0
    geo_exact = False

    if pred_stl_bytes and gt_stl_bytes and len(pred_stl_bytes) > 0 and len(gt_stl_bytes) > 0:
        try:
            mesh_pred = trimesh.load(io.BytesIO(pred_stl_bytes), file_type="stl")
            mesh_gt = trimesh.load(io.BytesIO(gt_stl_bytes), file_type="stl")

            if hasattr(mesh_pred, "sample") and hasattr(mesh_gt, "sample"):
                # Use deterministic seed for sample consistency
                np.random.seed(42)
                pts_pred, _ = trimesh.sample.sample_surface(mesh_pred, n_samples)
                np.random.seed(42)
                pts_gt, _ = trimesh.sample.sample_surface(mesh_gt, n_samples)

                raw_cd = compute_chamfer_distance(pts_pred, pts_gt)
                cd_norm = raw_cd / max(diag, 1e-4)
                geo_exact = (cd_norm < 0.01)

                # Volumetric IoU combining volume overlap ratio, bbox alignment, and surface alignment
                overlap_ratio = min(pred_vol, gt_vol) / max(pred_vol, gt_vol, 1e-6)
                surface_alignment = max(0.0, 1.0 - cd_norm)
                iou = float(max(0.0, overlap_ratio * (1.0 - min(bbox_err, 1.0)) * surface_alignment))
        except Exception:
            cd_norm = 1.0
            iou = 0.0
            geo_exact = False
    else:
        cd_norm = 1.0
        iou = 0.0
        geo_exact = False

    return {
        "chamfer_dist_norm": float(cd_norm),
        "volumetric_iou": float(iou),
        "volume_rel_error": float(vol_rel_err),
        "bbox_rel_error": float(bbox_err),
        "geometry_exact": float(geo_exact),
    }
