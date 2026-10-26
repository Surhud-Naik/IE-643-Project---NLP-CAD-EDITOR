# CAD Patch Editor: Model Showcase & Code Walkthrough Script

**Project**: Learning to Edit Parametric CAD Programs from Natural-Language Instructions  
**Course**: IE 643 — Advanced Deep Learning  
**Goal**: Presenting the core machine learning model, dataset pipeline, search/replace patching formulation, and evaluation metrics.

---

## Act 1: The Problem & Parametric Representation

### Step 1.1: Why Code Instead of Meshes?
- **[Open this file]**: `src/cadpatch/templates/catalog.py`
- **[Point to this line]**: Lines 10–35 (`box_plate` template definition)
- **[Say this]**:
  > *"When people think of 3D modeling with AI, they usually think of generative meshes or point clouds. But in engineering and manufacturing, raw polygon meshes like STL or OBJ files are static and uneditable—they lack dimensional variables and design intent.*
  > 
  > *In this project, we represent 3D geometry as executable Python code using CadQuery, an industrial wrapper around the OpenCASCADE B-Rep geometric modeling kernel. Here in `catalog.py`, notice our Level-3 parametric convention:*
  > 1. *All modifiable dimensions—`LENGTH`, `WIDTH`, `HEIGHT`, `HOLE_DIA`—are declared as uppercase constants at the top of the file.*
  > 2. *The 3D geometry is constructed through a fluent, deterministic pipeline.*
  > 3. *The final solid is assigned to `result`.*
  > 
  > *Editing the code by modifying a parameter updates the entire solid kernel model while preserving topological validity and exact engineering tolerances."*

---

## Act 2: Dataset Synthesis & Physical Constraints

### Step 2.1: Enforcing Mechanical Manufacturability
- **[Open this file]**: `src/cadpatch/data/generator.py`
- **[Point to this line]**: Lines 45–95 (Parameter perturbation and validity check)
- **[Say this]**:
  > *"Supervised learning requires paired examples of `(original code, edit instruction, edited code)`. However, no public paired CAD edit dataset existed in CadQuery Python.*
  > 
  > *Instead of randomly tweaking numbers, our synthetic generator in `generator.py` applies mathematically constrained perturbations spanning single-parameter changes, coupled dimension scalings, and feature toggles.*
  > 
  > *Notice that we enforce physical manufacturability constraints: hole diameters cannot exceed plate boundaries, wall thicknesses cannot drop below 2 millimeters, and fillet radii cannot exceed adjacent face dimensions. Every single synthesized triplet in our 1,000-sample dataset was executed through the OpenCASCADE kernel to confirm it yields a valid, non-self-intersecting solid."*

---

## Act 3: The Search/Replace Patch Engine

### Step 3.1: Why Localized Patches Beat Full Regeneration
- **[Open this file]**: `src/cadpatch/patching/patch.py`
- **[Point to this line]**: Lines 15–65 (`apply_patch` function)
- **[Say this]**:
  > *"Prior methods like CAD-Editor or standard LLM code generation prompt the model to rewrite the entire script from scratch. In physical CAD modeling, full regeneration is disastrous: rewriting 60 lines of code just to widen a hole frequently corrupts unmentioned dimensions, changes the base geometry, or hallucinates syntax.*
  > 
  > *In `patch.py`, we formulate editing as Search/Replace diff prediction, using the `<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE` block format popularized by modern developer tooling.*
  > 
  > *Notice our error handling: `apply_patch` checks for exact matches, handles whitespace normalization, and flags `STATUS_AMBIGUOUS` if a search block matches multiple locations in the code without sufficient context. Crucially, because only the matched block is swapped, unmodified code is guaranteed to remain 100% untouched—yielding zero unintended parameter drift."*

---

## Act 4: Model Architecture & Completion-Only Loss Masking

### Step 4.1: Prompt Formatting & Input Structure
- **[Open this file]**: `src/cadpatch/models/prompt_formatter.py`
- **[Point to this line]**: Lines 15–40 (`format_patch_prompt` function)
- **[Say this]**:
  > *"Here is how we feed inputs to the model. We supply a concise system instruction explaining the Search/Replace syntax, followed by the current CadQuery script and the natural language instruction.*
  > 
  > *The model is required to output ONLY the search/replace patch block—no markdown explanations, no conversational pleasantries, and no unchanged code."*

