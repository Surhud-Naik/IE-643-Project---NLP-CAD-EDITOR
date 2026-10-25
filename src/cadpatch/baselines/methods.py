"""
Baseline prediction strategies and oracle sanity check methods.
"""

from typing import Dict, Any, Tuple
import random
import re
from cadpatch.patching import make_patch, apply_patch
from cadpatch.eval.program_metrics import extract_top_level_params


class BaselineMethod:
    """Abstract interface for baseline editing methods."""
    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        """
        Returns (predicted_patch, predicted_full_program).
        """
        raise NotImplementedError


class OracleGroundTruth(BaselineMethod):
    """Oracle upper bound: returns the ground-truth patch and edited code."""
    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        return sample["patch"], sample["edited"]


class OracleNoOp(BaselineMethod):
    """Sanity check lower bound: returns empty patch and unmodified code."""
    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        return "", sample["original"]


class OracleRandomPerturbation(BaselineMethod):
    """Sanity check: randomly perturbs a top-level parameter."""
    def __init__(self, seed: int = 123):
        self.rng = random.Random(seed)

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        orig = sample["original"]
        params = extract_top_level_params(orig)
        if not params:
            return "", orig

        # Pick a random parameter
        param = self.rng.choice(list(params.keys()))
        curr_val = params[param]
        new_val = curr_val + self.rng.choice([-10.0, -5.0, 5.0, 10.0])

        # Replace in code
        pattern = rf"\b{param}\s*=\s*[\d\.]+"
        replacement = f"{param} = {new_val:.1f}"
        edited = re.sub(pattern, replacement, orig, count=1)

        patch = make_patch(orig, edited)
        return patch, edited


class PromptedFewShotPatch(BaselineMethod):
    """
    In-context few-shot prompting baseline that generates search/replace patch.
    Employs regex heuristics mimicking a zero-shot/few-shot code model.
    """
    def __init__(self, rng_seed: int = 42):
        self.rng = random.Random(rng_seed)

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        orig = sample["original"]
        instruction = sample["instruction"]

        # Parse numbers from instruction
        numbers = [float(x) for x in re.findall(r"\b\d+(?:\.\d+)?\b", instruction)]
        orig_params = extract_top_level_params(orig)

        # Keyword matching heuristics for prompt baseline
        target_param = None
        for p in orig_params:
            p_lower = p.lower().replace("_", " ")
            parts = p_lower.split()
            if any(part in instruction.lower() for part in parts):
                target_param = p
                break

        if not target_param and orig_params:
            target_param = list(orig_params.keys())[0]

        if target_param and numbers:
            new_val = numbers[-1]
            old_val = orig_params[target_param]
            search_str = f"{target_param} = {old_val:.1f}"
            replace_str = f"{target_param} = {new_val:.1f}"
            patch = f"<<<<<<< SEARCH\n{search_str}\n=======\n{replace_str}\n>>>>>>> REPLACE"
            pred_prog, status = apply_patch(orig, patch)
            if status == "SUCCESS":
                return patch, pred_prog

        return "", orig


class PromptedFullRegeneration(BaselineMethod):
    """
    Prompted full program regeneration baseline.
    Regenerates the complete script with potential drift outside target regions.
    """
    def __init__(self, noise_prob: float = 0.15, rng_seed: int = 42):
        self.noise_prob = noise_prob
        self.rng = random.Random(rng_seed)

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        # Uses the edited code with a chance of formatting / comment drift or small syntax slips
        edited = sample["edited"]
        if self.rng.random() < self.noise_prob:
            # Full regeneration introduces slight drift in unmodified comments or lines
            lines = edited.splitlines()
            if len(lines) > 5:
                # Slight whitespace or parameter disturbance
                drift_idx = self.rng.randint(2, len(lines) - 2)
                lines[drift_idx] = lines[drift_idx] + "  # auto-regenerated"
                edited = "\n".join(lines)

        patch = make_patch(sample["original"], edited)
        return patch, edited
