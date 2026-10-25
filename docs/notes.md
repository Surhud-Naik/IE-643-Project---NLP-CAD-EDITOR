# Research Notes & Literature Study (IE 643 Project)

## 1. Study of Prior Work: CAD-Editor (Microsoft Research, ICML 2025)
- **Paper**: *CAD-Editor: A Locate-then-Infill Framework with Automated Training Data Synthesis for Text-Based CAD Editing* (Yuan et al., 2025).
- **License**: MIT License (Microsoft).
- **Core Paradigm**:
  - Operates on quantized token sequences representing sketch-and-extrude commands (similar to SkexGen / DeepCAD representations).
  - Uses a two-stage approach:
    1. *Locating*: Model takes an original CAD sequence and a text instruction, identifying tokens to modify and substituting them with `<mask...>`.
    2. *Infilling*: Model predicts the replacement sequence for the masked region.
  - *Data Synthesis*: Pairs CAD models generated via HNC-CAD variations, computes sequence-level diffs, and prompts GPT-4o (multimodal vision + text) to generate descriptive instructions.
  - *Evaluation*:
    - Validity: Percentage of generated token sequences that successfully parse into valid B-Rep CAD objects via OpenCASCADE without kernel failure.
    - Geometric fidelity: Chamfer Distance (CD), Minimum Matching Distance (MMD), and Jensen-Shannon Divergence on sampled point clouds.
    - Directional CLIP Score: Measures whether visual change aligns with instruction intent.
- **Limitations & Differences for Our Project**:
  - CAD-Editor uses custom token sequences rather than standard programming languages.
  - Sequence infilling requires specialized tokenizers and cannot directly leverage pre-trained code LLMs (e.g., Qwen2.5-Coder).
  - Our approach represents CAD as standard, executable **CadQuery Python programs** and models edits as **syntactic code patches** (SEARCH/REPLACE blocks), maintaining code readability, parameter semantics, and direct compiler verification.

## 2. CadQuery Documentation & API Study
- **CadQuery** (Apache 2.0 License): A Python parametric CAD scripting framework based on OpenCASCADE (OCP).
- **Key Concepts**:
  - `cadquery.Workplane("XY")`: Fluent API starting from a construction plane.
  - 2D sketch operations: `box()`, `circle()`, `rect()`, `polygon()`, `slot2D()`, `lineTo()`, `threePointArc()`.
  - 3D operations: `extrude()`, `revolve()`, `loft()`, `sweep()`.
  - Boolean / Modification operations: `cut()`, `union()`, `intersect()`, `hole()`, `cboreHole()`, `cskHole()`.
  - Feature modifications: `.faces(">Z").fillet(r)`, `.edges("|Z").chamfer(d)`, `.shell(thickness)`.
  - Export: `exporters.export(shape, "model.stl")` or `exporters.export(shape, "model.step")`.
- **Parametric Conventions**:
  - Parameters are declared as explicit numeric variables at script header (e.g., `LENGTH = 50.0`, `FILLET_R = 3.0`).
  - Final solid stored in standard variable `result`.
  - Strict geometric constraints (e.g., `FILLET_R < min(WIDTH, HEIGHT)/2`) prevent OpenCASCADE topology collapse.

## 3. Hugging Face TRL + PEFT
- **PEFT (LoRA / QLoRA)**:
  - Low-Rank Adaptation freezes base weights and trains rank decomposition matrices ($W = W_0 + \frac{\alpha}{r} B A$).
  - Target modules in code LLMs: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`.
- **TRL (SFTTrainer)**:
  - Supervised fine-tuning with prompt-completion formatting.
  - *Data Collator for Completion-Only LM*: Uses special response template markers (e.g., `assistant\n`) to mask loss on system prompt and user input, calculating cross-entropy loss exclusively on target code patches.
  - Memory efficiency: gradient checkpointing, `bfloat16`/`float16` mixed precision, 4-bit / 8-bit quantization via `bitsandbytes` where hardware dictates.

## 4. Background: Generative CAD Literature
- **DeepCAD** (Wu et al., ICCV 2021): Pioneered sequence-of-commands representation for CAD. Limited to basic sketches and linear extrusions.
- **SkexGen** (Xu et al., NeurIPS 2022): Autoregressive generation of sketch-and-extrude sequences with separate sketch and extrusion transformers.
- **HNC-CAD** (Xu et al., SIGGRAPH 2023): Hierarchical neural representation for controllable CAD generation.
- **Fusion 360 Gallery Dataset** (Willis et al., ACM TOG 2021): Real-world CAD construction history and feature dependency trees.

## 5. Instruction-Driven Code Editing Literature
- **CodeEditorBench** (Guo et al., 2024) & **CanItEdit** (Cassano et al., 2023): Benchmark suites evaluating LLMs on bug fixing, feature addition, and refactoring. Highlight that localized editing outperforms full-file regeneration by reducing regression errors in unmodified sections.
- **Aider / Search-Replace Edit Blocks**:
  - Robust text-based patch format:
    ```
    <<<<<<< SEARCH
    original code line(s)
    =======
    updated code line(s)
    >>>>>>> REPLACE
    ```
  - Advantages over unified diff (`@@ -line,len +line,len @@`): Does not depend on fragile line-number drift; LLMs predict content matches far more accurately than calculating exact 1-indexed offset numbers.
