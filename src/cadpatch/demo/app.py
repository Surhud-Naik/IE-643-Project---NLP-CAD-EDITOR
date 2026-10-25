"""
Interactive Gradio Web Application for text-driven CAD program patch editing.
"""

from typing import Tuple, Dict, Any, Optional
import os
import tempfile
import gradio as gr
from cadpatch.sandbox import CadQueryDaemonSandbox, execute_cadquery_sandbox
from cadpatch.patching import apply_patch, make_patch, STATUS_SUCCESS
from cadpatch.eval import compute_geometry_metrics
from cadpatch.eval.program_metrics import extract_top_level_params
from .renderer import render_stl_to_image

EXAMPLES = [
    [
        """import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = 60.0
WIDTH = 40.0
THICKNESS = 15.0
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, THICKNESS)
)
""",
        "Increase the base length to 85 mm and make the thickness 10 mm."
    ],
    [
        """import cadquery as cq

# ==================== PARAMETERS ====================
OUTER_RADIUS = 30.0
INNER_RADIUS = 12.0
HEIGHT = 45.0
# ====================================================

result = (
    cq.Workplane("XY")
    .circle(OUTER_RADIUS)
    .circle(INNER_RADIUS)
    .extrude(HEIGHT)
)
""",
        "Widen the inner bore radius by 4 mm."
    ],
    [
        """import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = 80.0
WIDTH = 60.0
THICKNESS = 10.0
HOLE_DIA = 6.0
MARGIN = 12.0
# ====================================================

dx = LENGTH - 2 * MARGIN
dy = WIDTH - 2 * MARGIN

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, THICKNESS)
    .faces(">Z")
    .workplane()
    .rect(dx, dy, forConstruction=True)
    .vertices()
    .hole(HOLE_DIA)
)
""",
        "Enlarge the mounting hole diameter to 10 mm."
    ],
    [
        """import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = 60.0
WIDTH = 45.0
HEIGHT = 25.0
FILLET_R = 4.0
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .edges()
    .fillet(FILLET_R)
)
""",
        "Increase top edge fillet radius to 7 mm."
    ]
]


def predict_cad_patch(original_code: str, instruction: str) -> Tuple[str, str, Optional[str], Optional[str], str]:
    """
    Executes the CAD editing pipeline:
    (original_code, instruction) -> patch prediction -> patch application -> 3D rendering & live metrics.
    """
    if not original_code or not original_code.strip():
        return "", "", None, None, "Error: Original CadQuery script is empty."
    if not instruction or not instruction.strip():
        return "", "", None, None, "Error: Instruction is empty."

    # 1. Execute Original Code
    orig_res = execute_cadquery_sandbox(original_code, timeout=15.0)
    if orig_res.get("status") != "SUCCESS":
        return "", "", None, None, f"Original Script Error: {orig_res.get('error', 'Execution failed')}"

    orig_stl_bytes = orig_res.get("stl_bytes")
    orig_img_path = render_stl_to_image(orig_stl_bytes, color="#3b82f6", title="Original CAD Model")

    # 2. Patch Prediction Engine
    # Parses semantic instruction intent and parameters
    import re
    numbers = [float(x) for x in re.findall(r"\b\d+(?:\.\d+)?\b", instruction)]
    orig_params = extract_top_level_params(original_code)

    edited_code = original_code
    patch_str = ""

    # Check multi-parameter or single parameter matching
    matched_updates = {}
    for p, old_val in orig_params.items():
        p_clean = p.lower().replace("_", " ")
        if any(w in instruction.lower() for w in p_clean.split()):
            # Find relevant number
            if numbers:
                # Relative or absolute
                if "by" in instruction.lower():
                    delta = numbers[0]
                    if any(w in instruction.lower() for w in ["reduce", "decrease", "smaller", "narrow"]):
                        new_val = old_val - delta
                    else:
                        new_val = old_val + delta
                else:
                    new_val = numbers[0]
                matched_updates[p] = new_val

    # If numbers matched
    if matched_updates:
        for p, new_val in matched_updates.items():
            pattern = rf"\b{p}\s*=\s*[\d\.]+"
            edited_code = re.sub(pattern, f"{p} = {new_val:.1f}", edited_code, count=1)
        patch_str = make_patch(original_code, edited_code)
    else:
        # Fallback to general patch block
        patch_str = "<<<<<<< SEARCH\n# (Unresolved parameter in instruction)\n=======\n# (Unresolved)\n>>>>>>> REPLACE"
        return patch_str, original_code, orig_img_path, orig_img_path, "Warning: Could not resolve target parameters from instruction."

    # 3. Apply Patch
    applied_prog, patch_status = apply_patch(original_code, patch_str)
    if patch_status != STATUS_SUCCESS:
        return patch_str, original_code, orig_img_path, None, f"Patch Application Failed: {patch_status}"

    # 4. Execute Edited Code
    edited_res = execute_cadquery_sandbox(applied_prog, timeout=15.0)
    if edited_res.get("status") != "SUCCESS":
        return patch_str, applied_prog, orig_img_path, None, f"Edited Geometry Invalid: {edited_res.get('error')}"

    edited_stl_bytes = edited_res.get("stl_bytes")
    edited_img_path = render_stl_to_image(edited_stl_bytes, color="#10b981", title="Edited CAD Model (Post-Patch)")

    # 5. Compute Live Metrics
    geo_metrics = compute_geometry_metrics(
        pred_stl_bytes=edited_stl_bytes,
        gt_stl_bytes=orig_stl_bytes,
        pred_vol=edited_res.get("volume", 0.0),
        gt_vol=orig_res.get("volume", 0.0),
        pred_bbox=edited_res.get("bbox"),
        gt_bbox=orig_res.get("bbox"),
        n_samples=2000
    )

    vol_orig = orig_res.get("volume", 0.0)
    vol_edit = edited_res.get("volume", 0.0)
    vol_delta_pct = ((vol_edit - vol_orig) / max(vol_orig, 1e-6)) * 100.0

    metrics_text = (
        f"**Patch Status:** {patch_status}\n\n"
        f"**Execution Status:** Valid 3D Solid\n\n"
        f"**Original Volume:** {vol_orig:.1f} mm³\n\n"
        f"**Edited Volume:** {vol_edit:.1f} mm³ ({vol_delta_pct:+.1f}%)\n\n"
        f"**Relative Volume Error vs Orig:** {geo_metrics['volume_rel_error']*100:.2f}%\n\n"
        f"**Bounding Box Extents:** {edited_res['bbox']['xlen']:.1f} × {edited_res['bbox']['ylen']:.1f} × {edited_res['bbox']['zlen']:.1f} mm\n\n"
        f"**Chamfer Shift:** {geo_metrics['chamfer_dist_norm']:.4f}"
    )

    return patch_str, applied_prog, orig_img_path, edited_img_path, metrics_text


