# System Architecture & Design Specification (IE 643)

## Project: Learning to Edit Parametric CAD Programs from Natural-Language Instructions
- **Team**: AIADMK (T Ganesh, Surhud Naik)
- **Target Course**: IE 643

---

## 1. Phase-by-Phase Execution Plan

### Phase 1: Setup and Representation (Current Phase)
- Environment setup: Python 3.11 with CadQuery (OCP), Trimesh, PyTorch, Transformers, PEFT, TRL, Pytest.
- CadQuery smoke test: generate a box with a through-hole and export to STL.
- Program Convention: 20-60 line standalone Python scripts with explicit capitalized parameters (`PARAM = value`) and a terminal `result = ...` Workplane solid.
- Patch Representation: Multi-block `<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE` format with strict line-exact matching and typed statuses (`SUCCESS`, `NO_MATCH`, `AMBIGUOUS`, `MALFORMED`).
- Diff / Patch generation: `make_patch(orig, edited)` using hunk aggregation, verified via round-trip idempotency.
- Sandboxed Execution Engine: AST static validation + subprocess execution with timeouts, memory limits, and import whitelisting (`cadquery`, `cq`, `math` only).

### Phase 2: Parametric Dataset Construction
- 10 parametric templates across 6+ distinct manufacturing categories (plates, cylinders, hole arrays, fillets, chamfers, L-brackets, flanges, shelled boxes, slots, pulleys).
- Rigorous parameter boundaries ensuring valid topology (e.g., fillets < wall thickness/2).
- Synthetic perturbation engine: single-parameter shifts, multi-parameter shifts, feature toggle, count/spacing changes.
- Rich natural-language instruction synthesis using diverse engineering phrasing (e.g., "widen the mounting hole by 2 mm", "increase cylinder height to 40 mm").
- Programmatic validation: 100% of triplets verified for positive non-zero volume, no manifold errors, and geometric divergence between original and edited states.
- Train / Val / In-Distribution Test / Held-Out Template Test splits to rigorously test out-of-distribution generalization.

### Phase 3: Evaluation Framework & Baselines
- Dual-tier evaluation:
  1. Program-wise: Execution validity, patch application success, exact code match, normalized Levenshtein distance, correct-parameter-modified AST accuracy, unintended-modification rate, token count ratio.
  2. Geometry-wise: Normalized Chamfer Distance on 10,000 sampled surface points, Volumetric IoU (Boolean + Voxel fallback), bounding box aspect ratio error, relative volume error.
- Baseline models: Prompted few-shot full regeneration, Prompted few-shot patch prediction, Oracle sanity checks (GT patch, No-Op, Random perturbation).

### Phase 4: LoRA Model Fine-Tuning
- Base model: Qwen2.5-Coder (1.5B / 0.5B) loaded with PEFT LoRA (rank 16, alpha 32).
- Completion-only loss masking: prompt tokens ignored in loss computation.
- Dual fine-tuned models: (1) Patch Model (ours), (2) Full Regeneration Model.
- Deterministic greedy inference with early stop sequence handling and fallback retry logic.

### Phase 5: Comparison, Locate-then-Infill Ablation & Error Analysis
- Comparative analysis across all four model configurations on both In-Distribution and Held-Out Test sets.
- Locate -> Infill 2-stage ablation mimicking CAD-Editor over Python code.
- Exhaustive taxonomy of failure modes (syntax errors, arithmetic offsets, wrong parameter selection, geometry collapse).

### Phase 6: Interactive Demo & Final Deliverables
- Gradio web interface featuring code diff display, live 3D STL visualizer / preview renderer, before/after geometric comparison metrics.
- Complete documentation: `README.md`, `Makefile`, `docs/report.md`, `docs/analysis.md`, `docs/ATTRIBUTION.md`.

---

## 2. Program Conventions

Every CadQuery script must adhere to the following template structure:
```python
import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = 50.0
WIDTH = 30.0
HEIGHT = 15.0
HOLE_DIAMETER = 6.0
# ====================================================

# Build geometry
result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIAMETER)
)
```

Rules:
1. All editable values must appear as top-level capitalized constants.
2. The final 3D shape must be assigned to the global variable `result`.
3. No arbitrary I/O or system calls.
4. Total line count strictly maintained between 20 and 60 lines for clean diffing.

---

## 3. Patch Format Specification

Patches follow an exact search/replace block structure:
```text
<<<<<<< SEARCH
HOLE_DIAMETER = 6.0
=======
HOLE_DIAMETER = 8.0
>>>>>>> REPLACE
```

### Application Semantics:
- For each block:
  - If `SEARCH` block is empty: return `MALFORMED`.
  - If `SEARCH` text appears 0 times in target code: return `NO_MATCH`.
  - If `SEARCH` text appears > 1 times in target code: return `AMBIGUOUS`.
  - If `SEARCH` text appears exactly once: replace it with `REPLACE` text.
- If all blocks succeed: return `(modified_code, "SUCCESS")`.

### Round-trip Property:
For any valid pair `(orig, edited)`, `apply_patch(orig, make_patch(orig, edited))` must yield `(edited, "SUCCESS")`.

---

## 4. Sandbox Execution Specification

Untrusted model-generated code must never run directly in the host process.
- **Static Check**: Pre-scan code with Python `ast` parser. Reject forbidden modules (`os`, `sys`, `subprocess`, `socket`, `shutil`, `urllib`, `builtins`), attributes (`__subclasses__`, `__globals__`), or dynamic code execution (`eval`, `exec`).
- **Dynamic Check**: Spawn an isolated subprocess running an execution wrapper.
  - Timeout: 10 seconds.
  - Memory limit enforced.
  - Output: Serialized STL mesh file + volume / bounding box statistics, or structured exception traceback.
