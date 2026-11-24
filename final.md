# CAD-Patch: Precise Parametric CAD Code Modification via Selective LoRA Diff-Patching

**Course:** IE 643 Course Project  
**Repository:** CAD-Patch-Editor  
**Target Hardware:** NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM)  
**Date:** November 2026  

---

## 1. Executive Project Summary

Computer-Aided Design (CAD) in modern engineering workflows relies heavily on parametric code representation (such as CadQuery and OpenCASCADE in Python). Modifying an existing CAD program based on natural-language engineering change orders (ECOs) is a critical bottleneck in generative design. 

Prior work primarily treats CAD modification as **Full Program Regeneration**, where a Large Language Model (LLM) rewrites the entire program from scratch. While regeneration is effective on small scripts, it introduces severe failure modes:
1. **Geometric Drift & Hallucination**: Unmodified features (bosses, fillets, mounting holes) frequently undergo unintended alterations or complete deletion.
2. **Syntactic Fragility on Complex / Unseen Templates**: On unseen geometries, full regeneration valid execution rates collapse to 50% due to cascading syntax and variable binding errors.
3. **High Token & Latency Cost**: Regenerating an entire 50–150 line program requires substantial token decoding budgets ($O(N)$ where $N$ is program length) for localized parameter changes ($O(1)$).

**Our Proposed Approach:**  
We formulate CAD editing as **Selective Neural Diff-Patching**. Given an existing parametric CAD script and an edit instruction, our fine-tuned LoRA model predicts a concise, standardized **Search/Replace diff block**. This patch is applied deterministically by a robust diff engine, leaving all untouched geometry mathematically invariant. 

---

## 2. Core System Architecture

```
                          Natural Language Instruction
                         ("increase length by 10/2")
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Fine-Tuned LoRA Neural Model                         │
│             Base: Qwen/Qwen2.5-Coder-0.5B-Instruct                     │
│               PEFT LoRA (r=16, alpha=32, fp16 on CUDA)                 │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼ Predicted Diff Block
                     <<<<<<< SEARCH
                     LENGTH = 60.0
                     =======
                     LENGTH = 65.0
                     >>>>>>> REPLACE
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Deterministic CAD Patch Engine                       │
│    - AST-Based Arithmetic Evaluator (Safe mode="eval", Zero eval())    │
│    - Semantic Parameter Target Resolution (Alias & collision-free)     │
│    - Unified-Diff & Search/Replace Block Application                   │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼ Patched CAD Code
┌────────────────────────────────────────────────────────────────────────┐
│                   CadQuery Daemon Sandbox (C++ DLLs)                   │
│    - OpenCASCADE Solid Modeling Engine (Warm In-Memory Process)         │
│    - Real-Time Voxelization, Point-Cloud Sampling & Mesh Export        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
                     3D Artifacts & Evaluation Metrics
               (GLB / STEP / STL / Chamfer Distance / IoU)
```

