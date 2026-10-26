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


@pytest.fixture
def client(tmp_path):
    cfg = WebConfig({
        "server": {"host": "127.0.0.1", "port": 8000, "cors_origins": ["*"]},
        "model": {"backend": "mock", "retry_count": 2, "temperature": 0.2},
        "security": {
            "max_script_bytes": 20480,
            "max_instruction_chars": 500,
            "sandbox_timeout_seconds": 15.0,
            "rate_limit_per_minute": 20,
            "max_queue_size": 10
        },
        "storage": {
            "artifact_dir": str(tmp_path / "web_artifacts"),
            "ttl_seconds": 3600,
            "cache_geometry": True
        }
    })
    app = create_app(config=cfg, backend_override=MockModelBackend())
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_config(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    cfg_res = client.get("/api/config")
    assert cfg_res.status_code == 200
    assert "patch" in cfg_res.json()["available_modes"]


def test_examples_endpoint(client):
    res = client.get("/api/examples")
    assert res.status_code == 200
    examples = res.json()
    assert len(examples) >= 4
    assert all("id" in ex and "script" in ex for ex in examples)


def test_validate_script(client):
    ok_res = client.post("/api/validate", json={"script": VALID_BOX_SCRIPT})
    assert ok_res.status_code == 200
    assert ok_res.json()["valid"] is True

    bad_syntax = client.post("/api/validate", json={"script": "import cadquery\ndef ("})
    assert bad_syntax.status_code == 200
    assert bad_syntax.json()["valid"] is False

    malicious = client.post("/api/validate", json={"script": "import os\nos.system('dir')"})
    assert malicious.status_code == 200
    assert malicious.json()["valid"] is False
    assert malicious.json()["status"] == "SECURITY_VIOLATION"


def test_edit_happy_path_and_downloads(client):
    req = {
        "script": VALID_BOX_SCRIPT,
        "instruction": "Widen the mounting hole by 2 mm",
        "mode": "patch",
        "retry_count": 2
    }
    submit_res = client.post("/api/edit", json=req)
    assert submit_res.status_code == 200
    job_id = submit_res.json()["job_id"]

    data = None
    for _ in range(30):
        time.sleep(0.3)
        status_res = client.get(f"/api/jobs/{job_id}")
        data = status_res.json()
        if data["status"] in ["COMPLETED", "FAILED"]:
            break

    assert data["status"] == "COMPLETED"
    result = data["result"]
    assert "HOLE_DIA" in result["patch_text"]
    assert result["metrics"]["validity"] is True

    for kind in ["py", "patch", "stl", "step", "glb"]:
        dl_res = client.get(f"/api/jobs/{job_id}/download/{kind}")
        assert dl_res.status_code == 200
        assert len(dl_res.content) > 0


def test_rate_limiting(tmp_path):
    cfg = WebConfig({
        "server": {"host": "127.0.0.1", "port": 8000},
        "model": {"backend": "mock"},
        "security": {"rate_limit_per_minute": 2},
        "storage": {"artifact_dir": str(tmp_path / "web_artifacts")}
    })
    app = create_app(config=cfg, backend_override=MockModelBackend())
    client = TestClient(app)

    req = {"script": VALID_BOX_SCRIPT, "instruction": "Widen hole"}
    assert client.post("/api/edit", json=req).status_code == 200
    assert client.post("/api/edit", json=req).status_code == 200
    assert client.post("/api/edit", json=req).status_code == 429
