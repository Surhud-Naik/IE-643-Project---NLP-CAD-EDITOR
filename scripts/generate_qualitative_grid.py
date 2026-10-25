#!/usr/bin/env python3
"""
Generates qualitative 2D grid figure displaying Original, Instruction, Predicted, and Ground Truth
for both success and failure editing cases.
Saves to outputs/figures/qualitative_grid.png.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from cadpatch.sandbox import execute_cadquery_sandbox
from cadpatch.demo.renderer import render_stl_to_image

CASES = [
    {
        "case_name": "Success: Dimensional Shift (Box Plate)",
        "instruction": "Increase base length to 85 mm and thickness to 20 mm.",
        "orig_code": """import cadquery as cq
LENGTH = 60.0
WIDTH = 40.0
THICKNESS = 15.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, THICKNESS)
""",
        "gt_code": """import cadquery as cq
LENGTH = 85.0
WIDTH = 40.0
THICKNESS = 20.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, THICKNESS)
""",
        "pred_code": """import cadquery as cq
LENGTH = 85.0
WIDTH = 40.0
THICKNESS = 20.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, THICKNESS)
"""
    },
    {
        "case_name": "Success: Bore Hole Resizing (Cylinder)",
        "instruction": "Expand the inner bore radius by 4 mm.",
        "orig_code": """import cadquery as cq
OUTER_RADIUS = 30.0
INNER_RADIUS = 12.0
HEIGHT = 40.0
result = cq.Workplane("XY").circle(OUTER_RADIUS).circle(INNER_RADIUS).extrude(HEIGHT)
""",
        "gt_code": """import cadquery as cq
OUTER_RADIUS = 30.0
INNER_RADIUS = 16.0
HEIGHT = 40.0
result = cq.Workplane("XY").circle(OUTER_RADIUS).circle(INNER_RADIUS).extrude(HEIGHT)
""",
        "pred_code": """import cadquery as cq
OUTER_RADIUS = 30.0
INNER_RADIUS = 16.0
HEIGHT = 40.0
result = cq.Workplane("XY").circle(OUTER_RADIUS).circle(INNER_RADIUS).extrude(HEIGHT)
"""
    },
    {
        "case_name": "Failure: Unintended Parameter Over-modification",
        "instruction": "Make the plate 10 mm longer.",
        "orig_code": """import cadquery as cq
LENGTH = 80.0
WIDTH = 50.0
THICKNESS = 10.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, THICKNESS)
""",
        "gt_code": """import cadquery as cq
LENGTH = 90.0
WIDTH = 50.0
THICKNESS = 10.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, THICKNESS)
""",
        # Erroneous prediction that modified width as well
        "pred_code": """import cadquery as cq
LENGTH = 90.0
WIDTH = 65.0
THICKNESS = 10.0
result = cq.Workplane("XY").box(LENGTH, WIDTH, THICKNESS)
"""
    }
]


def main():
    out_dir = os.path.join("outputs", "figures")
    os.makedirs(out_dir, exist_ok=True)
    temp_dir = os.path.join(out_dir, "temp_renders")
    os.makedirs(temp_dir, exist_ok=True)

    fig, axes = plt.subplots(len(CASES), 3, figsize=(12, 11), facecolor="#f8fafc")
    plt.suptitle("Qualitative Analysis: Predicted CAD Patches vs Ground Truth (IE 643)", fontsize=14, fontweight="bold", y=0.98)

    for row, c in enumerate(CASES):
        # 1. Render Orig
        r_orig = execute_cadquery_sandbox(c["orig_code"])
        p_orig = os.path.join(temp_dir, f"r{row}_orig.png")
        render_stl_to_image(r_orig["stl_bytes"], output_path=p_orig, color="#3b82f6", title="Original Model")

        # 2. Render Pred
        r_pred = execute_cadquery_sandbox(c["pred_code"])
        pred_color = "#10b981" if "Success" in c["case_name"] else "#ef4444"
        p_pred = os.path.join(temp_dir, f"r{row}_pred.png")
        render_stl_to_image(r_pred["stl_bytes"], output_path=p_pred, color=pred_color, title="Predicted Output")

        # 3. Render GT
        r_gt = execute_cadquery_sandbox(c["gt_code"])
        p_gt = os.path.join(temp_dir, f"r{row}_gt.png")
        render_stl_to_image(r_gt["stl_bytes"], output_path=p_gt, color="#8b5cf6", title="Ground Truth Target")

        # Plot into subplots
        img_orig = mpimg.imread(p_orig)
        img_pred = mpimg.imread(p_pred)
        img_gt = mpimg.imread(p_gt)

        axes[row, 0].imshow(img_orig)
        axes[row, 0].axis("off")
        axes[row, 0].set_title(f"Original\n({c['case_name'].split(':')[0]})", fontsize=10, fontweight="bold")

        axes[row, 1].imshow(img_pred)
        axes[row, 1].axis("off")
        axes[row, 1].set_title(f"Predicted Model\nInstruction: \"{c['instruction']}\"", fontsize=9, style="italic")

        axes[row, 2].imshow(img_gt)
        axes[row, 2].axis("off")
        axes[row, 2].set_title("Ground Truth Model\n(Target Geometry)", fontsize=10, fontweight="bold")

    plt.tight_layout()
    grid_out = os.path.join(out_dir, "qualitative_grid.png")
    plt.savefig(grid_out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved qualitative grid figure to: {grid_out}")


if __name__ == "__main__":
    main()
