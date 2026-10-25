"""
Geometry service handling sandboxed execution, 3D mesh format conversion (STL, STEP, GLB),
geometry hashing/caching, and relative comparison metrics.
"""

from typing import Dict, Any, Optional, Tuple
import hashlib
import io
import re
import difflib
import trimesh
from ..sandbox.executor import execute_cadquery_sandbox, STATUS_SUCCESS
from ..eval.program_metrics import extract_top_level_params
from ..eval.geometry_metrics import compute_geometry_metrics
from .schemas import ChangeSummary, ParameterChange, GeometryMetrics


class GeometryService:
    def __init__(self, timeout: float = 20.0, enable_cache: bool = True):
        self.timeout = timeout
        self.enable_cache = enable_cache
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _hash_script(self, script: str) -> str:
        return hashlib.sha256(script.strip().encode("utf-8")).hexdigest()

    def execute_script(self, script: str, export_all: bool = True) -> Dict[str, Any]:
        """
        Executes a CadQuery script inside the sandbox.
        Exports STL, STEP, and converts to GLB.
        Caches execution output by script hash.
        """
        script_hash = self._hash_script(script)
        if self.enable_cache and script_hash in self._cache:
            return self._cache[script_hash]

        res = execute_cadquery_sandbox(
            script,
            timeout=self.timeout,
            export_step=export_all
        )

        if res.get("status") == STATUS_SUCCESS and export_all:
            stl_bytes = res.get("stl_bytes")
            if stl_bytes:
                try:
                    # Convert STL to GLB for web 3D viewer
                    mesh = trimesh.load(io.BytesIO(stl_bytes), file_type="stl")
                    glb_bytes = mesh.export(file_type="glb")
                    res["glb_bytes"] = glb_bytes
                except Exception as e:
                    res["glb_bytes"] = None
                    res["glb_error"] = str(e)

        if self.enable_cache and res.get("status") == STATUS_SUCCESS:
            self._cache[script_hash] = res

        return res

    def compute_summary_and_metrics(
        self,
        orig_script: str,
        edited_script: str,
        orig_res: Dict[str, Any],
        edited_res: Dict[str, Any],
        patch_text: str
    ) -> Tuple[ChangeSummary, GeometryMetrics]:
        """
        Calculates parameter differences, line changes, token savings,
        and 3D geometric divergence between the original and edited states.
        """
        # 1. Parameter changes via AST
        orig_params = extract_top_level_params(orig_script)
        edited_params = extract_top_level_params(edited_script)

        param_changes = []
        for k, v in orig_params.items():
            if k in edited_params and edited_params[k] != v:
                param_changes.append(ParameterChange(
                    name=k,
                    old_value=v,
                    new_value=edited_params[k]
                ))
        for k, v in edited_params.items():
            if k not in orig_params:
                param_changes.append(ParameterChange(
                    name=k,
                    old_value=None,
                    new_value=v
                ))

        # 2. Line diff calculation
        orig_lines = orig_script.splitlines()
        edited_lines = edited_script.splitlines()
        matcher = difflib.SequenceMatcher(None, orig_lines, edited_lines)
        lines_added = 0
        lines_removed = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                lines_added += (j2 - j1)
            elif tag == "delete":
                lines_removed += (i2 - i1)
            elif tag == "replace":
                lines_removed += (i2 - i1)
                lines_added += (j2 - j1)

        lines_touched = lines_added + lines_removed

        # 3. Token counts and savings
        patch_tokens = len(re.findall(r"\w+|[^\w\s]", patch_text))
        full_tokens = len(re.findall(r"\w+|[^\w\s]", edited_script))
        savings = max(0.0, (1.0 - (patch_tokens / max(full_tokens, 1))) * 100.0)

        change_summary = ChangeSummary(
            parameters_changed=param_changes,
            lines_added=lines_added,
            lines_removed=lines_removed,
            lines_touched=lines_touched,
            output_tokens=patch_tokens,
            full_program_tokens=full_tokens,
            token_savings_pct=round(savings, 1)
        )

        # 4. Geometry metrics
        orig_vol = float(orig_res.get("volume", 0.0))
        edited_vol = float(edited_res.get("volume", 0.0))
        vol_change_pct = ((edited_vol - orig_vol) / max(orig_vol, 1e-6)) * 100.0 if orig_vol > 0 else 0.0

        orig_bbox = orig_res.get("bbox") or {}
        edited_bbox = edited_res.get("bbox") or {}
        diag_orig = float(orig_bbox.get("diagonal", 0.0))
        diag_edited = float(edited_bbox.get("diagonal", 0.0))

        geo_calc = compute_geometry_metrics(
            pred_stl_bytes=edited_res.get("stl_bytes"),
            gt_stl_bytes=orig_res.get("stl_bytes"),
            pred_vol=edited_vol,
            gt_vol=orig_vol,
            pred_bbox=edited_bbox,
            gt_bbox=orig_bbox
        )

        metrics = GeometryMetrics(
            validity=(edited_res.get("status") == STATUS_SUCCESS),
            original_volume=round(orig_vol, 2),
            edited_volume=round(edited_vol, 2),
            volume_change_pct=round(vol_change_pct, 2),
            bbox_diagonal_original=round(diag_orig, 2),
            bbox_diagonal_edited=round(diag_edited, 2),
            chamfer_distance_relative=round(float(geo_calc.get("chamfer_dist_norm", 0.0)), 4),
            volumetric_iou=round(float(geo_calc.get("volumetric_iou", 0.0)), 4)
        )

        return change_summary, metrics