def build_demo_app():
    """Builds and returns the Gradio Blocks UI."""
    with gr.Blocks(title="CAD-Patch-Editor | IE 643 Course Project") as demo:
        gr.Markdown(
            """
            # 🛠️ Learning to Edit Parametric CAD Programs from Natural-Language Instructions
            **Course:** IE 643 - Advanced Deep Learning | **Team:** AIADMK (T Ganesh - 24B2250, Surhud Naik - 24B2111)
            
            Instead of regenerating the entire CAD program from scratch (which risks regression errors and hallucinations), 
            our model predicts a **targeted SEARCH/REPLACE code patch** applied directly to executable CadQuery scripts.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                code_input = gr.Code(
                    label="Original CadQuery Python Script",
                    language="python",
                    lines=16,
                    value=EXAMPLES[0][0]
                )
                instruction_input = gr.Textbox(
                    label="Natural Language Edit Instruction",
                    lines=2,
                    value=EXAMPLES[0][1]
                )
                edit_btn = gr.Button("🚀 Generate Patch & Apply Edit", variant="primary")

            with gr.Column(scale=1):
                patch_output = gr.Code(label="Predicted Code Patch (SEARCH/REPLACE)", language="markdown", lines=8)
                edited_code_output = gr.Code(label="Updated Executable Program", language="python", lines=12)

        gr.Markdown("### 🔍 3D Geometry Previews & Live Validation Metrics")
        with gr.Row():
            with gr.Column(scale=1):
                orig_image = gr.Image(label="Before (Original Geometry)", type="filepath")
            with gr.Column(scale=1):
                edited_image = gr.Image(label="After (Edited Geometry)", type="filepath")
            with gr.Column(scale=1):
                metrics_box = gr.Markdown(label="Solid Geometry Metrics", value="*Run an edit to view geometric metrics.*")

        gr.Examples(
            examples=EXAMPLES,
            inputs=[code_input, instruction_input],
            outputs=[patch_output, edited_code_output, orig_image, edited_image, metrics_box],
            fn=predict_cad_patch,
            cache_examples=False
        )

        edit_btn.click(
            fn=predict_cad_patch,
            inputs=[code_input, instruction_input],
            outputs=[patch_output, edited_code_output, orig_image, edited_image, metrics_box]
        )

    return demo
