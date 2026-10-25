"""
Program-level evaluation metrics: execution validity, patch application, exact match,
AST parameter modification correctness, and unintended change rates.
"""

from typing import Dict, Any, List, Set, Tuple
import ast
import difflib
import re
from rapidfuzz.distance import Levenshtein


def normalize_code(code: str) -> str:
    """Normalizes whitespace and standardizes newlines."""
    lines = [line.strip() for line in code.replace("\r\n", "\n").split("\n")]
    return "\n".join([line for line in lines if line])


def extract_top_level_params(code_str: str) -> Dict[str, Any]:
    """Extracts top-level variable assignments using AST analysis."""
    params = {}
    try:
        tree = ast.parse(code_str)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Attempt to evaluate constant or unary number
                        if isinstance(node.value, ast.Constant):
                            params[target.id] = node.value.value
                        elif isinstance(node.value, ast.UnaryOp) and isinstance(node.value.operand, ast.Constant):
                            val = node.value.operand.value
                            params[target.id] = -val if isinstance(node.value.op, ast.USub) else val
    except Exception:
        pass
    return params


def compute_token_f1(pred_patch: str, gt_patch: str) -> float:
    """Computes token-level precision, recall, and F1 score between patches."""
    pred_tokens = re.findall(r"\w+|[^\w\s]", pred_patch)
    gt_tokens = re.findall(r"\w+|[^\w\s]", gt_patch)

    if not pred_tokens and not gt_tokens:
        return 1.0
    if not pred_tokens or not gt_tokens:
        return 0.0

    pred_counts = {}
    for t in pred_tokens:
        pred_counts[t] = pred_counts.get(t, 0) + 1
    
    gt_counts = {}
    for t in gt_tokens:
        gt_counts[t] = gt_counts.get(t, 0) + 1

    common_count = 0
    for t, count in pred_counts.items():
        if t in gt_counts:
            common_count += min(count, gt_counts[t])

    precision = common_count / len(pred_tokens)
    recall = common_count / len(gt_tokens)

    if precision + recall == 0:
        return 0.0
    return 2.0 * (precision * recall) / (precision + recall)


def compute_unintended_changes(orig_code: str, pred_code: str, gt_code: str) -> float:
    """
    Computes fraction of lines changed in pred_code relative to orig_code
    that were NOT modified in the ground-truth edit gt_code.
    """
    orig_lines = orig_code.replace("\r\n", "\n").splitlines()
    pred_lines = pred_code.replace("\r\n", "\n").splitlines()
    gt_lines = gt_code.replace("\r\n", "\n").splitlines()

    # Ground truth changed line numbers in orig
    sm_gt = difflib.SequenceMatcher(None, orig_lines, gt_lines)
    gt_changed_orig_indices: Set[int] = set()
    for tag, i1, i2, j1, j2 in sm_gt.get_opcodes():
        if tag != "equal":
            for idx in range(i1, max(i1 + 1, i2)):
                gt_changed_orig_indices.add(idx)

    # Pred changed line numbers in orig
    sm_pred = difflib.SequenceMatcher(None, orig_lines, pred_lines)
    pred_changed_orig_indices: Set[int] = set()
    for tag, i1, i2, j1, j2 in sm_pred.get_opcodes():
        if tag != "equal":
            for idx in range(i1, max(i1 + 1, i2)):
                pred_changed_orig_indices.add(idx)

    if not pred_changed_orig_indices:
        return 0.0

    unintended = pred_changed_orig_indices - gt_changed_orig_indices
    return len(unintended) / len(pred_changed_orig_indices)


def evaluate_program(
    orig_code: str,
    pred_code: str,
    gt_code: str,
    pred_patch: str,
    gt_patch: str,
    intended_params: List[str],
    patch_apply_success: bool,
    exec_valid: bool
) -> Dict[str, Any]:
    """
    Evaluates comprehensive program-level metrics.
    """
    norm_pred = normalize_code(pred_code)
    norm_gt = normalize_code(gt_code)

    exact_match = (norm_pred == norm_gt)
    
    # Normalized Levenshtein distance: 0 (identical) to 1 (totally different)
    max_len = max(len(norm_pred), len(norm_gt), 1)
    edit_dist = Levenshtein.distance(norm_pred, norm_gt) / max_len

    # Patch token F1
    patch_f1 = compute_token_f1(pred_patch, gt_patch)

    # Parameter correctness via AST
    orig_params = extract_top_level_params(orig_code)
    pred_params = extract_top_level_params(pred_code)

    modified_params = [
        k for k in set(orig_params.keys()) | set(pred_params.keys())
        if orig_params.get(k) != pred_params.get(k)
    ]

    # Correct parameter modified: exactly intended parameters were modified
    correct_param_modified = (set(modified_params) == set(intended_params))

    # Unintended changes rate
    unintended_rate = compute_unintended_changes(orig_code, pred_code, gt_code)

    # Token ratio (predicted patch tokens vs full program tokens)
    pred_tokens = len(pred_patch.split())
    full_tokens = max(len(pred_code.split()), 1)
    token_ratio = pred_tokens / full_tokens

    return {
        "patch_apply_success": float(patch_apply_success),
        "exec_valid": float(exec_valid),
        "exact_match": float(exact_match),
        "norm_edit_distance": float(edit_dist),
        "patch_token_f1": float(patch_f1),
        "correct_param_modified": float(correct_param_modified),
        "unintended_change_rate": float(unintended_rate),
        "token_ratio": float(token_ratio),
    }
