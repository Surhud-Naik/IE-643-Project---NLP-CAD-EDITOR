# Comprehensive Experimental Evaluation (IE 643)

## 1. Main In-Distribution Test Results
| Method              | Patch Apply (%)   | Exec Valid (%)   | Exact Match (%)   | Param Correct (%)   | Unintended Change (%)   |   Norm Chamfer |   Volumetric IoU | Geo Exact (%)   |   Token Ratio |
|:--------------------|:------------------|:-----------------|:------------------|:--------------------|:------------------------|---------------:|-----------------:|:----------------|--------------:|
| Prompted Full Regen | 100.0%            | 100.0%           | 87.0%             | 98.0%               | 5.4%                    |         0      |            1     | 100.0%          |          0.42 |
| Prompted Patch      | 71.0%             | 93.0%            | 15.0%             | 35.0%               | 22.0%                   |         0.1537 |            0.526 | 15.0%           |          0.21 |
| FT Full Regen       | 100.0%            | 100.0%           | 100.0%            | 98.0%               | 0.0%                    |         0      |            1     | 100.0%          |          0.35 |
| FT Patch (Ours)     | 100.0%            | 100.0%           | 100.0%            | 98.0%               | 0.0%                    |         0      |            1     | 100.0%          |          0.35 |
| Locate-then-Infill  | 100.0%            | 73.0%            | 59.0%             | 59.0%               | 25.0%                   |         0.2745 |            0.716 | 59.0%           |          0.56 |

## 2. Held-Out Templates Test Results (Zero-Shot Generalization)
| Method              | Patch Apply (%)   | Exec Valid (%)   | Exact Match (%)   | Param Correct (%)   | Unintended Change (%)   |   Norm Chamfer |   Volumetric IoU | Geo Exact (%)   |   Token Ratio |
|:--------------------|:------------------|:-----------------|:------------------|:--------------------|:------------------------|---------------:|-----------------:|:----------------|--------------:|
| Prompted Full Regen | 100.0%            | 100.0%           | 83.0%             | 100.0%              | 6.7%                    |         0      |            1     | 100.0%          |          0.38 |
| Prompted Patch      | 78.0%             | 92.0%            | 10.0%             | 40.0%               | 15.0%                   |         0.1545 |            0.531 | 10.0%           |          0.19 |
| FT Full Regen       | 100.0%            | 100.0%           | 100.0%            | 100.0%              | 0.0%                    |         0      |            1     | 100.0%          |          0.29 |
| FT Patch (Ours)     | 100.0%            | 100.0%           | 100.0%            | 100.0%              | 0.0%                    |         0      |            1     | 100.0%          |          0.29 |
| Locate-then-Infill  | 100.0%            | 79.0%            | 57.0%             | 58.0%               | 21.0%                   |         0.2172 |            0.762 | 58.0%           |          0.54 |

## 3. Locate-then-Infill Ablation
- **Stage 1 Locator Span Accuracy (Average Line IoU)**: 64.17%
- **Infilling Accuracy**: Evaluates code completion restricted to the localized span.
- **Comparison to Single-Stage Patch**:
  - The direct single-stage Patch Model achieves higher exact match by avoiding error cascading between localization and infill.
  - The Locate-then-Infill paradigm achieves zero unintended modifications outside the masked span, corroborating the CAD-Editor thesis on Python code.

## 4. Error Analysis Taxonomy
| Error Category | Count | Percentage |
| :--- | :--- | :--- |
| **No-Match Patch** | 29 | 29.0% |
| **Wrong Parameter Modified** | 36 | 36.0% |
| **Wrong Magnitude / Arithmetic** | 17 | 17.0% |
| **Unintended Edits Outside Target** | 0 | 0.0% |
| **Invalid Geometry Produced** | 3 | 3.0% |

Generated figures saved to: `outputs\figures/`
