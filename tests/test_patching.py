import pytest
from cadpatch.patching import (
    apply_patch,
    make_patch,
    extract_patch_blocks,
    STATUS_SUCCESS,
    STATUS_NO_MATCH,
    STATUS_AMBIGUOUS,
    STATUS_MALFORMED,
)

SAMPLE_PROGRAM = """import cadquery as cq

LENGTH = 50.0
WIDTH = 30.0
HEIGHT = 15.0
HOLE_DIA = 6.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIA)
)
"""

SAMPLE_EDITED_PROGRAM = """import cadquery as cq

LENGTH = 50.0
WIDTH = 30.0
HEIGHT = 15.0
HOLE_DIA = 10.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIA)
)
"""


def test_apply_single_block_success():
    patch = """<<<<<<< SEARCH
HOLE_DIA = 6.0
=======
HOLE_DIA = 10.0
>>>>>>> REPLACE"""
    new_prog, status = apply_patch(SAMPLE_PROGRAM, patch)
    assert status == STATUS_SUCCESS
    assert "HOLE_DIA = 10.0" in new_prog
    assert "HOLE_DIA = 6.0" not in new_prog


def test_apply_multi_block_success():
    patch = """<<<<<<< SEARCH
LENGTH = 50.0
=======
LENGTH = 60.0
>>>>>>> REPLACE
<<<<<<< SEARCH
HOLE_DIA = 6.0
=======
HOLE_DIA = 8.0
>>>>>>> REPLACE"""
    new_prog, status = apply_patch(SAMPLE_PROGRAM, patch)
    assert status == STATUS_SUCCESS
    assert "LENGTH = 60.0" in new_prog
    assert "HOLE_DIA = 8.0" in new_prog


def test_apply_no_match():
    patch = """<<<<<<< SEARCH
NON_EXISTENT_VAR = 999.0
=======
NON_EXISTENT_VAR = 100.0
>>>>>>> REPLACE"""
    new_prog, status = apply_patch(SAMPLE_PROGRAM, patch)
    assert status == STATUS_NO_MATCH
    assert new_prog == SAMPLE_PROGRAM


def test_apply_ambiguous_match():
    # Code with duplicated line
    ambiguous_prog = "VAL = 1.0\nVAL = 1.0\n"
    patch = """<<<<<<< SEARCH
VAL = 1.0
=======
VAL = 2.0
>>>>>>> REPLACE"""
    new_prog, status = apply_patch(ambiguous_prog, patch)
    assert status == STATUS_AMBIGUOUS
    assert new_prog == ambiguous_prog


def test_apply_malformed_patch():
    # Missing REPLACE marker
    patch = """<<<<<<< SEARCH
HOLE_DIA = 6.0
=======
HOLE_DIA = 10.0"""
    new_prog, status = apply_patch(SAMPLE_PROGRAM, patch)
    assert status == STATUS_MALFORMED

    # Empty search block
    patch2 = """<<<<<<< SEARCH
=======
HOLE_DIA = 10.0
>>>>>>> REPLACE"""
    new_prog2, status2 = apply_patch(SAMPLE_PROGRAM, patch2)
    assert status2 == STATUS_MALFORMED


def test_make_patch_roundtrip():
    patch = make_patch(SAMPLE_PROGRAM, SAMPLE_EDITED_PROGRAM)
    assert patch != ""
    assert "<<<<<<< SEARCH" in patch
    assert ">>>>>>> REPLACE" in patch
    
    reconstructed, status = apply_patch(SAMPLE_PROGRAM, patch)
    assert status == STATUS_SUCCESS
    assert reconstructed.strip() == SAMPLE_EDITED_PROGRAM.strip()


def test_make_patch_identical_programs():
    patch = make_patch(SAMPLE_PROGRAM, SAMPLE_PROGRAM)
    assert patch == ""
