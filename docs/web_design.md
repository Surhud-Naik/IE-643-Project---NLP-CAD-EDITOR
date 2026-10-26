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
- **Plan**: Initialize React 19 + Vite + TypeScript frontend in `web/` with curated modern styling tokens (glassmorphism, vibrant dark/light modes, glowing accents). Build dual Three.js 3D viewers with synchronized OrbitControls, wireframe/shaded toggles, and translucent ghost overlay mode. Build Search/Replace diff viewer with line-level syntax highlighting, live SSE progress stepper, example gallery (8 mechanical parts), convention help modal, and iterative edit chaining with session history. Verify via Playwright E2E tests and save UI screenshots.
- **Acceptance Results**:
  - `web/` application built with React 19, TypeScript, Vite, and Three.js.
  - Production bundle compiled into `web/dist/` in 1.21s and served natively by FastAPI.
  - Playwright E2E test suite in `tests/web/test_e2e_playwright.py` verified against clean local server:
    - `test_example_to_edit_render_download`: **PASSED**
    - `test_invalid_script_error`: **PASSED**
    - `test_patch_failure_error_state`: **PASSED**
    - `test_chaining_two_edits`: **PASSED**
    - `test_revert_from_history`: **PASSED**
    - **Overall E2E Status**: **5 passed in 50.38s (100% pass rate)**.
  - Saved full-fidelity screenshots in `outputs/web_screenshots/`:
    - `01_initial_page.png`: Clean initial layout with editor, natural-language prompt box, and dual 3D canvas viewports.
    - `02_example_gallery_modal.png`: 8-item gallery modal with categorized mechanical presets.
    - `03_edit_completed_result.png`: Completed CAD edit with side-by-side 3D models, download buttons, and highlighted Search/Replace diff block.
    - `04_ghost_overlay_mode.png`: Ghost translucent overlay view with original solid in translucent grey and edited solid in vibrant cyan.
    - `05_invalid_script_error.png`: Actionable sandbox pre-flight failure alert blocking model execution.
    - `06_patch_failure_collapsible.png`: Graceful failure display with collapsible raw model output inspect panel.
    - `07_chained_second_edit.png`: Sequential multi-turn editing state verifying cumulative geometry modifications.
    - `08_revert_history.png`: Session history timeline with one-click instant state reversion.

### Phase W4: Hardening & Localhost POC Packaging
- **Plan**: Configure security headers, request ID tracking, sliding window rate limits, daemon sandbox protection, and Makefile commands for zero-friction localhost execution (`make web-dev`, `make web-build`, `make web-serve`).
- **Acceptance Results**:
  - Security headers active: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
  - Rate limiting active: 10 edits/min per IP via sliding window queue.
  - Defense-in-depth security barrier: static AST scanner rejecting non-math/cadquery imports, dunder methods, `eval`/`exec`, and OS calls before reaching sandboxed subprocess execution.
  - Makefile targets configured and verified: `make web-build`, `make web-serve`, `make web-dev`.

### Phase W5: Documentation & Delivery
- **Plan**: Update `README.md` and `docs/web_design.md` detailing architecture, how to run locally, smoke test latency, screenshots, known limitations, and future improvements.
- **Acceptance Results**: Updated documentation and completed reproducible single-command local serving.

---

## 4. API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/health` | `GET` | Health check and system uptime status |
| `/api/config` | `GET` | Operational limits, available models, and active configuration |
| `/api/examples` | `GET` | 8 built-in CadQuery examples with metadata and instructions |
| `/api/validate` | `POST` | Pre-flight dry-run testing a script in the sandbox without model inference |
| `/api/edit` | `POST` | Enqueue a CAD editing job with script, instruction, and options |
| `/api/jobs/{id}` | `GET` | Poll status, queue position, retry attempts, and result metrics |
| `/api/jobs/{id}/events` | `GET` | Server-Sent Events (SSE) stream for live progress tracking |
| `/api/jobs/{id}/cancel` | `POST` | Cancel an in-flight or queued job |
| `/api/jobs/{id}/download/{kind}` | `GET` | Download artifacts (`py`, `patch`, `stl`, `step`, `glb`, `original_glb`) |
