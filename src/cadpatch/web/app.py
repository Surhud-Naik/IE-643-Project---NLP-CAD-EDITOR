"""
FastAPI application for CAD Patch Editor.
Exposes REST and SSE endpoints for parametric CAD editing, validation, and artifact retrieval.
"""

from typing import Dict, Any, Optional
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status, Path
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import WebConfig, load_web_config
from .schemas import (
    EditRequest, ValidateRequest, ValidateResponse, JobStatusResponse,
    ConfigResponse, BoundingBoxInfo
)
from .security import RateLimiter, get_client_ip, validate_script_security
from .geometry_service import GeometryService
from .model_service import ModelBackend, MockModelBackend, AsyncModelQueue
from .jobs import JobManager, JobStatus
from .examples import get_examples
from ..sandbox.executor import STATUS_SUCCESS, static_security_check


def create_app(
    config: Optional[WebConfig] = None,
    backend_override: Optional[ModelBackend] = None
) -> FastAPI:
    if config is None:
        config = load_web_config()

    # Initialize model backend
    if backend_override is not None:
        model_backend = backend_override
    elif config.model_backend == "mock":
        model_backend = MockModelBackend()
    else:
        # local_peft or merged_model (Phase W2 imports)
        from .model_service_peft import create_peft_backend
        model_backend = create_peft_backend(config)

    geometry_service = GeometryService(
        timeout=config.sandbox_timeout,
        enable_cache=config.cache_geometry
    )
    model_queue = AsyncModelQueue(model_backend)
    job_manager = JobManager(
        geometry_service=geometry_service,
        model_queue=model_queue,
        artifact_dir=config.artifact_dir,
        ttl_seconds=config.ttl_seconds
    )
    rate_limiter = RateLimiter(
        max_requests=config.rate_limit_per_minute,
        window_seconds=60.0
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await model_queue.start()
        await job_manager.start()
        yield
        # Shutdown
        await job_manager.stop()
        await model_queue.stop()

    app = FastAPI(
        title="CAD Patch Editor API",
        description="Learning to Edit Parametric CAD Programs from Natural-Language Instructions",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach instances to app state
    app.state.config = config
    app.state.job_manager = job_manager
    app.state.geometry_service = geometry_service
    app.state.rate_limiter = rate_limiter

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "timestamp": time.time(),
            "model_backend": config.model_backend,
            "jobs_active": len(job_manager.jobs)
        }

    @app.get("/api/config", response_model=ConfigResponse)
    async def get_config():
        has_full_regen = os.path.exists(config.full_regen_adapter_path)
        available_modes = ["patch"]
        if has_full_regen or config.model_backend == "mock":
            available_modes.append("full_regen")

        return ConfigResponse(
            model_backend=config.model_backend,
            base_model=config.base_model,
            available_modes=available_modes,
            has_full_regen_adapter=has_full_regen,
            has_locate_infill_adapter=False,
            max_script_bytes=config.max_script_bytes,
            max_instruction_chars=config.max_instruction_chars,
            timeout_seconds=config.sandbox_timeout
        )

    @app.get("/api/examples")
    async def examples():
        return get_examples()

    @app.post("/api/validate", response_model=ValidateResponse)
    async def validate_script(req: ValidateRequest):
        # 1. Check size limit
        if len(req.script.encode("utf-8")) > config.max_script_bytes:
            return ValidateResponse(
                valid=False,
                status="SIZE_EXCEEDED",
                error=f"Script size exceeds {config.max_script_bytes} bytes.",
                duration=0.0
            )

        # 2. AST security & syntax check
        violation = static_security_check(req.script)
        if violation:
            status_name = "SECURITY_VIOLATION" if "Security Violation" in violation else "SYNTAX_ERROR"
            return ValidateResponse(
                valid=False,
                status=status_name,
                error=violation,
                duration=0.0
            )

        # 3. Dry run in sandbox
        res = geometry_service.execute_script(req.script, export_all=False)
        is_valid = (res.get("status") == STATUS_SUCCESS)
        bbox = None
        if is_valid and res.get("bbox"):
            b = res["bbox"]
            bbox = BoundingBoxInfo(**b)

        return ValidateResponse(
            valid=is_valid,
            status=res.get("status", "UNKNOWN"),
            error=res.get("error"),
            volume=res.get("volume"),
            bbox=bbox,
            duration=res.get("duration", 0.0)
        )

    @app.post("/api/edit")
    async def create_edit_job(req: EditRequest, request: Request):
        # Rate limit check
        client_ip = get_client_ip(request)
        allowed, remaining = rate_limiter.check(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded (max {config.rate_limit_per_minute} requests/minute). Please wait."
            )

        # Input constraints
        if len(req.script.encode("utf-8")) > config.max_script_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Script size exceeds {config.max_script_bytes} bytes limit."
            )

        if len(req.instruction) > config.max_instruction_chars:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Instruction exceeds {config.max_instruction_chars} characters limit."
            )

        # Queue capacity check
        if len(job_manager.jobs) >= config.max_queue_size:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server processing queue is full. Please try again in a few moments."
            )

        # Security check
        validate_script_security(req.script, max_bytes=config.max_script_bytes)

        # Create and enqueue job
        job = job_manager.create_job(
            script=req.script,
            instruction=req.instruction,
            mode=req.mode,
            retry_count=req.retry_count,
            temperature=req.temperature
        )

        return {"job_id": job.job_id, "status": job.status.value}

    @app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(job_id: str):
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found."
            )

        q_pos = model_queue.get_queue_position(job_id)
        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            queue_position=q_pos,
            current_attempt=job.current_attempt,
            max_attempts=job.retry_count,
            message=job.message,
            result=job.result
        )

    @app.get("/api/jobs/{job_id}/events")
    async def stream_job_events(job_id: str):
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found."
            )

        return StreamingResponse(
            job_manager.subscribe(job_id),
            media_type="text/event-stream"
        )

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        success = job_manager.cancel_job(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job cannot be cancelled (it may have already finished or does not exist)."
            )
        return {"status": "CANCELLED", "job_id": job_id}

    @app.get("/api/jobs/{job_id}/download/{kind}")
    async def download_artifact(
        job_id: str,
        kind: str = Path(..., pattern="^(py|patch|stl|step|glb|original_glb)$")
    ):
        job_dir = os.path.join(config.artifact_dir, job_id)
        if not os.path.exists(job_dir):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job artifact folder not found."
            )

        file_map = {
            "py": ("model_edited.py", "text/x-python", "edited_model.py"),
            "patch": ("patch.diff", "text/plain", "patch.diff"),
            "stl": ("model.stl", "application/sla", "model.stl"),
            "step": ("model.step", "model/step", "model.step"),
            "glb": ("model.glb", "model/gltf-binary", "model.glb"),
            "original_glb": ("original.glb", "model/gltf-binary", "original.glb")
        }

        filename, media_type, download_name = file_map[kind]
        filepath = os.path.join(job_dir, filename)

        if not os.path.exists(filepath):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{kind}' is not available for this job."
            )

        return FileResponse(
            path=filepath,
            media_type=media_type,
            filename=download_name
        )

    # Mount static frontend build if present
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dist_dir = os.path.join(repo_root, "web", "dist")
    if os.path.exists(dist_dir):
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

    return app


# Module-level app instance for uvicorn
app = create_app()