### Step 4.2: LoRA Fine-Tuning with Target-Only Masking
- **[Open this file]**: `src/cadpatch/models/dataset.py` (or `src/cadpatch/models/trainer.py`)
- **[Point to this line]**: Lines 25–55 (Loss masking with `-100`)
- **[Say this]**:
  > *"This is a key technical detail of our training setup. We fine-tune Qwen2.5-Coder-1.5B-Instruct using LoRA with rank 16 and alpha 32 applied to all attention projection layers.*
  > 
  > *Notice here in the dataset collator: we apply **Completion-Only Loss Masking**. All tokens belonging to the system prompt, the input CadQuery code, and the user instruction are masked with label `-100` in PyTorch.*
  > 
  > *Gradients are computed strictly on the predicted patch tokens. This forces the model to learn the semantic mapping from the natural language edit request to the exact parameter diff, rather than wasting model capacity memorizing boilerplate Python imports or standard geometry methods."*

---

## Act 5: OpenCASCADE Kernel Sandbox & Daemon Acceleration

### Step 5.1: Subprocess Security & Daemon Acceleration
- **[Open this file]**: `src/cadpatch/sandbox/daemon_sandbox.py`
- **[Point to this line]**: Lines 20–65 (`CadQueryDaemonSandbox` class)
- **[Say this]**:
  > *"Executing arbitrary LLM-generated Python code presents two major engineering challenges: security and latency.*
  > 
  > *First, security: all code undergoes static AST verification that strictly permits `cadquery` and `math` imports while blocking system calls, dunder exploits, and eval.*
  > 
  > *Second, latency: OpenCASCADE is a massive C++ geometry library. On Windows, spawning a fresh Python subprocess and loading OpenCASCADE DLLs takes 6 to 9 seconds per run.*
  > 
  > *To solve this, we built `CadQueryDaemonSandbox`. It launches a persistent background worker over stdio that keeps the OpenCASCADE kernel warm in memory. Incoming scripts are passed as JSON-RPC payloads, bringing execution time down from 8 seconds to just 10 milliseconds—a greater than 100x speedup that makes real-time validation and iterative retry sampling feasible."*

---

## Act 6: Dual-Tier Evaluation & Benchmark Results

### Step 6.1: Program & 3D Geometry Metrics
- **[Open this file]**: `src/cadpatch/eval/geometry_metrics.py`
- **[Point to this line]**: Lines 15–50 (`compute_geometry_metrics`, Chamfer distance & Volumetric IoU)
- **[Say this]**:
  > *"Code exact-match alone is not enough to validate CAD editing—two syntactically different programs might produce the identical 3D solid, or a 1-character typo might cause a catastrophic topological failure.*
  > 
  > *We built a dual-tier evaluation framework: Tier 1 tracks AST parameter modifications, Levenshtein distance, and unintended changes. Tier 2 tessellates both models into meshes, samples 2,000 surface points via a KD-Tree to calculate normalized Chamfer Distance, and computes 3D Volumetric IoU via bounding box voxelization."*

### Step 6.2: Experimental Results & Baseline Comparison
- **[Open this file]**: `docs/report.md` (or `outputs/eval/summary_table.csv`)
- **[Point to this line]**: Table 1 (Experimental Evaluation Table)
- **[Say this]**:
  > *"Here are the experimental results across our held-out test split, comparing our Fine-Tuned Patch model against Prompted Few-Shot Patching, Prompted Full Regeneration, and the Locate-then-Infill paradigm adapted from CAD-Editor:*
  > 
  > 1. ***0.0% Unintended Changes**: Our patch model achieved 100% exact match and 0.0% unintended changes. In contrast, Full Regeneration suffered 5.4% to 6.7% unintended parameter drift, altering features the user never asked to touch.*
  > 2. ***68.5% Compute Savings**: Patch prediction reduced the token generation ratio from 1.0 down to 0.315, cutting GPU compute by more than two thirds.*
  > 3. ***Single-Stage Superiority**: The two-stage Locate-then-Infill baseline dropped to 73% execution validity due to cascading localization errors. Predicting the localized search/replace diff directly in one pass proved vastly superior."*

---

## Act 7: Live Execution Check

### Step 7.1: Verify All Test Suites Pass
- **[Run command]**:
  ```bash
  .venv\Scripts\pytest
  ```
- **[Say this]**:
  > *"As you can see, our full test suite covers synthetic data generation, search/replace patching, security sandboxing, 3D geometry metrics, and all 10 CAD parametric templates—with 37 passing unit tests."*

---

## Quick Reference / Cheat Sheet for Q&A

| Question | Recommended Answer |
| :--- | :--- |
| **Why not train an end-to-end vision-to-CAD model?** | Vision-to-CAD lacks parametric constraints and precision. Modifying an existing engineering part requires preserving exact dimensions and assembly mating surfaces, which are natively represented in parametric code. |
| **What happens if the model generates a bad patch?** | Our inference loop catches `STATUS_NO_MATCH` or kernel runtime exceptions, feeds the error back, and performs temperature-sampled retry inference ($k=3$) to self-correct. |
| **Why Qwen2.5-Coder-1.5B?** | It has strong code syntax comprehension and fills-in-the-middle pre-training, while being compact enough to run with low latency and modest VRAM. |
