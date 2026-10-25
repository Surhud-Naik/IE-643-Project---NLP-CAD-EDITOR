# Project Attribution and Originality Documentation

## Course Project Details
- **Course**: IE 643 - Advanced Deep Learning (Autumn 2026)
- **Project Title**: Learning to Edit Parametric CAD Programs from Natural-Language Instructions
- **Team**: AIADMK
- **Team Members**:
  - T Ganesh (Roll: 24B2250)
  - Surhud Naik (Roll: 24B2111)

---

## Third-Party Libraries & Resources Used

| Library / Resource | URL | License | Usage Description |
| :--- | :--- | :--- | :--- |
| **CadQuery** | https://github.com/CadQuery/cadquery | Apache 2.0 | Python parametric CAD modeling engine using OpenCASCADE backend to build and evaluate 3D solids. |
| **OCP (OpenCASCADE)** | https://github.com/CadQuery/OCP | LGPL 2.1 | Underlying geometry kernel for solid modeling, boolean operations, and STL meshing. |
| **Trimesh** | https://github.com/mikedh/trimesh | MIT | Surface mesh loading, point sampling, surface area and volumetric analysis. |
| **Hugging Face Transformers** | https://github.com/huggingface/transformers | Apache 2.0 | Base model loading, tokenization, and generation. |
| **PEFT** | https://github.com/huggingface/peft | Apache 2.0 | Parameter-Efficient Fine-Tuning via LoRA adapters. |
| **TRL** | https://github.com/huggingface/trl | Apache 2.0 | SFTTrainer and data collation for instruction tuning. |
| **Pytest** | https://github.com/pytest-dev/pytest | MIT | Unit testing suite for sandbox, patching, and evaluation. |
| **Gradio** | https://github.com/gradio-app/gradio | Apache 2.0 | Interactive web demo for CAD program editing. |
| **SciPy / NumPy** | https://scipy.org / https://numpy.org | BSD-3-Clause | Point cloud distance metrics (KDTree / Chamfer distance). |

---

## Relation to Prior Work: CAD-Editor

### Conceptual Inspiration Borrowed from CAD-Editor
1. **Localized Editing Motivation**: Real-world CAD modifications are inherently local; regenerating an entire design risks hallucination and unwanted drift in unmodified regions.
2. **Paired Edit Synthesis**: Generating paired CAD variations with programmatic parameter shifts to construct supervision data.
3. **Multi-level Evaluation Strategy**: Jointly evaluating syntactic validity (code execution), structural correctness (patch fidelity), and 3D geometric fidelity (Chamfer distance, volumetric overlap).
4. **Locate-then-Infill Concept**: Examining whether separating the localization of modification regions from the generation of updated code yields benefits.

### Core Differences & Original Contributions in Our Work
1. **Executable Python Programs vs. Domain-Specific Token Sequences**:
   - *CAD-Editor* uses custom, quantized command token sequences requiring specialized custom parsers.
   - *Our Work* operates entirely on standard, human-readable **CadQuery Python programs** with explicit named parameters, compatible with mainstream code LLMs.
2. **Syntactic Code-Patch Formulation vs. Sequence Infilling**:
   - Instead of token masking and sequence infilling, our model outputs a localized **SEARCH/REPLACE code patch** (inspired by modern developer tooling), leaving the rest of the script untouched.
3. **Parameter Perturbation & Semantic Templates vs. Latent Variation Sampling**:
   - We construct a parametric template bank with explicit mechanical constraints (plates, brackets, flanges, pulleys, filleted boxes), perturbing named dimensions and features programmatically with realistic mechanical vocabularies.
4. **Sandboxed Code Execution Engine**:
   - A dedicated secure sandbox evaluates arbitrary CadQuery code under memory, CPU, and timeout constraints with restricted namespaces, catching syntax errors, runtime exceptions, and invalid geometries.
5. **Exact AST/Regex Parameter Tracking**:
   - We compute unintended-change rates and verify whether the model modified exactly the intended engineering parameters.

---

## Originality Self-Check Compliance
- All templates, prompt banks, synthetic data generators, patch parsers, sandboxes, and metrics scripts are implemented from scratch.
- No code, datasets, or prompts from `microsoft/CAD-Editor` or any external repository were copied.
