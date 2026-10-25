"""
Off-screen 3D CAD mesh renderer using Matplotlib and Trimesh.
Renders watertight 3D perspective previews of CAD models to PNG images without requiring an OpenGL display server.
"""

from typing import Optional
import io
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import trimesh


def render_stl_to_image(
    stl_bytes: bytes,
    output_path: Optional[str] = None,
    color: str = "#3b82f6",
    elevation: float = 30,
    azimuth: float = -45,
    title: str = "3D CAD Solid"
) -> str:
    """
    Renders an STL byte stream to a shaded 3D isometric view saved as a PNG file.
    Returns the path to the rendered image.
    """
    if not stl_bytes or len(stl_bytes) == 0:
        return ""

    mesh = trimesh.load(io.BytesIO(stl_bytes), file_type="stl")
    vertices = mesh.vertices
    faces = mesh.faces

    fig = plt.figure(figsize=(5, 5), facecolor="#f8fafc")
    ax = fig.add_subplot(111, projection="3d", facecolor="#f8fafc")

    # Construct face polygons
    triangles = vertices[faces]
    poly = Poly3DCollection(
        triangles,
        facecolors=color,
        edgecolors="#1e293b",
        linewidths=0.2,
        alpha=0.9
    )
    ax.add_collection3d(poly)

    # Auto-scale bounding box
    min_b = vertices.min(axis=0)
    max_b = vertices.max(axis=0)
    center = (min_b + max_b) / 2.0
    max_range = (max_b - min_b).max() / 2.0

    ax.set_xlim(center[0] - max_range, center[0] + max_range)
    ax.set_ylim(center[1] - max_range, center[1] + max_range)
    ax.set_zlim(center[2] - max_range, center[2] + max_range)

    ax.view_init(elev=elevation, azim=azimuth)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.axis("off")

    if output_path is None:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        output_path = tmp.name
        tmp.close()

    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return output_path
