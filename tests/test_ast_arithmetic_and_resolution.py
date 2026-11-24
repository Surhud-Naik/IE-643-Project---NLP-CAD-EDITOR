import pytest
import torch
from cadpatch.patching.expr import (
    safe_eval_arithmetic,
    extract_numeric_expressions,
    resolve_parameter_target,
    resolve_instruction_edits,
)
from cadpatch.models.inference import resolve_device_and_dtype, empty_device_cache
from cadpatch.web.model_service import MockModelBackend
from cadpatch.demo.app import predict_cad_patch


SAMPLE_CAD_SCRIPT = """import cadquery as cq

LENGTH = 60.0
WIDTH = 40.0
HEIGHT = 15.0
HOLE_DIA = 6.0
THICKNESS = 10.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIA)
)
"""


class TestSafeEvalArithmetic:
    def test_basic_operations(self):
        assert safe_eval_arithmetic("10/2") == 5.0
        assert safe_eval_arithmetic("20 / 4") == 5.0
        assert safe_eval_arithmetic("4 * 2") == 8.0
        assert safe_eval_arithmetic("12 - 4") == 8.0
        assert safe_eval_arithmetic("6 + 3.5") == 9.5
        assert safe_eval_arithmetic("15 // 2") == 7.0
        assert safe_eval_arithmetic("15 % 4") == 3.0
        assert safe_eval_arithmetic("2 ** 3") == 8.0

    def test_unary_and_constants(self):
        assert safe_eval_arithmetic("-10.5") == -10.5
        assert safe_eval_arithmetic("+5") == 5.0
        assert safe_eval_arithmetic("42") == 42.0

    def test_zero_division_and_bounds(self):
        assert safe_eval_arithmetic("10 / 0") is None
        assert safe_eval_arithmetic("10 // 0") is None
        assert safe_eval_arithmetic("10 % 0") is None
        assert safe_eval_arithmetic("2 ** 100") is None

    def test_security_rejections(self):
        assert safe_eval_arithmetic("__import__('os')") is None
        assert safe_eval_arithmetic("eval('1+1')") is None
        assert safe_eval_arithmetic("open('file.txt')") is None
        assert safe_eval_arithmetic("[1, 2, 3]") is None
        assert safe_eval_arithmetic("x = 10") is None
        assert safe_eval_arithmetic("") is None
        assert safe_eval_arithmetic(None) is None


class TestParameterResolution:
    def test_widen_does_not_collide_with_hole(self):
        params = {"LENGTH": 60.0, "WIDTH": 40.0, "HEIGHT": 15.0, "HOLE_DIA": 6.0}
        target = resolve_parameter_target("widen the plate by 5 mm", params)
        assert target == "WIDTH"

    def test_hole_widen_resolves_to_hole(self):
        params = {"LENGTH": 60.0, "WIDTH": 40.0, "HEIGHT": 15.0, "HOLE_DIA": 6.0}
        target = resolve_parameter_target("widen the hole by 2 mm", params)
        assert target == "HOLE_DIA"

    def test_height_and_thickness(self):
        params = {"LENGTH": 60.0, "WIDTH": 40.0, "HEIGHT": 15.0}
        assert resolve_parameter_target("increase the height by 10/2", params) == "HEIGHT"

        params_thick = {"LENGTH": 60.0, "WIDTH": 40.0, "THICKNESS": 10.0}
        assert resolve_parameter_target("set thickness to 20/4", params_thick) == "THICKNESS"

    def test_unresolved_returns_none(self):
        params = {"LENGTH": 60.0, "WIDTH": 40.0, "HEIGHT": 15.0}
        assert resolve_parameter_target("change the color to blue", params) is None


class TestResolveInstructionEdits:
    def test_arithmetic_expression_height(self):
        res = resolve_instruction_edits(SAMPLE_CAD_SCRIPT, "increase the height by 10/2")
        assert res["success"] is True
        assert res["updates"]["HEIGHT"] == 20.0  # 15.0 + 5.0
        assert "HEIGHT = 20.0" in res["edited_script"]

    def test_widen_plate(self):
        res = resolve_instruction_edits(SAMPLE_CAD_SCRIPT, "widen the plate by 5 mm")
        assert res["success"] is True
        assert res["updates"]["WIDTH"] == 45.0  # 40.0 + 5.0
        assert "WIDTH = 45.0" in res["edited_script"]
        # Must NOT touch HOLE_DIA
        assert "HOLE_DIA" not in res["updates"]

    def test_set_thickness_absolute(self):
        res = resolve_instruction_edits(SAMPLE_CAD_SCRIPT, "set thickness to 20/4")
        assert res["success"] is True
        assert res["updates"]["THICKNESS"] == 5.0
        assert "THICKNESS = 5.0" in res["edited_script"]

    def test_multi_clause_instruction(self):
        res = resolve_instruction_edits(
            SAMPLE_CAD_SCRIPT,
            "increase length by 10/2 and reduce thickness by 2"
        )
        assert res["success"] is True
        assert res["updates"]["LENGTH"] == 65.0  # 60.0 + 5.0
        assert res["updates"]["THICKNESS"] == 8.0  # 10.0 - 2.0
        assert "LENGTH = 65.0" in res["edited_script"]
        assert "THICKNESS = 8.0" in res["edited_script"]
        assert "<<<<<<< SEARCH" in res["patch"]

    def test_unresolved_does_not_modify(self):
        res = resolve_instruction_edits(SAMPLE_CAD_SCRIPT, "repaint all faces blue")
        assert res["success"] is False
        assert len(res["updates"]) == 0
        assert res["patch"] == ""


class TestMockModelBackendAndDemo:
    def test_backend_with_arithmetic_instruction(self):
        backend = MockModelBackend()
        patch, raw = backend.generate(SAMPLE_CAD_SCRIPT, "increase the height by 10/2")
        assert "<<<<<<< SEARCH" in patch
        assert "HEIGHT = 15.0" in patch
        assert "HEIGHT = 20.0" in patch

    def test_backend_widen_plate(self):
        backend = MockModelBackend()
        patch, raw = backend.generate(SAMPLE_CAD_SCRIPT, "widen the plate by 5 mm")
        assert "WIDTH = 40.0" in patch
        assert "WIDTH = 45.0" in patch
        assert "HOLE_DIA" not in patch

    def test_demo_predict_cad_patch_with_expression(self):
        patch, applied, orig_img, edit_img, metrics = predict_cad_patch(
            SAMPLE_CAD_SCRIPT,
            "increase the height by 10/2"
        )
        assert "SUCCESS" in metrics or "Valid" in metrics
        assert "HEIGHT = 20.0" in applied


class TestDeviceResolution:
    def test_cpu_device(self):
        dev, dt = resolve_device_and_dtype("cpu")
        assert dev.type == "cpu"
        assert dt == torch.float32

    def test_auto_device(self):
        dev, dt = resolve_device_and_dtype("auto")
        assert dev.type in ("cuda", "mps", "cpu")
        if dev.type == "cuda":
            assert dt == torch.float16
        elif dev.type == "mps":
            assert dt == torch.bfloat16
        else:
            assert dt == torch.float32

    def test_empty_cache_callable(self):
        dev, _ = resolve_device_and_dtype("cpu")
        empty_device_cache(dev)
