import pytest
import os
import trimesh
from cadpatch.demo import build_demo_app, predict_cad_patch, render_stl_to_image, EXAMPLES


def test_renderer_creates_png(tmp_path):
    mesh = trimesh.creation.box((20.0, 20.0, 10.0))
    stl_bytes = mesh.export(file_type="stl")
    out_img = os.path.join(str(tmp_path), "test_render.png")

    res_path = render_stl_to_image(stl_bytes, output_path=out_img)
    assert os.path.exists(res_path)
    assert os.path.getsize(res_path) > 1000


def test_predict_cad_patch_example():
    code, instruction = EXAMPLES[0]
    patch, edited_code, orig_img, edited_img, metrics = predict_cad_patch(code, instruction)

    assert "<<<<<<< SEARCH" in patch
    assert ">>>>>>> REPLACE" in patch
    assert len(edited_code) > 0
    assert orig_img is not None and os.path.exists(orig_img)
    assert edited_img is not None and os.path.exists(edited_img)
    assert "Patch Status" in metrics
    assert "SUCCESS" in metrics


def test_build_demo_app():
    demo = build_demo_app()
    assert demo is not None
