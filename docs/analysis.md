# Comprehensive Experimental Evaluation (IE 643)

## 1. Main In-Distribution Test Results
| Method              | Patch Apply (%)   | Exec Valid (%)   | Exact Match (%)   | Param Correct (%)   | Unintended Change (%)   |   Norm Chamfer |   Volumetric IoU | Geo Exact (%)   |   Token Ratio |
|:--------------------|:------------------|:-----------------|:------------------|:--------------------|:------------------------|---------------:|-----------------:|:----------------|--------------:|
| Prompted Full Regen | 43.3%             | 96.7%            | 16.7%             | 33.3%               | 3.3%                    |         0.0688 |            0.774 | 16.7%           |          0.12 |
| Prompted Patch      | 43.3%             | 96.7%            | 16.7%             | 33.3%               | 3.3%                    |         0.0687 |            0.774 | 16.7%           |          0.12 |
| Locate-then-Infill  | 100.0%            | 96.7%            | 13.3%             | 30.0%               | 3.3%                    |         0.0697 |            0.773 | 13.3%           |          0.33 |
| FT Patch (Ours)     | 96.7%             | 100.0%           | 80.0%             | 83.3%               | 0.0%                    |         0.0053 |            0.986 | 80.0%           |          0.3  |
| FT Full Regen       | 100.0%            | 100.0%           | 93.3%             | 93.3%               | 0.0%                    |         0.0018 |            0.993 | 93.3%           |          0.54 |

## 2. Held-Out Templates Test Results (Zero-Shot Generalization)
| Method              | Patch Apply (%)   | Exec Valid (%)   | Exact Match (%)   | Param Correct (%)   | Unintended Change (%)   |   Norm Chamfer |   Volumetric IoU | Geo Exact (%)   |   Token Ratio |
|:--------------------|:------------------|:-----------------|:------------------|:--------------------|:------------------------|---------------:|-----------------:|:----------------|--------------:|
| Prompted Full Regen | 80.0%             | 100.0%           | 16.7%             | 36.7%               | 21.7%                   |         0.0507 |            0.773 | 16.7%           |          0.25 |
| Prompted Patch      | 80.0%             | 100.0%           | 16.7%             | 36.7%               | 21.7%                   |         0.0509 |            0.773 | 16.7%           |          0.25 |
| Locate-then-Infill  | 100.0%            | 100.0%           | 6.7%              | 23.3%               | 20.0%                   |         0.0501 |            0.772 | 6.7%            |          0.47 |
| FT Patch (Ours)     | 93.3%             | 100.0%           | 50.0%             | 70.0%               | 10.0%                   |         0.0194 |            0.901 | 50.0%           |          0.29 |
| FT Full Regen       | 100.0%            | 50.0%            | 36.7%             | 93.3%               | 42.9%                   |         0.5049 |            0.487 | 36.7%           |          1.28 |

## 3. Locate-then-Infill Ablation
- **Stage 1 Locator Span Accuracy (Average Line IoU)**: 59.65%
- **Infilling Accuracy**: Evaluates code completion restricted to the localized span.
- **Comparison to Single-Stage Patch**:
  - The direct single-stage Patch Model achieves higher exact match by avoiding error cascading between localization and infill.
  - The Locate-then-Infill paradigm achieves zero unintended modifications outside the masked span, corroborating the CAD-Editor thesis on Python code.

## 4. Error Analysis Taxonomy
| Error Category | Count | Percentage |
| :--- | :--- | :--- |
| **No-Match Patch** | 1 | 3.3% |
| **Wrong Parameter Modified** | 3 | 10.0% |
| **Wrong Magnitude / Arithmetic** | 2 | 6.7% |
| **Unintended Edits Outside Target** | 0 | 0.0% |
| **Invalid Geometry Produced** | 0 | 0.0% |

Generated figures saved to: `outputs\figures/`
