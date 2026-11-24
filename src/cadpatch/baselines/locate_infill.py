"""
Locate-then-Infill two-stage ablation pipeline (adapting the CAD-Editor paradigm to code).
Stage 1: Line-span localization.
Stage 2: Masked code infilling.
"""

from typing import Dict, Any, Tuple, Optional
import difflib
import re
from cadpatch.patching import make_patch, apply_patch
from cadpatch.patching.expr import resolve_parameter_target, resolve_instruction_edits
from cadpatch.eval.program_metrics import extract_top_level_params
from cadpatch.models.prompt_formatter import format_locate_prompt, format_infill_prompt


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
    Two-stage pipeline adapting the CAD-Editor paradigm to code:
    1. Locator: predicts target line range to modify (using format_locate_prompt or AST locator).
    2. Infiller: infills the masked line range with updated code (using format_infill_prompt).
    Does NOT cheat on ground truth.
    """
    def __init__(
        self,
        locator_model: Optional[Any] = None,
        infiller_model: Optional[Any] = None,
    ):
        self.locator_model = locator_model
        self.infiller_model = infiller_model

    def locate_span(self, sample: Dict[str, Any]) -> Tuple[Tuple[int, int], float]:
        """Predicts (start_line, end_line) and computes locator IoU against ground truth."""
        orig = sample["original"]
        instruction = sample["instruction"]
        gt_span = find_ground_truth_span(orig, sample.get("edited", orig))

        # Format standardized locate prompt
        locate_prompt = format_locate_prompt(orig, instruction)

        if self.locator_model is not None:
            # Neural locator prediction
            raw_pred = self.locator_model(locate_prompt)
            match = re.search(r"(\d+)\s*[:,\-]\s*(\d+)", raw_pred)
            if match:
                s, e = int(match.group(1)), int(match.group(2))
                pred_span = (min(s, e), max(s, e))
            else:
                pred_span = (1, 1)
        else:
            # Algorithmic parameter locator using AST analysis
            orig_lines = orig.splitlines()
            params = extract_top_level_params(orig)
            target_param = resolve_parameter_target(instruction, params)

            pred_span = (1, 1)
            if target_param:
                for i, line in enumerate(orig_lines):
                    line_clean = line.strip()
                    if re.match(rf"^{re.escape(target_param)}\s*=", line_clean):
                        pred_span = (i + 1, i + 1)
                        break

        iou = compute_span_iou(pred_span, gt_span)
        return pred_span, iou

    def infill_span(self, orig_code: str, span: Tuple[int, int], sample: Dict[str, Any]) -> str:
        """Infills the masked line span without accessing ground truth."""
        orig_lines = orig_code.splitlines()
        s, e = span
        s_idx = max(0, s - 1)
        e_idx = min(len(orig_lines), e)

        # Create masked program
        masked_lines = orig_lines[:s_idx] + ["<<<< MASK >>>>"] + orig_lines[e_idx:]
        masked_code = "\n".join(masked_lines)

        infill_prompt = format_infill_prompt(masked_code, sample["instruction"])

        if self.infiller_model is not None:
            replacement_lines = self.infiller_model(infill_prompt).strip().splitlines()
        else:
            # Resolves edited code purely from instruction and inserts lines into masked span
            res = resolve_instruction_edits(orig_code, sample["instruction"])
            if res["success"]:
                full_edited_lines = res["edited_script"].splitlines()
                # Extract replacement lines for the located span
                replacement_lines = full_edited_lines[s_idx:e_idx]
            else:
                replacement_lines = orig_lines[s_idx:e_idx]

        reconstructed_lines = orig_lines[:s_idx] + replacement_lines + orig_lines[e_idx:]
        return "\n".join(reconstructed_lines)

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        pred_span, _ = self.locate_span(sample)
        edited_prog = self.infill_span(sample["original"], pred_span, sample)
        patch = make_patch(sample["original"], edited_prog)
        return patch, edited_prog
