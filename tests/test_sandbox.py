import pytest
from cadpatch.sandbox import (
    execute_cadquery_sandbox,
    STATUS_SUCCESS,
    STATUS_SECURITY_VIOLATION,
    STATUS_TIMEOUT,
    STATUS_SYNTAX_ERROR,
    STATUS_INVALID_GEOMETRY,
)

VALID_CADQUERY_SCRIPT = """import cadquery as cq

LENGTH = 40.0
WIDTH = 25.0
HEIGHT = 10.0
HOLE_DIA = 6.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIA)
)
"""


def test_sandbox_smoke_test_box_hole():
    """Builds a box with a through hole and validates volume and STL export."""
    res = execute_cadquery_sandbox(VALID_CADQUERY_SCRIPT, timeout=10.0)
    assert res["status"] == STATUS_SUCCESS
    assert res["volume"] > 0
    # Expected volume: (40 * 25 * 10) - (pi * 3^2 * 10) ≈ 10000 - 282.74 ≈ 9717.26
    assert 9000 < res["volume"] < 10000
    assert res["bbox"] is not None
    assert "stl_bytes" in res
    assert len(res["stl_bytes"]) > 0


def test_sandbox_security_import_os():
    """Malicious code attempting to import os is intercepted statically."""
    bad_code = "import os\nos.system('dir')"
    res = execute_cadquery_sandbox(bad_code)
    assert res["status"] == STATUS_SECURITY_VIOLATION
    assert "Security Violation" in res["error"]


def test_sandbox_security_import_subprocess():
    """Attempting to import subprocess is intercepted."""
    bad_code = "import subprocess\nsubprocess.run(['ls'])"
    res = execute_cadquery_sandbox(bad_code)
    assert res["status"] == STATUS_SECURITY_VIOLATION


def test_sandbox_security_eval():
    """Attempting to invoke eval is intercepted statically."""
    bad_code = "eval('1 + 1')"
    res = execute_cadquery_sandbox(bad_code)
    assert res["status"] == STATUS_SECURITY_VIOLATION


def test_sandbox_security_subclasses():
    """Attempting dunder attribute exploitation is intercepted."""
    bad_code = "x = ().__class__.__subclasses__()"
    res = execute_cadquery_sandbox(bad_code)
    assert res["status"] == STATUS_SECURITY_VIOLATION


def test_sandbox_timeout_infinite_loop():
    """An infinite loop triggers timeout containment."""
    loop_code = "while True:\n    pass"
    res = execute_cadquery_sandbox(loop_code, timeout=2.0)
    assert res["status"] == STATUS_TIMEOUT
    assert "timed out" in res["error"]


def test_sandbox_syntax_error():
    """Syntax error is caught gracefully."""
    bad_syntax = "def broken(:\n    pass"
    res = execute_cadquery_sandbox(bad_syntax)
    assert res["status"] == STATUS_SYNTAX_ERROR


def test_sandbox_missing_result():
    """Script without 'result' defined fails validation."""
    no_result = "x = 10\ny = 20"
    res = execute_cadquery_sandbox(no_result)
    assert res["status"] == STATUS_INVALID_GEOMETRY