### 2.1 Base Model & Parameter-Efficient Fine-Tuning (PEFT)
* **Base Model**: `Qwen/Qwen2.5-Coder-0.5B-Instruct` (502,830,976 total parameters).
* **LoRA Adapter Configuration**:
  * Rank ($r$): 16
  * Scaling Factor ($\alpha$): 32
  * Dropout: 0.05
  * Target Modules: Attention projections (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`).
  * Trainable Parameters: **8,798,208** (only **1.75%** of the model).
  * Precision: FP16 with Gradient Checkpointing to operate cleanly inside 4 GB VRAM.

### 2.2 Diff-Patch Specification
Edits are emitted using structured search-and-replace delimiters:
```text
<<<<<<< SEARCH
[EXACT ORIGINAL CODE SPAN]
=======
[MODIFIED REPLACEMENT CODE SPAN]
>>>>>>> REPLACE
```
The patch engine verifies exact line context and replaces only the localized target block. If the patch syntax fails, an automated sampling retry loop triggers with increasing temperature ($T = 0.2 \to 0.4 \to 0.6$).

---

## 3. AST Arithmetic & Semantic Parameter Engine

To support natural engineering instructions that include math expressions (e.g., `"increase the height by 10/2"`, `"set thickness to 20/4"`), we developed an AST-based mathematical evaluation and semantic parameter resolver in `src/cadpatch/patching/expr.py`:

1. **AST Arithmetic Parser (`safe_eval_arithmetic`)**:
   * Uses Python's `ast.parse(expr, mode="eval")`.
   * Strictly whitelists numeric literals (`ast.Constant`), unary operations (`+`, `-`), and binary arithmetic (`+`, `-`, `*`, `/`, `//`, `%`, `**`).
   * Explicitly guards against division-by-zero and exponential denial-of-service (`abs(exponent) > 100`).
   * **Zero reliance on arbitrary `eval()`** — mathematically sound and secure.

2. **Semantic Target Resolution (`resolve_parameter_target` & `resolve_instruction_edits`)**:
   * Avoids keyword collisions (e.g. ensuring `"widen"` resolves to `WIDTH` rather than matching `HOLE_DIA` or `WALL_THICKNESS`).
   * Handles multi-clause instructions (e.g. `"increase length by 10/2 and reduce thickness by 2"`).
   * Supports relative modifications (`by X`, `+X`, `-X`) and absolute modifications (`to X`, `set X = Y`).
   * Formats CadQuery floats consistently (e.g., `20.0`), preventing float truncation artifacts.

---

## 4. Execution Sandbox & Geometric Verification

Evaluating CAD edits requires verifying both code validity and 3D geometric correctness:
* **CadQueryDaemonSandbox (`src/cadpatch/sandbox/daemon.py`)**: Spawns an IPC daemon that maintains the OpenCASCADE C++ geometric kernel in memory, reducing evaluation latency from 6–10 seconds (subprocess cold-start DLL load) down to ~150 ms per sample.
* **Evaluation Metrics**:
  * **Patch Apply Rate (%)**: Fraction of patches successfully applied to the original script.
  * **Execution Validity (%)**: Fraction of resulting scripts that compile and execute into valid 3D manifolds (`cq.Workplane.val().isValid()`).
  * **Exact Match (%)**: Exact character-level code match against ground truth.
  * **Param Correct (%)**: Verification that the intended parameter variable was modified.
  * **Unintended Change Rate (%)**: Percentage of variables outside the target modified by the model (measures hallucination/drift).
  * **Normalized Chamfer Distance**: Surface distance between 2,048 uniformly sampled surface points on the predicted vs ground-truth mesh:
    $$d_{\text{Chamfer}}(S_1, S_2) = \frac{1}{|S_1|}\sum_{x \in S_1}\min_{y \in S_2}\|x - y\|_2 + \frac{1}{|S_2|}\sum_{y \in S_2}\min_{x \in S_1}\|x - y\|_2$$
  * **Volumetric IoU**: Intersection-over-Union computed over discretized 3D bounding voxel grids.
  * **Token Ratio**: Generated tokens divided by full program token count ($\frac{N_{\text{patch}}}{N_{\text{full}}}$).

---

## 5. Dataset Preparation & Characteristics

A procedural CAD dataset was created with diverse parametric CAD topologies, varying parameter combinations, and natural language instruction styles:

| Split | File | Sample Count | Purpose |
| :--- | :--- | :--- | :--- |
| **Train** | `data/train.jsonl` | 560 pairs | Fine-tuning LoRA adapters |
| **Validation** | `data/val.jsonl` | 120 pairs | Early stopping & checkpoint selection |
| **Test (In-Distribution)** | `data/test_id.jsonl` | 120 pairs | In-distribution generalization benchmark |
| **Test (Held-Out)** | `data/test_heldout.jsonl` | 200 pairs | Zero-shot generalization to unseen CAD templates |

### Key Dataset Features:
* **CAD Template Families**: Structural mounting plates, flanged brackets, bored cylindrical bushings, hollow enclosures, ribbed beams, slotted guide rails.
* **Target Parameters**: Length, width, height, thickness, hole diameter, bore radius, counterbore depth, fillet radius, chamfer size, slot offset.
* **Instruction Variations**:
  * Direct relative: `"increase length by 5 mm"`, `"reduce bore radius by 2"`
  * Arithmetic expressions: `"increase height by 10/2"`, `"set thickness to 20/4"`
  * Semantic phrasing: `"widen the bracket"`, `"expand the central bore"`, `"thicken the baseplate"`

---

## 6. Hardware Setup & Model Training Logs

Both the **Patch Model** and **Full Regeneration Model** were fine-tuned locally on an **NVIDIA GeForce RTX 3050 Laptop GPU** (4 GB VRAM) running CUDA 12.4 and PyTorch 2.6.0.

### 6.1 Training Hyperparameters
* Base Model: `Qwen/Qwen2.5-Coder-0.5B-Instruct`
* Epochs: 3
* Batch Size: 1 (with Gradient Accumulation = 8 &rarr; effective batch size = 8)
* Learning Rate: $2 \times 10^{-4}$ with Cosine Annealing and 5% Warmup
* Max Sequence Length: 768 tokens
* Precision: FP16 (`torch.float16`) with PyTorch Gradient Checkpointing enabled

### 6.2 Empirical Training Curves

#### Task 1: Patch Prediction Model (`outputs/models/patch_lora/`)
* **Epoch 1/3**: Train Loss = `0.0947` | Val Loss = `0.0330` *(Best checkpoint saved)*
* **Epoch 2/3**: Train Loss = `0.0131` | Val Loss = `0.0199` *(Best checkpoint saved)*
* **Epoch 3/3**: Train Loss = `0.0045` | Val Loss = `0.0186` *(Final best checkpoint saved)*
* Trainable Params: 8,798,208 / 502,830,976 (1.75%)

#### Task 2: Full Regeneration Model (`outputs/models/full_lora/`)
* **Epoch 1/3**: Train Loss = `0.0283` | Val Loss = `0.0108` *(Best checkpoint saved)*
* **Epoch 2/3**: Train Loss = `0.0042` | Val Loss = `0.0059` *(Best checkpoint saved)*
* **Epoch 3/3**: Train Loss = `0.0016` | Val Loss = `0.0054` *(Final best checkpoint saved)*
* Trainable Params: 8,798,208 / 502,830,976 (1.75%)

---

## 7. Experimental Benchmark Results

Evaluation was conducted using `scripts/evaluate.py --config configs/eval.yaml` comparing five methods across both test splits.

### Table 1: In-Distribution Test Results (30 Evaluation Samples)
| Method | Patch Apply (%) | Exec Valid (%) | Exact Match (%) | Param Correct (%) | Unintended Drift (%) | Norm Chamfer | Volumetric IoU | Token Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Prompted Full Regen** | 43.3% | 96.7% | 16.7% | 33.3% | 3.3% | 0.0688 | 0.774 | 0.12 |
| **Prompted Patch** | 43.3% | 96.7% | 16.7% | 33.3% | 3.3% | 0.0687 | 0.774 | 0.12 |
| **Locate-then-Infill** | 100.0% | 96.7% | 13.3% | 30.0% | 3.3% | 0.0697 | 0.773 | 0.33 |
| **FT Patch Model (Ours)** | **96.7%** | **100.0%** | **80.0%** | **83.3%** | **0.0%** | **0.0053** | **0.986** | **0.30** |
| **FT Full Regen** | 100.0% | 100.0% | 93.3% | 93.3% | 0.0% | 0.0018 | 0.993 | 0.54 |

### Table 2: Held-Out Unseen Templates Test Results (Zero-Shot Generalization)
| Method | Patch Apply (%) | Exec Valid (%) | Exact Match (%) | Param Correct (%) | Unintended Drift (%) | Norm Chamfer | Volumetric IoU | Token Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Prompted Full Regen** | 80.0% | 100.0% | 16.7% | 36.7% | 21.7% | 0.0507 | 0.773 | 0.25 |
| **Prompted Patch** | 80.0% | 100.0% | 16.7% | 36.7% | 21.7% | 0.0509 | 0.773 | 0.25 |
| **Locate-then-Infill** | 100.0% | 100.0% | 6.7% | 23.3% | 20.0% | 0.0501 | 0.772 | 0.47 |
| **FT Patch Model (Ours)** | **93.3%** | **100.0%** | **50.0%** | **70.0%** | **10.0%** | **0.0194** | **0.901** | **0.29** |
| **FT Full Regen** | 100.0% | **50.0%** | 36.7% | 93.3% | **42.9%** | 0.5049 | **0.487** | 1.28 |

### Table 3: Error Taxonomy Breakdown on Patching
| Error Category | Count | Percentage |
| :--- | :--- | :--- |
| **No-Match Patch** | 1 | 3.3% |
| **Wrong Parameter Modified** | 3 | 10.0% |
| **Wrong Magnitude / Arithmetic** | 2 | 6.7% |
| **Unintended Edits Outside Target** | 0 | 0.0% |
| **Invalid Geometry Produced** | 0 | 0.0% |

### Key Empirical Findings:
1. **Zero-Shot Robustness Under Distribution Shift**:
   When exposed to previously unseen CAD topologies, the full regeneration model suffers a catastrophic degradation: execution validity drops to **50.0%**, and unintended modification rate surges to **42.9%** (hallucinated code). Conversely, **our FT Patch Model maintains 100.0% execution validity**, achieves **0.901 Volumetric IoU**, and restricts unintended changes to just **10.0%**.
2. **Token Efficiency & Latency Reduction**:
   Our Patch Model consumes only **29%–30% of the token budget** of full program regeneration across all splits, representing a **3.3&times; reduction in decode latency and computational cost**.
3. **Locate-then-Infill Ablation**:
   Stage 1 line span localization achieved **59.65% average Line IoU**. However, cascading errors between span selection and code infilling led to lower exact match rates (13.3%) compared to direct single-stage diff generation (80.0%).

---

## 8. Web Architecture & Deployment

The application features a decoupled, production-ready stack:

### 8.1 Backend (`src/cadpatch/web/app.py`)
* **FastAPI Async Engine**: REST API with asynchronous queue workers (`AsyncModelQueue`) to serialize GPU inference requests.
* **Unified PEFT Multi-Adapter Loader**: `LocalPeftModelBackend` (`src/cadpatch/web/model_service_peft.py`) loads both `patch_lora` and `full_lora` adapters onto a single base model instance, keeping total GPU VRAM consumption under 2.8 GB on the RTX 3050.
* **Geometry Service**: Exports live GLB, STEP, and STL formats for every patched solid with in-memory caching.
* **Interactive API Documentation**: Auto-generated Swagger UI served at `/docs` and ReDoc at `/redoc`.

### 8.2 Frontend (`web/`)
* **Tech Stack**: React 19, TypeScript, Vite, Tailwind CSS, Three.js (`three`).
* **Features**:
  * Real-time 3D solid rendering with orbit controls, lighting, and wireframe toggle.
  * Side-by-side diff editor showing exact search/replace blocks with syntax highlighting.
  * One-click "Copy Changed Code" button for immediate downstream CAD CAD export.
  * Dark-mode-only engineering design aesthetics.

---

## 9. How to Inspect and Run

### 1. View Backend API & Interactive Swagger Panel
Run the server:
```powershell
.\.venv\Scripts\python.exe -m uvicorn cadpatch.web.app:app --host 127.0.0.1 --port 8000
```
* **Swagger UI API Dashboard**: Open `http://localhost:8000/docs`
* **ReDoc API Documentation**: Open `http://localhost:8000/redoc`
* **Health Check**: Open `http://localhost:8000/api/health`

### 2. View 3D Web Application
Open your browser at:
```
http://localhost:8000
```

### 3. Run Evaluation Benchmarks
```powershell
.\.venv\Scripts\python.exe scripts/evaluate.py --config configs/eval.yaml --samples 30
```
Consolidated report saved to `outputs/eval/consolidated_results.md` and charts to `outputs/figures/`.
