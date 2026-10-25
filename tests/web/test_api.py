"""
Comprehensive unit and integration tests for CAD Patch Editor Web API.
Covers: health/config, validation, happy path, pre-flight failures, retry-success,
patch failure, malicious inputs, oversize inputs, rate limiting, and artifact downloads.
"""

import time
import pytest
from fastapi.testclient import TestClient

from cadpatch.web.config import WebConfig
from cadpatch.web.app import create_app
from cadpatch.web.model_service import MockModelBackend

VALID_BOX_SCRIPT = """import cadquery as cq

LENGTH = 40.0
WIDTH = 30.0
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

BROKEN_SCRIPT = """import cadquery as cq

LENGTH = 40.0
WIDTH = 30.0
HEIGHT = 10.0

# Broken geometry - hollow with thickness larger than dimensions
result = cq.Workplane("XY").box(LENGTH, WIDTH, HEIGHT).shell(-100.0)
"""


@pytest.fixture
def client(tmp_path):
    """Creates a test client with a mock backend and isolated temp artifact dir."""
    config_dict = {
        "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
        "model": {"backend": "mock", "retry_count": 3, "temperature": 0.2},
        "security": {
            "max_script_bytes": 20480,
            "max_instruction_chars": 500,
            "sandbox_timeout_seconds": 15.0,
            "rate_limit_per_minute": 10,
            "max_queue_size": 20
        },
        "storage": {
            "artifact_dir": str(tmp_path / "web_artifacts"),
            "ttl_seconds": 3600,
            "cache_geometry": True
        }
    }
    cfg = WebConfig(config_dict)
    app = create_app(config=cfg, backend_override=MockModelBackend())
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_config(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["model_backend"] == "mock"

    cfg_res = client.get("/api/config")
    assert cfg_res.status_code == 200
    cfg = cfg_res.json()
    assert "patch" in cfg["available_modes"]
    assert cfg["max_script_bytes"] == 20480
    assert cfg["max_instruction_chars"] == 500


def test_examples_endpoint(client):
    res = client.get("/api/examples")
    assert res.status_code == 200
    examples = res.json()
    assert len(examples) >= 6
    assert all("id" in ex and "script" in ex and "instruction" in ex for ex in examples)


def test_validate_script_success(client):
    res = client.post("/api/validate", json={"script": VALID_BOX_SCRIPT})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["volume"] > 0
    assert data["bbox"] is not None


def test_validate_script_syntax_error(client):
    bad_code = "import cadquery as cq\ndef invalid_syntax"
    res = client.post("/api/validate", json={"script": bad_code})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert "SyntaxError" in data["error"] or data["status"] == "SYNTAX_ERROR"


def test_validate_script_security_violation(client):
    malicious = "import os\nos.system('dir')"
    res = client.post("/api/validate", json={"script": malicious})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert data["status"] == "SECURITY_VIOLATION"
    assert "Security Violation" in data["error"]


def test_edit_happy_path_and_downloads(client):
    # 1. Submit edit request
    req = {
        "script": VALID_BOX_SCRIPT,
        "instruction": "Widen the mounting hole by 2 mm",
        "mode": "patch",
        "retry_count": 3
    }
    submit_res = client.post("/api/edit", json=req)
    assert submit_res.status_code == 200
    job_id = submit_res.json()["job_id"]

    # 2. Poll until completed (timeout 25s)
    completed = False
    data = None
    for _ in range(50):
        time.sleep(0.5)
        status_res = client.get(f"/api/jobs/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        if data["status"] in ["COMPLETED", "FAILED"]:
            completed = True
            break

    assert completed is True
    assert data["status"] == "COMPLETED"
    result = data["result"]
    assert result is not None
    assert result["attempts_used"] == 1
    assert "HOLE_DIA" in result["patch_text"]

    # Verify change summary
    change = result["change_summary"]
    assert change["lines_touched"] > 0
    assert any(p["name"] == "HOLE_DIA" for p in change["parameters_changed"])
    assert change["token_savings_pct"] > 0

    # Verify metrics
    metrics = result["metrics"]
    assert metrics["validity"] is True
    assert metrics["edited_volume"] < metrics["original_volume"]  # Bigger hole = smaller solid
    assert metrics["chamfer_distance_relative"] >= 0.0

    # 3. Test downloads of all formats
    for kind in ["py", "patch", "stl", "step", "glb", "original_glb"]:
        dl_res = client.get(f"/api/jobs/{job_id}/download/{kind}")
        assert dl_res.status_code == 200, f"Download failed for kind {kind}: {dl_res.text}"
        assert len(dl_res.content) > 0, f"Empty artifact for kind {kind}"


def test_original_script_fails_preflight(client):
    # Submitting broken script should fail before calling the model
    req = {
        "script": BROKEN_SCRIPT,
        "instruction": "Widen the mounting hole by 2 mm",
        "mode": "patch"
    }
    submit_res = client.post("/api/edit", json=req)
    assert submit_res.status_code == 200
    job_id = submit_res.json()["job_id"]

    # Poll until failure
    for _ in range(30):
        time.sleep(0.5)
        status_res = client.get(f"/api/jobs/{job_id}")
        data = status_res.json()
        if data["status"] in ["FAILED", "COMPLETED"]:
            break

    assert data["status"] == "FAILED"
    assert "Pre-flight verification failed" in data["message"] or (data["result"] and "Pre-flight" in str(data["result"]))


def test_patch_fails_then_retry_succeeds(client):
    req = {
        "script": VALID_BOX_SCRIPT,
        "instruction": "Widen hole simulate_retry_success by 2 mm",
        "mode": "patch",
        "retry_count": 3
    }
    submit_res = client.post("/api/edit", json=req)
    assert submit_res.status_code == 200
    job_id = submit_res.json()["job_id"]

    for _ in range(40):
        time.sleep(0.5)
        status_res = client.get(f"/api/jobs/{job_id}")
        data = status_res.json()
        if data["status"] in ["COMPLETED", "FAILED"]:
            break

    assert data["status"] == "COMPLETED"
    assert data["result"]["attempts_used"] == 2


def test_patch_never_applies(client):
    req = {
        "script": VALID_BOX_SCRIPT,
        "instruction": "Widen hole simulate_no_match by 2 mm",
        "mode": "patch",
        "retry_count": 2
    }
    submit_res = client.post("/api/edit", json=req)
    assert submit_res.status_code == 200
    job_id = submit_res.json()["job_id"]

    for _ in range(40):
        time.sleep(0.5)
        status_res = client.get(f"/api/jobs/{job_id}")
        data = status_res.json()
        if data["status"] in ["COMPLETED", "FAILED"]:
            break

    assert data["status"] == "FAILED"
    assert "non-applicable patch" in data["message"] or "non-applicable patch" in str(status_res.json())


def test_malicious_script_rejected_at_endpoint(client):
    bad_req = {
        "script": "import subprocess\nsubprocess.run(['ls'])",
        "instruction": "Widen hole"
    }
    res = client.post("/api/edit", json=bad_req)
    assert res.status_code == 400
    assert "Security Policy Violation" in res.json()["detail"]


def test_oversize_script_rejected(client):
    huge_script = VALID_BOX_SCRIPT + "\n# " + ("A" * 25000)
    res = client.post("/api/edit", json={"script": huge_script, "instruction": "Widen hole"})
    assert res.status_code in [413, 422]


def test_oversize_instruction_rejected(client):
    huge_inst = "Widen hole " + ("x" * 600)
    res = client.post("/api/edit", json={"script": VALID_BOX_SCRIPT, "instruction": huge_inst})
    assert res.status_code in [400, 422]


def test_rate_limiting(tmp_path):
    # Configure strict rate limit of 2 requests/minute
    config_dict = {
        "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
        "model": {"backend": "mock", "retry_count": 1},
        "security": {
            "max_script_bytes": 20480,
            "max_instruction_chars": 500,
            "sandbox_timeout_seconds": 15.0,
            "rate_limit_per_minute": 2,
            "max_queue_size": 20
        },
        "storage": {
            "artifact_dir": str(tmp_path / "web_artifacts"),
            "ttl_seconds": 3600
        }
    }
    cfg = WebConfig(config_dict)
    app = create_app(config=cfg, backend_override=MockModelBackend())
    client = TestClient(app)

    req = {"script": VALID_BOX_SCRIPT, "instruction": "Widen hole"}
    # Req 1: ok
    r1 = client.post("/api/edit", json=req)
    assert r1.status_code == 200
    # Req 2: ok
    r2 = client.post("/api/edit", json=req)
    assert r2.status_code == 200
    # Req 3: rate limited
    r3 = client.post("/api/edit", json=req)
    assert r3.status_code == 429
    assert "Rate limit exceeded" in r3.json()["detail"]


def test_job_cancel(client):
    req = {
        "script": VALID_BOX_SCRIPT,
        "instruction": "Widen the hole by 2 mm"
    }
    submit_res = client.post("/api/edit", json=req)
    assert submit_res.status_code == 200
    job_id = submit_res.json()["job_id"]

    # Cancel immediately
    cancel_res = client.post(f"/api/jobs/{job_id}/cancel")
    # Might succeed or already be processing
    assert cancel_res.status_code in [200, 400]
