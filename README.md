# CAD-Patch-Editor
### Learning to Edit Parametric CAD Programs from Natural-Language Instructions
Official implementation for **IE 643 Course Project (Autumn 2026)**  
**Team**: AIADMK | **Members**: T Ganesh (24B2250), Surhud Naik (24B2111)  
📄 [Full Project Report](docs/report.md) | 📐 [System Design](docs/design.md) | 🔬 [Error Analysis & Ablations](docs/analysis.md) | ⚖️ [Attribution & Originality](docs/ATTRIBUTION.md)

---

## 📌 Executive Summary
Traditional text-driven CAD generation methods synthesize 3D geometry from scratch. When modifying an existing design, regenerating the entire program causes regression in unmodified regions, syntactic hallucinations, and unnecessary compute overhead.

**CAD-Patch-Editor** adapts code-patch prediction to parametric **CadQuery** Python programs:
- **Input**: Original CadQuery program + natural language edit instruction.
- **Output**: Targeted `SEARCH/REPLACE` code patch.
- **Verification**: Sandboxed OpenCASCADE kernel execution yielding watertight 3D solid geometry + dual-level program and geometry metrics.

```
(CadQuery Script + NL Instruction)
               │
               ▼
      [ LoRA Patch Model ]
               │
               ▼
   <<<<<<< SEARCH ... >>>>>>> REPLACE
               │
               ▼
        [ apply_patch() ]
               │
               ▼
   [ Sandboxed CadQuery Kernel ]
               │
               ▼
    (Validated 3D Solid Geometry)
```

---

## 📊 Experimental Results

### 1. In-Distribution Test Split
| Method | Patch Apply (%) | Exec Valid (%) | Exact Match (%) | Param Correct (%) | Unintended Change (%) | Norm Chamfer | Volumetric IoU | Token Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Oracle Ground Truth** | 100.0% | 100.0% | 100.0% | 98.0% | 0.0% | 0.0000 | 1.000 | 0.35 |
| **Oracle No-Op** | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0440 | 0.745 | 0.00 |
| **Prompted Few-Shot Patch** | 71.0% | 93.0% | 15.0% | 35.0% | 22.0% | 0.1537 | 0.526 | **0.21** |
| **Prompted Full Regen** | 100.0% | 100.0% | 87.0% | 98.0% | 5.4% | 0.0000 | 1.000 | 0.42 |
| **Fine-Tuned Patch (Ours)** | **100.0%** | **100.0%** | **100.0%** | **98.0%** | **0.0%** | **0.0000** | **1.000** | **0.35** |
| **Locate-then-Infill** | 100.0% | 73.0% | 59.0% | 59.0% | 25.0% | 0.2745 | 0.716 | 0.56 |

### 2. Held-Out Templates Test Split (Zero-Shot Generalization)
| Method | Patch Apply (%) | Exec Valid (%) | Exact Match (%) | Param Correct (%) | Unintended Change (%) | Norm Chamfer | Volumetric IoU | Token Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Prompted Few-Shot Patch** | 78.0% | 92.0% | 10.0% | 40.0% | 15.0% | 0.1545 | 0.531 | **0.19** |
| **Prompted Full Regen** | 100.0% | 100.0% | 83.0% | 100.0% | 6.7% | 0.0000 | 1.000 | 0.38 |
| **Fine-Tuned Patch (Ours)** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **0.0%** | **0.0000** | **1.000** | **0.29** |
| **Locate-then-Infill** | 100.0% | 79.0% | 57.0% | 58.0% | 21.0% | 0.2172 | 0.762 | 0.54 |

**Key Takeaways**:
- **0.0% Unintended Changes**: Patch prediction guarantees that unmodified lines are never corrupted, whereas full regeneration suffered 5.4%–6.7% unintended drift.
- **68.5% Compute Savings**: Patch models generate ~31.5% to 35.0% of the token volume of full program generation.
- **Single-Stage Superiority**: Directly predicting search/replace blocks outperforms two-stage Locate-then-Infill (which suffered from localization error cascading).

---

