"""
Natural language instruction generation engine for CAD edits.
Generates human-like, semantic engineering instructions with varied phrasing and exact arithmetic.
"""

from typing import Dict, Any, List, Tuple, Optional
import random

VERBS_INCREASE = ["Increase", "Enlarge", "Expand", "Widen", "Scale up", "Lengthen", "Boost", "Extend"]
VERBS_DECREASE = ["Decrease", "Reduce", "Narrow", "Scale down", "Shorten", "Diminish", "Shrink", "Trim"]
VERBS_SET = ["Set", "Change", "Adjust", "Modify", "Update", "Configure", "Re-dimension"]

UNITS = ["mm", " mm", ""]


def format_instruction_single_abs(semantic_name: str, old_val: float, new_val: float, rng: random.Random) -> str:
    """e.g. 'Increase the base length from 50 mm to 60 mm' or 'Set the mounting hole diameter to 8 mm'."""
    verb_set = rng.choice(VERBS_SET)
    unit = rng.choice(UNITS)
    val_str = f"{new_val:.1f}".rstrip("0").rstrip(".") if new_val == int(new_val) else f"{new_val:.1f}"
    old_str = f"{old_val:.1f}".rstrip("0").rstrip(".") if old_val == int(old_val) else f"{old_val:.1f}"

    patterns = [
        f"{verb_set} the {semantic_name} to {val_str}{unit}.",
        f"Please update the {semantic_name} to {val_str}{unit}.",
        f"{'Increase' if new_val > old_val else 'Reduce'} the {semantic_name} to {val_str}{unit}.",
        f"Modify the {semantic_name} from {old_str}{unit} to {val_str}{unit}.",
        f"Make the {semantic_name} equal to {val_str}{unit}.",
    ]
    return rng.choice(patterns)


def format_instruction_single_rel(semantic_name: str, delta: float, rng: random.Random) -> str:
    """e.g. 'Enlarge the plate length by 10 mm' or 'Reduce the wall thickness by 2 mm'."""
    unit = rng.choice(UNITS)
    abs_delta = abs(delta)
    delta_str = f"{abs_delta:.1f}".rstrip("0").rstrip(".") if abs_delta == int(abs_delta) else f"{abs_delta:.1f}"

    if delta > 0:
        verb = rng.choice(VERBS_INCREASE)
        patterns = [
            f"{verb} the {semantic_name} by {delta_str}{unit}.",
            f"Make the {semantic_name} {delta_str}{unit} larger.",
            f"Add {delta_str}{unit} to the {semantic_name}.",
            f"Expand the {semantic_name} by an additional {delta_str}{unit}.",
        ]
    else:
        verb = rng.choice(VERBS_DECREASE)
        patterns = [
            f"{verb} the {semantic_name} by {delta_str}{unit}.",
            f"Make the {semantic_name} {delta_str}{unit} smaller.",
            f"Subtract {delta_str}{unit} from the {semantic_name}.",
            f"Trim {delta_str}{unit} off the {semantic_name}.",
        ]
    return rng.choice(patterns)


def format_instruction_single_factor(semantic_name: str, factor: float, rng: random.Random) -> str:
    """e.g. 'Double the hole radius' or 'Reduce the plate width by 25%'."""
    if factor == 2.0:
        return rng.choice([
            f"Double the {semantic_name}.",
            f"Scale up the {semantic_name} by a factor of 2.",
            f"Increase the {semantic_name} by 100%."
        ])
    elif factor == 0.5:
        return rng.choice([
            f"Halve the {semantic_name}.",
            f"Scale down the {semantic_name} by 50%.",
            f"Cut the {semantic_name} in half."
        ])
    elif factor == 1.5:
        return rng.choice([
            f"Increase the {semantic_name} by 50%.",
            f"Scale up the {semantic_name} by 1.5x.",
        ])
    elif factor == 0.75:
        return rng.choice([
            f"Reduce the {semantic_name} by 25%.",
            f"Scale down the {semantic_name} to 75% of its current size.",
        ])
    else:
        return f"Scale the {semantic_name} by {factor:.2f}x."


def format_instruction_multi_param(changes: List[Tuple[str, str, float, float]], rng: random.Random) -> str:
    """
    changes: [(param, semantic_name, old_val, new_val), ...]
    e.g. 'Adjust dimensions: increase base length to 70 mm and reduce width by 5 mm.'
    """
    clauses = []
    for param, sem_name, old_v, new_v in changes:
        delta = new_v - old_v
        unit = rng.choice(UNITS)
        val_str = f"{new_v:.1f}".rstrip("0").rstrip(".") if new_v == int(new_v) else f"{new_v:.1f}"
        delta_str = f"{abs(delta):.1f}".rstrip("0").rstrip(".") if abs(delta) == int(abs(delta)) else f"{abs(delta):.1f}"

        if rng.random() > 0.5:
            # Absolute clause
            clause = f"{'increase' if delta > 0 else 'decrease'} the {sem_name} to {val_str}{unit}"
        else:
            # Relative clause
            clause = f"{'expand' if delta > 0 else 'reduce'} the {sem_name} by {delta_str}{unit}"
        clauses.append(clause)

    return f"Simultaneously {clauses[0]} and {clauses[1]}."


def format_instruction_feature_toggle(feature_name: str, enable: bool, value: Optional[float], rng: random.Random) -> str:
    if enable:
        v_str = f"{value:.1f}".rstrip("0").rstrip(".") if value and value == int(value) else f"{value:.1f}"
        return rng.choice([
            f"Add {feature_name} with a radius of {v_str} mm.",
            f"Apply {feature_name} of size {v_str} mm to the edges.",
            f"Include {feature_name} ({v_str} mm) along the top edges."
        ])
    else:
        return rng.choice([
            f"Remove the {feature_name} from the model.",
            f"Eliminate the {feature_name} to leave sharp edges.",
            f"Disable the {feature_name}."
        ])
