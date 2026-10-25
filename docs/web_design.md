# CAD Patch Editor - Production Web Architecture & Design

## 1. System Overview & Findings
The repository provides an end-to-end framework for editing parametric CadQuery Python models from natural-language instructions using code-patch prediction:
- `src/cadpatch/patching`: Robust search/replace patch generator and applier (`apply_patch`, `make_patch`) with strict match constraints.
- `src/cadpatch/sandbox`: Multi-layered sandbox (`execute_cadquery_sandbox` and `CadQueryDaemonSandbox`) enforcing static AST security (disallowing arbitrary imports and dangerous dunder attributes) and isolated subprocess execution.
- `src/cadpatch/templates`: 10 parametric templates spanning multiple mechanical operations (box, bushing, patterned plate, filleted/chamfered blocks, bracket, flange, shelled box, slot, pulley).
- `src/cadpatch/eval`: Exact match, AST parameter diffing, unintended change rate, Levenshtein edit distance, 3D point cloud Chamfer distance, and volumetric IoU.
- `src/cadpatch/models`: LoRA inference and training with completion-only loss masking.

The goal of this phase is to construct an enterprise-grade, responsive, and secure web application allowing users to input CadQuery scripts (paste, upload, or example), submit natural-language instructions, track live SSE execution progress, inspect before/after 3D models with interactive orbit controls and overlay modes, review code diffs, verify metrics, download output formats (`.py`, `.patch`, `.stl`, `.step`, `.glb`), and chain iterative edits with session history.

---

## 2. High-Level Architecture Diagram
```
+---------------------------------------------------------------------------------------+
|                                    Browser Client                                     |
|  - React + Vite + TypeScript + Tailwind                                               |
|  - Monaco / Code Editor & Syntax Highlighted Diff Viewer                              |
|  - Synchronized Three.js 3D Viewers (Shaded, Wireframe, Translucent Overlay, Slider)  |
|  - SSE EventSource (/api/jobs/{id}/events) for real-time progress                     |
|  - History & Iterative Chaining Manager                                               |
+-------------------------------------------+-------------------------------------------+
                                            | HTTP / SSE
                                            v
+---------------------------------------------------------------------------------------+
|                                  FastAPI Backend                                      |
|  - Security Middleware: AST Sanitizer, Input Caps (20KB / 500 chars), Rate Limiter    |
|  - Endpoints: /api/edit, /api/jobs/{id}, /api/jobs/{id}/events, /api/jobs/{id}/download|
|  - Single-Worker Inference Queue (Prevents GPU OOM)                                   |
|  - Pluggable Model Backends: 'mock', 'local_peft', 'merged_model'                    |
|  - CadQuery Sandbox & Exporter (STL, STEP, GLB via Trimesh)                           |
|  - Job Artifact Store with TTL Cleanup (1h) & Geometry Hash Cache                     |
+---------------------------------------------------------------------------------------+
```

---

## 3. Phase Plans

### Phase W1: Backend Foundation
- **Plan**: Implement `configs/web.yaml`, Pydantic request/response models (`src/cadpatch/web/schemas.py`), job queue and state manager (`src/cadpatch/web/jobs.py`), mock model backend (`src/cadpatch/web/model_service.py`), sandboxed geometry exporter supporting STL/STEP/GLB with content caching (`src/cadpatch/web/geometry_service.py`), and FastAPI routes (`src/cadpatch/web/app.py`). Write and pass `tests/web/test_api.py`.
- **Acceptance Results**:
  - `pytest tests/web/test_api.py -v` -> **14 passed in 60.87s (100% pass rate)**.
  - Endpoints verified: `/api/health`, `/api/config`, `/api/examples`, `/api/validate`, `/api/edit`, `/api/jobs/{id}`, `/api/jobs/{id}/events` (SSE), `/api/jobs/{id}/cancel`, `/api/jobs/{id}/download/{kind}` (py, patch, stl, step, glb, original_glb).
  - Robustness verified: pre-flight failure interception, retry loop on malformed patch, typed patch failure handling, AST security violation blocking, oversize request rejection, and IP-based sliding window rate limiting.

### Phase W2: Real Model Integration
- **Plan**: Implement `LocalPeftModelBackend` and `MergedModelBackend` loading models with optional 4-bit quantization behind the single-worker async queue. Support retry-with-sampling on malformed patches. Add `scripts/web_smoke.py` evaluating 20 test triplets through the live API with latency and accuracy reporting.
- **Acceptance Results**:
  - Implemented `LocalPeftModelBackend` and `MergedModelBackend` in `src/cadpatch/web/model_service_peft.py` reusing `src/cadpatch/models`.
  - Configured single-worker asynchronous queue with auto-healing and queue position reporting.
  - Accelerated sandboxed execution via `CadQueryDaemonSandbox` reducing execution latency from ~6s to sub-second.
  - Ran `scripts/web_smoke.py` on 20 held-out test triplets:
    - **Execution Validity Rate**: **100.0%** (20/20 valid solids generated)
    - **Exact Match Rate**: **15.0%** (3/20 exact program matches, aligning with offline zero-shot prompted baseline)
    - **Latency**: p50 = **0.63s**, p95 = **0.98s**, Mean = **0.67s**
    - Saved benchmark results to `outputs/eval/web_smoke_results.json`.
  - Full API test suite passed: `pytest tests/web/test_api.py -v` -> **14 passed in 71.93s**.

### Phase W3: Frontend Development
- **Plan**: Initialize React + Vite + TypeScript + Tailwind frontend in `web/` or `frontend/`. Build code editor, diff viewer, 3D viewers with three.js, synchronized controls, overlay/ghost comparison mode, live progress stepper, example gallery, and iterative edit chaining. Verify via Playwright E2E tests and save UI screenshots.

### Phase W4: Hardening & Packaging
- **Plan**: Add rate limiting middleware, security headers, request ID logging, graceful shutdown, health probes, Dockerfile, docker-compose.yml, and Makefile web targets. Run concurrent load tests and sandbox attack tests.

### Phase W5: Documentation & Delivery
- **Plan**: Update `README.md`, finalize `docs/web_design.md` and `docs/deploy.md` with benchmark results, screenshots, and reproduction commands.
