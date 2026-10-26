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


def test_sandbox_execution():
    res = execute_cadquery_sandbox(VALID_CADQUERY_SCRIPT, timeout=10.0)
    assert res["status"] == STATUS_SUCCESS
    assert 9000 < res["volume"] < 10000
    assert res["bbox"] is not None
    assert "stl_bytes" in res and len(res["stl_bytes"]) > 0


@pytest.mark.parametrize("bad_code", [
    "import os\nos.system('dir')",
    "import subprocess\nsubprocess.run(['ls'])",
    "eval('1 + 1')",
    "x = ().__class__.__subclasses__()",
])
def test_sandbox_security(bad_code):
    res = execute_cadquery_sandbox(bad_code)
    assert res["status"] == STATUS_SECURITY_VIOLATION


def test_sandbox_timeout():
    res = execute_cadquery_sandbox("while True: pass", timeout=2.0)
    assert res["status"] == STATUS_TIMEOUT


def test_sandbox_errors():
    res_syntax = execute_cadquery_sandbox("def broken(: pass")
    assert res_syntax["status"] == STATUS_SYNTAX_ERROR

    res_missing = execute_cadquery_sandbox("x = 10\ny = 20")
    assert res_missing["status"] == STATUS_INVALID_GEOMETRY
