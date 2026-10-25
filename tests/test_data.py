import pytest
import random
from cadpatch.templates import ALL_TEMPLATES
from cadpatch.data import synthesize_triplet, generate_dataset
from cadpatch.patching import apply_patch, STATUS_SUCCESS


def test_synthesize_triplet():
    rng = random.Random(999)
    template = ALL_TEMPLATES[0]  # box_plate
    triplet = synthesize_triplet(template, "single_param_rel", rng)
    assert triplet is not None
    assert triplet["template"] == "box_plate"
    assert len(triplet["instruction"]) > 0
    assert triplet["orig_volume"] > 0
    assert triplet["edited_volume"] > 0
    assert triplet["orig_volume"] != triplet["edited_volume"]

    # Verify patch round-trip
    reconstructed, status = apply_patch(triplet["original"], triplet["patch"])
    assert status == STATUS_SUCCESS
    assert reconstructed.strip() == triplet["edited"].strip()


def test_dataset_generation_small(tmp_path):
    stats = generate_dataset(target_count=20, output_dir=str(tmp_path), seed=42)
    assert stats["total_count"] == 20
    assert stats["train_count"] > 0
    assert stats["val_count"] > 0
    assert stats["test_id_count"] > 0
    assert stats["test_heldout_count"] > 0
