# CAD Patch Editor — Complete Technical & Model Architecture Summary

**Course Project**: IE 643 — Advanced Deep Learning (Autumn 2026)  
**Team**: AIADMK  
**Members**: T Ganesh (24B2250), Surhud Naik (24B2111)  
**Repository**: [https://github.com/Surhud-Naik/IE-643-Project---NLP-CAD-EDITOR.git](https://github.com/Surhud-Naik/IE-643-Project---NLP-CAD-EDITOR.git)  

---

## 1. Executive Summary & Core Motivation

In computer-aided engineering and manufacturing, 3D mechanical designs are created iteratively. Modifying an existing CAD design through a graphical user interface (GUI) requires specialized expertise, while communicating edits using natural language (e.g., *"Widen the central mounting hole by 4 mm"* or *"Increase plate thickness to 15 mm"*) promises to democratize design automation.

### Why Edit Code Instead of Raw Meshes (STL/STEP)?
Raw polygon meshes (STL/OBJ) or boundary representation interchange files (STEP) are **static geometries**. They lack the parametric history, dimensional variables, functional constraints, and semantic intent required for clean modification. Attempting to edit a mesh via 3D point deformation introduces non-manifold artifacts and destroys engineering tolerances. In contrast, **CadQuery (Python)** represents 3D shapes procedurally through executable code driven by named parameters. Modifying a parameter updates the entire solid kernel model while preserving topological validity.

### Why Localized Code Patches Instead of Full Regeneration?
Prior attempts at text-driven code editing rely on **full-program regeneration** (prompting an LLM to rewrite the entire script from scratch). In physical CAD modeling, full regeneration is fundamentally flawed:
1. **Unintended Geometric Drift**: Rewriting 50–100 lines of CAD code to tweak one hole diameter frequently alters other unmentioned dimensions (e.g., changing plate length or shifting hole centers), causing assembly misalignments.
2. **Syntactic Hallucinations**: Code LLMs frequently alter CAD kernel API calls, leading to OpenCASCADE kernel crashes.
3. **Inefficiency**: Re-generating dozens of lines of identical code consumes excess GPU compute and increases latency.

**Our Core Solution**: We formulate text-guided CAD editing as **Search/Replace code patch prediction**. The model generates only minimal diff blocks specifying what code lines to remove and what to insert. Unmodified code remains bit-for-bit identical, guaranteeing **zero unintended parameter changes** in unedited regions and slashing token generation by **68.5%**.

---

## 2. Conceptual Inspirations & Relation to Prior Work

Our architecture synthesizes ideas from recent research in generative CAD and developer code intelligence:

### 1. CAD-Editor (Microsoft Research, Yuan et al., ICML 2025)
* **What We Drew Inspiration From**:
  * The fundamental thesis that physical CAD modifications are inherently **local** and must preserve unedited regions.
  * The concept of **paired edit synthesis**: generating paired CAD program variations via programmatic parameter shifts to construct training supervision without manual annotation.
  * Multi-tier evaluation strategy: validating programs across syntactic validity (kernel execution), structural precision (patch application), and 3D geometric fidelity (Chamfer distance and volumetric IoU).
  * The **Locate-then-Infill** paradigm: exploring whether explicitly identifying the modification location before generating code changes prevents hallucinations.
* **How Our Work Differs and Improves**:
  * *CAD-Editor* uses custom, quantized command token sequences (sketch-and-extrude primitives) that require specialized tokenizers, cannot run standard Python libraries, and are difficult for human engineers to read or modify.
  * *Our Work* operates over standard, executable **CadQuery Python programs** running on an industrial OpenCASCADE B-Rep modeling kernel.
  * Instead of sequence infilling with mask tokens (`<mask...>` infill), we frame editing as **SEARCH/REPLACE code patches** compatible with off-the-shelf code LLMs.

### 2. Developer Tooling & Search/Replace Diff Formulations (Aider, CodeEditorBench)
* Early attempts at code diffs used Unix unified diffs (`@@ -12,4 +12,4 @@`). However, LLMs struggle with exact line-number arithmetic.
* Following modern developer tooling (e.g., Aider) and benchmarks (*CodeEditorBench*, *CanItEdit*), we adopt the `<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE` format. This format matches target code semantically by text content rather than fragile line numbers.

### 3. Procedural CAD Foundations (Fusion 360 Gallery, Willis et al., 2021)
* Demonstrates that mechanical assemblies in production environments are strictly parameter-driven, confirming that Level-3 procedural scripts are the most faithful representation of engineering design intent.

---

## 3. Parametric Program Representation & Dataset Engine

### Level-3 Executable Program Convention
Every CAD script adheres to a strict parametric convention:
```python
import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = 60.0
WIDTH = 40.0
HEIGHT = 12.0
HOLE_DIA = 8.0
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIA)
)
```
* **Convention Rules**:
  1. Top-level parameters are defined as uppercase constants at the top of the file.
  2. All operations form a fluent method-chaining pipeline rooted on `cq.Workplane`.
  3. The final evaluatable solid body is assigned to `result`.

### 10 Parametric Mechanical Templates
We authored 10 distinct parametric CAD templates spanning primary mechanical engineering categories:
1. `box`: Rectangular fixture plate with parameterized length, width, and height.
2. `bushing`: Concentric rotational sleeve bushing with inner/outer radii and axial length.
3. `patterned_plate`: Four-corner bolt clearance hole array on a rectangular base.
4. `filleted_block`: Rectangular body with edge rounding controlled by fillet radius.
5. `chamfered_block`: Machined mounting block with 45° beveled edges.
6. `l_bracket`: Structural angle bracket with horizontal/vertical flanges and mounting holes.
7. `circular_flange`: Circular pipe flange with bolt circle diameter and circular hole pattern.
8. `shelled_enclosure`: Electronics enclosure casing with wall thickness and hollow interior.
9. `slotted_link`: Kinematic linkage arm with dual rounded pin-joint slots.
10. `stepped_pulley`: Dual-tier V-belt transmission pulley with stepped outer radii.

### Synthetic Triplet Engine & Mechanical Constraints
To ensure every generated program is physically manufacturable, each template enforces geometric constraint functions:
* Wall thickness must exceed minimum thresholds ($\text{wall} \ge 2.0\text{ mm}$).
* Hole diameters cannot exceed plate boundaries ($D < \min(L, W) - 4.0\text{ mm}$).
* Fillet radii cannot exceed adjacent face dimensions ($R < H/2$).

The perturbation engine applies 4 types of mechanical mutations:
* **Single-parameter shifts**: Relative additions/subtractions, factor scalings, or absolute assignments.
* **Multi-parameter coupled shifts**: Proportional adjustments (e.g., scaling length and width together).
* **Feature toggles**: Adding/removing fillets, chamfers, or counterbores.
* **Array count/spacing edits**: Altering bolt hole numbers or pitch circle radii.

Paired natural language instructions are generated using diverse mechanical vocabularies (*"widen"*, *"expand bore"*, *"shave down"*, *"thicken"*, *"reinforce wall"*). All 1,000 synthesized triplets were executed in the sandbox; non-manifold or failing geometries were rejected, producing 1,000 verified `(original_code, instruction, edited_code)` triplets partitioned into Train (700), Validation (100), In-Distribution Test (100), and Held-Out Template Test (100).

---

## 4. Model Architecture & Training

```
+-----------------------------------------------------------------------------+
|                               Input Prompt                                  |
|  - System Instruction (CadQuery Patch Expert)                               |
|  - Natural-Language Edit Instruction                                        |
|  - Original CadQuery Script                                                 |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                   Base LLM: Qwen2.5-Coder-1.5B-Instruct                     |
|           + LoRA Adapter (r=16, alpha=32, target: all linear layers)        |
|                   Trained with Completion-Only Loss Masking                 |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                        Predicted Search/Replace Patch                       |
|   <<<<<<< SEARCH                                                            |
|   HOLE_DIA = 8.0                                                            |
|   =======                                                                   |
|   HOLE_DIA = 12.0                                                           |
|   >>>>>>> REPLACE                                                           |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                      apply_patch() & AST Validation                         |
|   - Replaces matched lines                                                  |
|   - Checks for NO_MATCH, AMBIGUOUS, MALFORMED                               |
|   - Retries with sampling (k=3) if non-applicable                           |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                     OpenCASCADE Sandboxed Execution                         |
|   - CadQueryDaemonSandbox (Hot stdio worker, ~10ms execution)               |
|   - Tessellates B-Rep Solid -> STL / STEP / GLB                             |
+-----------------------------------------------------------------------------+
```

### 1. Base Model & Fine-Tuning Setup
* **Base Model**: `Qwen2.5-Coder-1.5B-Instruct` — chosen for its strong reasoning on Python ASTs and low GPU memory footprint.
* **LoRA (Parameter-Efficient Fine-Tuning)**:
  * Rank $r = 16$, scaling $\alpha = 32$, dropout $= 0.05$.
  * Target modules: all linear projection layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`).
  * Total trainable parameters: **~9.5 million** (<0.6% of base model weights).
* **Optimization**:
  * AdamW with Cosine Learning Rate Scheduler ($lr = 2 \times 10^{-4}$, warmup ratio $0.03$).
  * Batch size 4 with gradient accumulation 4 (effective batch size 16).
  * Mixed precision FP16.

### 2. Completion-Only Loss Masking
Standard causal language modeling trains on the entire sequence, which wastes capacity predicting the user prompt and input script. We apply **completion-only loss masking**:
$$\mathcal{L} = -\sum_{t \in \text{Patch Tokens}} \log P(x_t \mid x_{<t})$$
The loss is zeroed out for all instruction and input program tokens. The gradient updates focus entirely on emitting the exact diff syntax and the updated numeric parameters.

### 3. Patch Application & Fallback Logic
The patch parser enforces strict verification:
1. **`SUCCESS`**: Exact match found; replaces target lines and verifies AST validity.
2. **`NO_MATCH`**: Target search block does not exist in the source code.
3. **`AMBIGUOUS`**: Target search block occurs multiple times with insufficient context.
4. **`MALFORMED`**: Missing delimiters (`<<<<<<< SEARCH`, `=======`, `>>>>>>> REPLACE`).

When `NO_MATCH` or `MALFORMED` occurs during inference, the system activates an automatic **retry-with-sampling loop** ($k=3$, temperature $\tau = 0.4$) to sample alternative valid diff proposals.

---

## 5. Sandboxed Geometry Engine & Daemon Acceleration

### Multi-Layer Security Architecture
User scripts and model outputs are treated as untrusted code:
1. **Static AST Pre-Check**: Before running Python, an AST visitor inspects code to reject imports other than `cadquery` and `math`, blocks all dunder attribute access (`__class__`, `__subclasses__`), and bans `eval`, `exec`, `open`, `os`, and `subprocess`.
2. **Subprocess Sandboxing**: Execution occurs in an isolated subprocess with memory limits (512 MB) and a strict 15-second execution timeout.

### The OpenCASCADE Daemon Acceleration
* **The Problem**: On Windows and Linux, launching a fresh Python subprocess that imports `cadquery` and loads the underlying OpenCASCADE (OCP) C++ shared libraries incurs **6 to 9 seconds of DLL startup overhead per execution**.
* **Our Solution (`CadQueryDaemonSandbox`)**: We built a persistent background worker communicating via JSON-RPC over stdio. The daemon initializes CadQuery and OpenCASCADE once and keeps the kernel hot in memory. Subsequent script executions run in **~10 milliseconds (>100x speedup)**.
* **Mesh Export**: Validated solids are tessellated into STL, converted to binary GLB via `trimesh` for WebGL rendering, and exported to STEP for CAD interoperability.

---

## 6. Evaluation Framework & Empirical Findings

### Evaluation Metrics
1. **Syntactic & Execution Validity**: Percentage of generated scripts that execute in OpenCASCADE without syntax errors or modeling kernel exceptions.
2. **Exact Program Match Rate**: Percentage of generated programs identical to ground-truth scripts.
3. **Unintended Parameter Change Rate**: Percentage of top-level parameters modified by the model that were *not* targeted by the natural-language instruction (measured via AST diffing).
4. **Normalized 3D Chamfer Distance**: Bidirectional surface distance evaluated by sampling 2,000 points over the B-Rep surface using a KDTree:
   $$d_{\text{CD}}(S_1, S_2) = \frac{1}{|S_1|}\sum_{x \in S_1} \min_{y \in S_2} \|x - y\|_2 + \frac{1}{|S_2|}\sum_{y \in S_2} \min_{x \in S_1} \|x - y\|_2$$
5. **Volumetric Intersection-over-Union (IoU)**: Voxelized 3D solid overlap.
6. **Token Ratio**: Ratio of generated output tokens to the full script length.

### Empirical Results Summary

| Model / Strategy | Execution Validity | Exact Match (In-Dist) | Exact Match (Held-Out) | Unintended Change Rate | Output Token Length | Token Savings vs Full-Regen |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **No-Op Baseline** | 100.0% | 0.0% | 0.0% | 0.0% | 0 tokens | N/A |
| **Prompted Full Regeneration** | 82.0% | 5.0% | 2.0% | **5.4%** | 89.2 tokens | 0.0% |
| **Prompted Zero-Shot Patch** | 88.0% | 15.0% | 8.0% | 1.8% | 28.1 tokens | -68.5% |
| **Locate-then-Infill Ablation** | 94.0% | 82.0% | 71.0% | 0.2% | 34.6 tokens | -61.2% |
| **Fine-Tuned CAD-Patch-Editor (Ours)** | **100.0%** | **100.0%** | **94.0%** | **0.0%** | **28.1 tokens** | **-68.5%** |

### Key Takeaways
1. **Zero Unintended Modifications**: The patch model achieved a **0.0% unintended change rate**, compared to 5.4% for full regeneration where the model regularly drifted unmentioned dimensions.
2. **Efficiency**: Code patches required an average of **28.1 tokens**, compared to **89.2 tokens** for regenerating full scripts (**68.5% compute reduction**).
3. **Locate-then-Infill vs. Single-Stage Patching**: While Locate-then-Infill (inspired by CAD-Editor) performed well, cascading errors (mis-localizing the line number caused the infill stage to fail) resulted in slightly lower held-out generalization than direct semantic search/replace patching.

---

## 7. How the Frontend Connects to the Model (API Bridge)

The web client communicates with the machine learning and geometry pipeline through an asynchronous, decoupled FastAPI service:

```
[ React 19 Frontend ]
       │
       ├─ POST /api/validate   ───> [ Pre-flight Dry-Run in Sandbox ]
       │
       ├─ POST /api/edit       ───> [ Enqueue Job in AsyncModelQueue (Prevents GPU OOM) ]
       │                                     │
       ├─ GET  /api/jobs/{id}/events <───────┴── [ SSE Stream: VALIDATING -> GENERATING -> APPLYING -> EXECUTING ]
       │
       └─ GET  /api/jobs/{id}/download/{kind} ──> [ Serve STL, STEP, GLB, .py, .diff ]
```

1. **Job Enqueueing (`POST /api/edit`)**:
   * Accepts `{ script, instruction, retry_count }`.
   * Passes the script through a pre-flight sandbox check to ensure the starting model is valid before invoking the model.
   * Enqueues the request into a **single-worker asynchronous queue (`AsyncModelQueue`)**. This prevents concurrent users from overloading GPU VRAM.
   * Returns a unique `job_id` and initial queue position.

2. **Live Event Streaming (`GET /api/jobs/{id}/events`)**:
   * Uses **Server-Sent Events (SSE)** over a single HTTP connection.
   * Pushes fine-grained status transitions to the client:
     * `VALIDATING`: Pre-flight sandbox check of original script.
     * `GENERATING (attempt n/3)`: Model inference generating search/replace patch.
     * `APPLYING`: Applying diff block to source code.
     * `EXECUTING`: Daemon sandbox evaluating geometry, calculating Chamfer distance & IoU, and generating 3D meshes.
     * `COMPLETED`: Emits full payload containing the edited script, patch text, AST metrics, and download URLs.

3. **3D Mesh Rendering & Downloads (`GET /api/jobs/{id}/download/{kind}`)**:
   * The client Three.js 3D viewport requests the binary GLB (`/download/glb`) for instantaneous hardware-accelerated 3D rendering.
   * Clean downloads are provided for `.py`, `.diff`, `.stl`, `.step`, and `.glb`.

4. **Iterative Multi-Turn Chaining**:
   * Clicking *"Continue Editing from Result"* feeds the generated `edited_script` back into the input state, enabling sequential conversational editing while preserving the session history for one-click reversion.

---

## 8. Summary Table of Repo Deliverables

| Component | Path | Description |
| :--- | :--- | :--- |
| **Model Trainer** | `scripts/train.py` | SFT LoRA fine-tuning on Qwen2.5-Coder with completion-only loss |
| **Patch Engine** | `src/cadpatch/patching/patch.py` | Search/replace patch parser with typed error handling |
| **Sandbox & Daemon** | `src/cadpatch/sandbox/` | AST security validator and persistent OpenCASCADE daemon |
| **Geometry Metrics** | `src/cadpatch/eval/geometry_metrics.py` | KDTree surface Chamfer distance and volumetric IoU |
| **FastAPI Backend** | `src/cadpatch/web/app.py` | REST & SSE service with single-worker model queue |
| **React Web App** | `web/src/` | Pure dark-mode single-page UI with Three.js dual viewers |
| **Single Runner** | `run_web.py` | Single-command localhost runner (`python run_web.py`) |
| **Smoke Benchmark** | `scripts/web_smoke.py` | Live-API evaluation on 20 test triplets (100% valid, 0.63s p50) |
