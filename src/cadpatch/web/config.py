"""
Web configuration manager for CAD Patch Editor.
"""

from typing import Dict, Any, List
import os
import yaml


class WebConfig:
    def __init__(self, config_dict: Dict[str, Any]):
        self.raw = config_dict
        server = config_dict.get("server", {})
        self.host: str = server.get("host", "0.0.0.0")
        self.port: int = int(server.get("port", 8000))
        self.cors_origins: List[str] = server.get("cors_origins", ["*"])

        model = config_dict.get("model", {})
        self.model_backend: str = os.environ.get("CADPATCH_MODEL_BACKEND", model.get("backend", "mock"))
        self.base_model: str = model.get("base_model", "Qwen/Qwen2.5-Coder-0.5B-Instruct")
        self.adapter_path: str = model.get("adapter_path", "outputs/checkpoints/patch_model")
        self.full_regen_adapter_path: str = model.get("full_regen_adapter_path", "outputs/checkpoints/full_model")
        self.load_in_4bit: bool = bool(model.get("load_in_4bit", False))
        self.device: str = model.get("device", "auto")
        self.max_new_tokens: int = int(model.get("max_new_tokens", 256))
        self.retry_count: int = int(model.get("retry_count", 3))
        self.temperature: float = float(model.get("temperature", 0.2))

        security = config_dict.get("security", {})
        self.max_script_bytes: int = int(security.get("max_script_bytes", 20480))
        self.max_instruction_chars: int = int(security.get("max_instruction_chars", 500))
        self.sandbox_timeout: float = float(security.get("sandbox_timeout_seconds", 15.0))
        self.rate_limit_per_minute: int = int(security.get("rate_limit_per_minute", 10))
        self.max_queue_size: int = int(security.get("max_queue_size", 50))

        storage = config_dict.get("storage", {})
        self.artifact_dir: str = storage.get("artifact_dir", "outputs/web_jobs")
        self.ttl_seconds: int = int(storage.get("ttl_seconds", 3600))
        self.cache_geometry: bool = bool(storage.get("cache_geometry", True))


def load_web_config(config_path: str = "configs/web.yaml") -> WebConfig:
    if not os.path.exists(config_path):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        alt_path = os.path.join(repo_root, config_path)
        if os.path.exists(alt_path):
            config_path = alt_path

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    return WebConfig(data)