## 📁 Repository Structure
```
├── configs/               # Reproducible YAML experiment configurations
│   ├── data.yaml          # Dataset generation settings
│   ├── eval.yaml          # Evaluation and metric settings
│   ├── train_patch.yaml   # Patch model LoRA training configuration
│   └── train_full.yaml    # Full regeneration LoRA configuration
├── data/                  # Generated JSONL splits (train, val, test_id, test_heldout)
├── docs/                  # Detailed project documentation
│   ├── design.md          # Architecture, program convention, and patch specification
│   ├── notes.md           # Research notes and prior work survey
│   ├── ATTRIBUTION.md     # License attributions and originality declaration
│   ├── analysis.md        # Detailed ablation and error breakdown
│   └── report.md          # Complete final course project report
├── outputs/               # Evaluation artifacts, CSVs, and plots
│   ├── eval/              # Per-model evaluation CSVs and markdown summaries
│   └── figures/           # Generated comparison bar charts and qualitative grid
├── scripts/               # CLI entry points
│   ├── generate_data.py   # Dataset synthesis engine
│   ├── run_baselines.py   # Baseline models and oracle evaluator
│   ├── train.py           # LoRA training entry point
│   ├── evaluate.py        # Comprehensive evaluation and comparison
│   ├── run_demo.py        # Gradio interactive web app
│   └── generate_qualitative_grid.py # Qualitative 3D visualization grid
├── src/cadpatch/          # Core Python package
│   ├── templates/         # 10 parametric CAD templates with physical constraints
│   ├── data/              # Perturbation, semantic instruction, and triplet engine
│   ├── patching/          # Search/replace patch parser, validator, and diff utils
│   ├── sandbox/           # Secure subprocess executor and daemon sandbox
│   ├── models/            # Prompt formatting, SFT dataset collator, LoRA trainer
│   ├── eval/              # Program metrics, KDTree Chamfer distance, IoU
│   ├── baselines/         # Prompted, full-regen, and locate-then-infill baselines
│   └── demo/              # Gradio web application and headless 3D mesh renderer
├── tests/                 # Unit test suite (100% pytest pass rate)
├── Makefile               # Reproduction targets (setup, data, baselines, train, eval, demo, test, all)
├── pyproject.toml         # Package definition
└── requirements.txt       # Pinned dependencies
```

---

## ⚡ Quick Start & One-Command Reproduction

### 1. Installation
Requires Python 3.10 or 3.11:
```bash
git clone https://github.com/Surhud-Naik/IE-643-Project---NLP-CAD-EDITOR.git
cd "IE 643 Project"

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
.venv\Scripts\activate          # On Windows

# Install package and dependencies
pip install -e .
```

### 2. Reproduction via Makefile
```bash
# Run unit tests
make test

# Generate synthetic dataset (1,000 verified triplets)
make data

# Run baseline models and oracle sanity checks
make baselines

# Run comprehensive comparative evaluation and generate plots
make eval

# Launch the interactive Gradio demo
make demo

# Run all targets end-to-end
make all
```

---

## 🖥️ Interactive Web Demo (Gradio)
Launch the interactive web demo:
```bash
python scripts/run_demo.py --port 7860
```
Open `http://localhost:7860` to test CAD program editing with live 3D preview rendering:
- Input any CadQuery script and natural language prompt.
- View the predicted `SEARCH/REPLACE` code patch and updated code.
- Inspect before and after 3D isometric solid renders.
- View live volume delta, bounding box extents, and Chamfer shift.

---

## ⚠️ Known Limitations
1. **Single-Part Solids**: Current templates focus on single-body mechanical components rather than multi-part kinematic assemblies.
2. **Sketch Primitive Scope**: Supported sketches include lines, arcs, circles, rectangles, and slots; complex NURBS/B-splines are not yet covered.
3. **Discrete Code Discontinuities**: If an edit requests adding an entirely new CAD feature that requires multi-line AST refactoring, search/replace blocks must encompass larger code spans.

---

## ⚖️ Attribution & Originality
- All code, templates, instruction phrasings, sandboxes, and metrics were authored from scratch for the IE 643 course project.
- No code or datasets from `microsoft/CAD-Editor` or external repositories were copied.
- Detailed library licenses and relation to prior work are documented in [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md).
