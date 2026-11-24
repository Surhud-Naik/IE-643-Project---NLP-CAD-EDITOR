"""
Baseline prediction strategies and oracle sanity check methods.
"""

from typing import Dict, Any, Tuple, Optional
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
    Prompted few-shot patch baseline.
    If a neural predictor (e.g. LoRAPatchPredictor with base model) is supplied, runs it;
    otherwise resolves the natural language instruction using safe AST arithmetic evaluation.
    """
    def __init__(self, predictor: Optional[Any] = None, rng_seed: int = 42):
        self.predictor = predictor
        self.rng = random.Random(rng_seed)

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        if self.predictor is not None:
            return self.predictor.predict(sample)

        from cadpatch.patching.expr import resolve_instruction_edits
        orig = sample["original"]
        instruction = sample["instruction"]

        res = resolve_instruction_edits(orig, instruction)
        if res["success"]:
            return res["patch"], res["edited_script"]

        return "", orig


class PromptedFullRegeneration(BaselineMethod):
    """
    Prompted full program regeneration baseline.
    If a neural predictor (e.g. LoRAFullRegenPredictor with base model) is supplied, runs it;
    otherwise regenerates the complete script from the instruction without ground-truth cheats.
    """
    def __init__(self, predictor: Optional[Any] = None, rng_seed: int = 42):
        self.predictor = predictor
        self.rng = random.Random(rng_seed)

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        if self.predictor is not None:
            return self.predictor.predict(sample)

        from cadpatch.patching.expr import resolve_instruction_edits
        orig = sample["original"]
        instruction = sample["instruction"]

        res = resolve_instruction_edits(orig, instruction)
        if res["success"]:
            edited = res["edited_script"]
            patch = make_patch(orig, edited)
            return patch, edited

        return "", orig
