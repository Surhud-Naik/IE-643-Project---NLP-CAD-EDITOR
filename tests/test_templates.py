import pytest
import random
from cadpatch.templates import ALL_TEMPLATES
from cadpatch.sandbox import execute_cadquery_sandbox, STATUS_SUCCESS


@pytest.mark.parametrize("template", ALL_TEMPLATES, ids=[t.name for t in ALL_TEMPLATES])
def test_template_instantiation_and_execution(template):
    rng = random.Random(123)
    params = template.sample_valid_params(rng)
    assert template.constraints_fn(params) is True

    code = template.render(params)
    assert "import cadquery as cq" in code
    assert "result =" in code

    res = execute_cadquery_sandbox(code, timeout=20.0)
    assert res["status"] == STATUS_SUCCESS, f"Template {template.name} failed: {res.get('error')}"
    assert res["volume"] > 0
    assert res["bbox"] is not None
    assert "stl_bytes" in res
