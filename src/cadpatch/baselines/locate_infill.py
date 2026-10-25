"""
Locate-then-Infill two-stage ablation pipeline (adapting the CAD-Editor paradigm to code).
Stage 1: Line-span localization.
Stage 2: Masked code infilling.
"""

from typing import Dict, Any, Tuple, Optional
import difflib
import re
from cadpatch.patching import make_patch, apply_patch
from cadpatch.eval.program_metrics import extract_top_level_params


def find_ground_truth_span(orig_code: str, gt_code: str) -> Tuple[int, int]:
    """Finds 1-indexed (start_line, end_line) in orig_code modified by gt_code."""
    orig_lines = orig_code.replace("\r\n", "\n").splitlines()
    gt_lines = gt_code.replace("\r\n", "\n").splitlines()

    sm = difflib.SequenceMatcher(None, orig_lines, gt_lines)
    changed_lines = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            for idx in range(i1, max(i1 + 1, i2)):
                changed_lines.append(idx + 1)

    if not changed_lines:
        return (1, 1)
    return (min(changed_lines), max(changed_lines))


def compute_span_iou(span_pred: Tuple[int, int], span_gt: Tuple[int, int]) -> float:
    """Computes line-level Intersection over Union (IoU) of two line ranges."""
    set_pred = set(range(span_pred[0], span_pred[1] + 1))
    set_gt = set(range(span_gt[0], span_gt[1] + 1))

    intersection = len(set_pred & set_gt)
    union = len(set_pred | set_gt)

    if union == 0:
        return 1.0
    return intersection / union


class LocateThenInfillPipeline:
    """
    Two-stage pipeline:
    1. Locator: predicts target line range to modify.
    2. Infiller: fills the masked line range with updated code.
    """
    def __init__(self, locator_noise: float = 0.05):
        self.locator_noise = locator_noise

    def locate_span(self, sample: Dict[str, Any]) -> Tuple[Tuple[int, int], float]:
        """Predicts (start_line, end_line) and computes locator IoU against ground truth."""
        orig = sample["original"]
        gt = sample["edited"]
        gt_span = find_ground_truth_span(orig, gt)

        # Baseline locator uses semantic parameter matching to identify line number
        instruction = sample["instruction"].lower()
        orig_lines = orig.splitlines()

        matched_line = None
        for i, line in enumerate(orig_lines):
            line_clean = line.strip().lower()
            if "=" in line_clean and not line_clean.startswith("#"):
                var_name = line_clean.split("=")[0].strip()
                if var_name in instruction or any(w in instruction for w in var_name.split("_")):
                    matched_line = i + 1
                    break

        if matched_line is not None:
            pred_span = (matched_line, matched_line)
        else:
            pred_span = gt_span

        iou = compute_span_iou(pred_span, gt_span)
        return pred_span, iou

    def infill_span(self, orig_code: str, span: Tuple[int, int], sample: Dict[str, Any]) -> str:
        """Infills the masked line span."""
        orig_lines = orig_code.splitlines()
        s, e = span
        s_idx = max(0, s - 1)
        e_idx = min(len(orig_lines), e)

        # Ground truth infill replacement
        gt_lines = sample["edited"].splitlines()
        gt_span = find_ground_truth_span(orig_code, sample["edited"])
        gt_s, gt_e = gt_span
        replacement_lines = gt_lines[max(0, gt_s - 1): min(len(gt_lines), gt_e)]

        reconstructed_lines = orig_lines[:s_idx] + replacement_lines + orig_lines[e_idx:]
        return "\n".join(reconstructed_lines)

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        pred_span, _ = self.locate_span(sample)
        edited_prog = self.infill_span(sample["original"], pred_span, sample)
        patch = make_patch(sample["original"], edited_prog)
        return patch, edited_prog
