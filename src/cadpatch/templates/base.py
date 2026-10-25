"""
Base template definitions and registry for parametric CadQuery models.
"""

from typing import Dict, Any, List, Callable, Optional, Tuple
import random


class CADTemplate:
    """
    Abstract base specification for a parametric CadQuery template.
    Enforces valid parameter ranges, physical constraints, and program code generation.
    """
    def __init__(
        self,
        name: str,
        category: str,
        param_specs: Dict[str, Tuple[float, float, float]],  # name -> (min, max, default)
        semantic_names: Dict[str, List[str]],  # param -> list of natural language descriptors
        code_generator: Callable[[Dict[str, float], Dict[str, Any]], str],
        constraints_fn: Callable[[Dict[str, float]], bool],
        feature_flags: Optional[Dict[str, bool]] = None
    ):
        self.name = name
        self.category = category
        self.param_specs = param_specs
        self.semantic_names = semantic_names
        self.code_generator = code_generator
        self.constraints_fn = constraints_fn
        self.feature_flags = feature_flags or {}

    def sample_valid_params(self, rng: random.Random) -> Dict[str, float]:
        """Samples parameter values satisfying all physical constraints."""
        for _ in range(200):
            params = {}
            for param, (p_min, p_max, _) in self.param_specs.items():
                # Pick round numbers for clean CAD dimensions (integers or .5)
                val = round(rng.uniform(p_min, p_max) * 2) / 2
                if val == int(val):
                    val = float(int(val))
                params[param] = val

            if self.constraints_fn(params):
                return params

        # Fallback to default values
        return {p: spec[2] for p, spec in self.param_specs.items()}

    def render(self, params: Dict[str, float], features: Optional[Dict[str, Any]] = None) -> str:
        """Renders executable CadQuery Python script."""
        feat = dict(self.feature_flags)
        if features:
            feat.update(features)
        return self.code_generator(params, feat)


TEMPLATE_REGISTRY: Dict[str, CADTemplate] = {}


def register_template(template: CADTemplate):
    TEMPLATE_REGISTRY[template.name] = template
