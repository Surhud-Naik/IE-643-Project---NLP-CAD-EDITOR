"""
Synthetic dataset generator: synthesizes (original_script, instruction, edited_script, patch) triplets.
Validates 100% of samples through CadQuery execution and enforces physical and geometric feasibility.
"""

from typing import Dict, Any, List, Optional, Tuple
import random
import json
import os
from cadpatch.templates import ALL_TEMPLATES, TEMPLATE_REGISTRY, CADTemplate
from cadpatch.patching import make_patch, apply_patch, STATUS_SUCCESS
from cadpatch.sandbox import execute_cadquery_sandbox, CadQueryDaemonSandbox
from .instructions import (
    format_instruction_single_abs,
    format_instruction_single_rel,
    format_instruction_single_factor,
    format_instruction_multi_param,
    format_instruction_feature_toggle,
)

EDIT_TYPES = [
    "single_param_abs",
    "single_param_rel",
    "single_param_factor",
    "multi_param",
    "feature_toggle",
    "count_spacing",
]


def synthesize_triplet(
    template: CADTemplate,
    edit_type: str,
    rng: random.Random,
    max_attempts: int = 50,
    sandbox: Optional[Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Synthesizes a single validated CAD editing triplet.
    Returns None if valid edit cannot be formed within max_attempts.
    """
    for _ in range(max_attempts):
        orig_params = template.sample_valid_params(rng)
        orig_features = dict(template.feature_flags)

        edited_params = dict(orig_params)
        edited_features = dict(orig_features)
        instruction = ""
        params_changed = []

        # 1. Feature Toggle Edit (if supported)
        if edit_type == "feature_toggle" and template.feature_flags:
            flag_name = list(template.feature_flags.keys())[0]
            current_state = orig_features[flag_name]
            edited_features[flag_name] = not current_state
            
            # Semantic naming
            feat_label = "fillet" if "fillet" in flag_name else "chamfer"
            val = orig_params.get("FILLET_R") or orig_params.get("CHAMFER_D") or 3.0
            instruction = format_instruction_feature_toggle(feat_label, edited_features[flag_name], val, rng)
            params_changed = [flag_name]

        # 2. Count / Spacing Edit
        elif edit_type == "count_spacing" and ("BOLT_COUNT" in orig_params or "MARGIN" in orig_params):
            if "BOLT_COUNT" in orig_params:
                param = "BOLT_COUNT"
                choices = [4, 6, 8]
                new_c = rng.choice([c for c in choices if c != int(orig_params[param])])
                edited_params[param] = float(new_c)
                sem = rng.choice(template.semantic_names[param])
                instruction = rng.choice([
                    f"Change the {sem} to {new_c}.",
                    f"Adjust the model to have {new_c} bolt holes.",
                    f"Set {sem} to {new_c}."
                ])
                params_changed = [param]
            else:
                param = "MARGIN"
                delta = rng.choice([-3.0, -2.0, 2.0, 3.0])
                edited_params[param] = orig_params[param] + delta
                sem = rng.choice(template.semantic_names[param])
                instruction = format_instruction_single_rel(sem, delta, rng)
                params_changed = [param]

        # 3. Multi-Parameter Edit
        elif edit_type == "multi_param":
            keys = [k for k in orig_params.keys() if k != "BOLT_COUNT"]
            if len(keys) < 2:
                continue
            selected_params = rng.sample(keys, 2)
            changes = []
            valid_shift = True
            for p in selected_params:
                p_min, p_max, _ = template.param_specs[p]
                delta = rng.choice([-6.0, -4.0, -2.0, 2.0, 4.0, 6.0])
                new_val = orig_params[p] + delta
                if not (p_min <= new_val <= p_max):
                    valid_shift = False
                    break
                edited_params[p] = new_val
                sem = rng.choice(template.semantic_names[p])
                changes.append((p, sem, orig_params[p], new_val))
                params_changed.append(p)
            if not valid_shift:
                continue
            instruction = format_instruction_multi_param(changes, rng)

        # 4. Single Parameter Relative Edit
        elif edit_type == "single_param_rel":
            keys = [k for k in orig_params.keys() if k != "BOLT_COUNT"]
            param = rng.choice(keys)
            p_min, p_max, _ = template.param_specs[param]
            delta = rng.choice([-8.0, -5.0, -3.0, -2.0, 2.0, 3.0, 5.0, 8.0])
            new_val = orig_params[param] + delta
            if not (p_min <= new_val <= p_max):
                continue
            edited_params[param] = new_val
            sem = rng.choice(template.semantic_names[param])
            instruction = format_instruction_single_rel(sem, delta, rng)
            params_changed = [param]

        # 5. Single Parameter Factor Edit
        elif edit_type == "single_param_factor":
            keys = [k for k in orig_params.keys() if k != "BOLT_COUNT"]
            param = rng.choice(keys)
            p_min, p_max, _ = template.param_specs[param]
            factor = rng.choice([0.5, 0.75, 1.5, 2.0])
            new_val = round((orig_params[param] * factor) * 2) / 2
            if not (p_min <= new_val <= p_max) or new_val == orig_params[param]:
                continue
            edited_params[param] = new_val
            sem = rng.choice(template.semantic_names[param])
            instruction = format_instruction_single_factor(sem, factor, rng)
            params_changed = [param]

        # 6. Single Parameter Absolute Edit (Default)
        else:
            keys = [k for k in orig_params.keys() if k != "BOLT_COUNT"]
            param = rng.choice(keys)
            p_min, p_max, _ = template.param_specs[param]
            possible_vals = [v for v in [p_min + i * 2.0 for i in range(int((p_max - p_min) / 2) + 1)] if abs(v - orig_params[param]) >= 2.0]
            if not possible_vals:
                continue
            new_val = rng.choice(possible_vals)
            edited_params[param] = new_val
            sem = rng.choice(template.semantic_names[param])
            instruction = format_instruction_single_abs(sem, orig_params[param], new_val, rng)
            params_changed = [param]

        # Check edited constraints
        if not template.constraints_fn(edited_params):
            continue

        orig_code = template.render(orig_params, orig_features)
        edited_code = template.render(edited_params, edited_features)

        if orig_code.strip() == edited_code.strip():
            continue

        # Derive patch and verify round-trip
        patch = make_patch(orig_code, edited_code)
        if not patch:
            continue
        reconstructed, status = apply_patch(orig_code, patch)
        if status != STATUS_SUCCESS or reconstructed.strip() != edited_code.strip():
            continue

        # Execute both in sandbox to guarantee solid validity
        def _exec(code):
            if sandbox is not None:
                return sandbox.execute(code)
            return execute_cadquery_sandbox(code, timeout=15.0)

        orig_res = _exec(orig_code)
        if orig_res.get("status") != "SUCCESS" or orig_res.get("volume", 0) <= 1e-4:
            continue

        edited_res = _exec(edited_code)
        if edited_res.get("status") != "SUCCESS" or edited_res.get("volume", 0) <= 1e-4:
            continue

        # Check geometry actually changed
        vol_diff = abs(orig_res["volume"] - edited_res["volume"])
        if vol_diff <= 1e-4:
            continue

        return {
            "template": template.name,
            "category": template.category,
            "edit_type": edit_type,
            "original": orig_code,
            "instruction": instruction,
            "edited": edited_code,
            "patch": patch,
            "params_changed": params_changed,
            "orig_volume": orig_res["volume"],
            "edited_volume": edited_res["volume"],
            "orig_bbox": orig_res["bbox"],
            "edited_bbox": edited_res["bbox"],
        }

    return None


def generate_dataset(
    target_count: int = 1200,
    held_out_templates: Optional[List[str]] = None,
    seed: int = 42,
    output_dir: str = "data"
) -> Dict[str, Any]:
    """
    Generates train, val, test_id, and test_heldout splits.
    Saves JSONL files and returns dataset statistics.
    """
    rng = random.Random(seed)
    held_out = set(held_out_templates or ["shelled_box", "revolve_pulley"])
    
    in_dist_templates = [t for t in ALL_TEMPLATES if t.name not in held_out]
    held_out_tmpl_list = [t for t in ALL_TEMPLATES if t.name in held_out]

    os.makedirs(output_dir, exist_ok=True)

    triplets_in_dist = []
    triplets_held_out = []

    # Distribution of edit types
    edit_weights = {
        "single_param_abs": 0.25,
        "single_param_rel": 0.25,
        "single_param_factor": 0.15,
        "multi_param": 0.20,
        "feature_toggle": 0.08,
        "count_spacing": 0.07,
    }

    print(f"Generating synthetic CAD edit dataset (Target: {target_count} total)...")

    # In-distribution generation
    target_in_dist = int(target_count * 0.8)
    attempts = 0
    max_total_attempts = target_in_dist * 4

    seen_pairs = set()

    with CadQueryDaemonSandbox() as daemon_sb:
        while len(triplets_in_dist) < target_in_dist and attempts < max_total_attempts:
            attempts += 1
            tmpl = rng.choice(in_dist_templates)
            edit_type = rng.choices(list(edit_weights.keys()), weights=list(edit_weights.values()))[0]

            triplet = synthesize_triplet(tmpl, edit_type, rng, sandbox=daemon_sb)
            if triplet:
                pair_key = (triplet["original"].strip(), triplet["instruction"].strip())
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                triplet["id"] = f"id_{len(triplets_in_dist):04d}"
                triplets_in_dist.append(triplet)
                if len(triplets_in_dist) % 100 == 0:
                    print(f"  [In-Dist] Generated {len(triplets_in_dist)} / {target_in_dist} valid triplets...")

        # Held-out generation
        target_held_out = target_count - len(triplets_in_dist)
        attempts = 0
        max_ho_attempts = target_held_out * 4

        while len(triplets_held_out) < target_held_out and attempts < max_ho_attempts:
            attempts += 1
            tmpl = rng.choice(held_out_tmpl_list)
            # Note: revolve_pulley and shelled_box don't have feature_toggle or count_spacing
            ho_edits = ["single_param_abs", "single_param_rel", "single_param_factor", "multi_param"]
            edit_type = rng.choice(ho_edits)

            triplet = synthesize_triplet(tmpl, edit_type, rng, sandbox=daemon_sb)
            if triplet:
                pair_key = (triplet["original"].strip(), triplet["instruction"].strip())
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                triplet["id"] = f"ho_{len(triplets_held_out):04d}"
                triplets_held_out.append(triplet)
                if len(triplets_held_out) % 50 == 0:
                    print(f"  [Held-Out] Generated {len(triplets_held_out)} / {target_held_out} valid triplets...")

    # Shuffle in-distribution and partition: 70% train, 15% val, 15% test_id
    rng.shuffle(triplets_in_dist)
    n_in = len(triplets_in_dist)
    n_train = int(n_in * 0.70)
    n_val = int(n_in * 0.15)

    train_data = triplets_in_dist[:n_train]
    val_data = triplets_in_dist[n_train:n_train + n_val]
    test_id_data = triplets_in_dist[n_train + n_val:]
    test_ho_data = triplets_held_out

    # Split leakage verification
    train_keys = { (d["original"].strip(), d["instruction"].strip()) for d in train_data }
    val_keys = { (d["original"].strip(), d["instruction"].strip()) for d in val_data }
    test_id_keys = { (d["original"].strip(), d["instruction"].strip()) for d in test_id_data }
    test_ho_keys = { (d["original"].strip(), d["instruction"].strip()) for d in test_ho_data }

    assert len(train_keys & val_keys) == 0, "Leakage detected between train and val!"
    assert len(train_keys & test_id_keys) == 0, "Leakage detected between train and test_id!"
    assert len(train_keys & test_ho_keys) == 0, "Leakage detected between train and test_ho!"

    # Write files
    def save_jsonl(path: str, data: List[Dict[str, Any]]):
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")

    train_path = os.path.join(output_dir, "train.jsonl")
    val_path = os.path.join(output_dir, "val.jsonl")
    test_id_path = os.path.join(output_dir, "test_id.jsonl")
    test_ho_path = os.path.join(output_dir, "test_heldout.jsonl")

    save_jsonl(train_path, train_data)
    save_jsonl(val_path, val_data)
    save_jsonl(test_id_path, test_id_data)
    save_jsonl(test_ho_path, test_ho_data)

    # Compute statistics
    all_data = train_data + val_data + test_id_data + test_ho_data
    avg_orig_len = sum(len(d["original"].splitlines()) for d in all_data) / len(all_data)
    avg_patch_len = sum(len(d["patch"].splitlines()) for d in all_data) / len(all_data)
    token_ratio = sum(len(d["patch"].split()) for d in all_data) / sum(len(d["edited"].split()) for d in all_data)

    stats = {
        "total_count": len(all_data),
        "train_count": len(train_data),
        "val_count": len(val_data),
        "test_id_count": len(test_id_data),
        "test_heldout_count": len(test_ho_data),
        "avg_program_lines": avg_orig_len,
        "avg_patch_lines": avg_patch_len,
        "patch_to_full_token_ratio": token_ratio,
        "held_out_templates": list(held_out),
    }

    with open(os.path.join(output_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    return stats
