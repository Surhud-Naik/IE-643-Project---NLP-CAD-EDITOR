"""
Catalog of 10 parametric CadQuery templates spanning standard mechanical engineering primitives.
"""

from typing import Dict, Any, List
import math
from .base import CADTemplate, register_template

# 1. Plain Extrude Plate
def _gen_box_plate(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = {params['LENGTH']:.1f}
WIDTH = {params['WIDTH']:.1f}
THICKNESS = {params['THICKNESS']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, THICKNESS)
)
"""

TEMPLATE_BOX_PLATE = CADTemplate(
    name="box_plate",
    category="extrude",
    param_specs={
        "LENGTH": (30.0, 100.0, 60.0),
        "WIDTH": (20.0, 80.0, 40.0),
        "THICKNESS": (5.0, 30.0, 15.0),
    },
    semantic_names={
        "LENGTH": ["length", "base length", "longitudinal dimension", "span"],
        "WIDTH": ["width", "breadth", "lateral dimension"],
        "THICKNESS": ["thickness", "height", "depth", "plate gauge"],
    },
    code_generator=_gen_box_plate,
    constraints_fn=lambda p: p["LENGTH"] >= p["WIDTH"] >= p["THICKNESS"] >= 4.0
)

# 2. Cylinder Bushing with Through-Hole
def _gen_cylinder_bushing(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
OUTER_RADIUS = {params['OUTER_RADIUS']:.1f}
INNER_RADIUS = {params['INNER_RADIUS']:.1f}
HEIGHT = {params['HEIGHT']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .circle(OUTER_RADIUS)
    .circle(INNER_RADIUS)
    .extrude(HEIGHT)
)
"""

TEMPLATE_CYLINDER_BUSHING = CADTemplate(
    name="cylinder_bushing",
    category="hole_cut",
    param_specs={
        "OUTER_RADIUS": (15.0, 50.0, 30.0),
        "INNER_RADIUS": (5.0, 20.0, 12.0),
        "HEIGHT": (20.0, 80.0, 45.0),
    },
    semantic_names={
        "OUTER_RADIUS": ["outer radius", "external diameter radius", "outer cylindrical radius"],
        "INNER_RADIUS": ["inner bore radius", "hole radius", "central aperture radius", "bore radius"],
        "HEIGHT": ["cylinder height", "axial length", "standoff height", "overall height"],
    },
    code_generator=_gen_cylinder_bushing,
    constraints_fn=lambda p: (p["OUTER_RADIUS"] - p["INNER_RADIUS"] >= 5.0) and (p["HEIGHT"] >= 10.0)
)

# 3. Plate with 4 Corner Mounting Holes
def _gen_pattern_plate(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = {params['LENGTH']:.1f}
WIDTH = {params['WIDTH']:.1f}
THICKNESS = {params['THICKNESS']:.1f}
HOLE_DIA = {params['HOLE_DIA']:.1f}
MARGIN = {params['MARGIN']:.1f}
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
"""

TEMPLATE_PATTERN_PLATE = CADTemplate(
    name="pattern_plate",
    category="pattern",
    param_specs={
        "LENGTH": (60.0, 120.0, 80.0),
        "WIDTH": (40.0, 90.0, 60.0),
        "THICKNESS": (6.0, 20.0, 10.0),
        "HOLE_DIA": (4.0, 12.0, 6.0),
        "MARGIN": (8.0, 20.0, 12.0),
    },
    semantic_names={
        "LENGTH": ["plate length", "base length", "overall length"],
        "WIDTH": ["plate width", "base width", "overall width"],
        "THICKNESS": ["plate thickness", "base thickness"],
        "HOLE_DIA": ["mounting hole diameter", "corner hole size", "bolt hole diameter"],
        "MARGIN": ["corner margin", "edge offset", "hole setback distance"],
    },
    code_generator=_gen_pattern_plate,
    constraints_fn=lambda p: (
        (p["LENGTH"] - 2 * p["MARGIN"] >= p["HOLE_DIA"] + 10.0) and
        (p["WIDTH"] - 2 * p["MARGIN"] >= p["HOLE_DIA"] + 10.0) and
        (p["MARGIN"] >= p["HOLE_DIA"] / 2.0 + 3.0)
    )
)

# 4. Filleted Prismatic Block
def _gen_filleted_block(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    has_fillet = feat.get("has_fillet", True)
    if has_fillet:
        return f"""import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = {params['LENGTH']:.1f}
WIDTH = {params['WIDTH']:.1f}
HEIGHT = {params['HEIGHT']:.1f}
FILLET_R = {params['FILLET_R']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .edges()
    .fillet(FILLET_R)
)
"""
    else:
        return f"""import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = {params['LENGTH']:.1f}
WIDTH = {params['WIDTH']:.1f}
HEIGHT = {params['HEIGHT']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
)
"""

TEMPLATE_FILLETED_BLOCK = CADTemplate(
    name="filleted_block",
    category="fillet",
    param_specs={
        "LENGTH": (40.0, 90.0, 60.0),
        "WIDTH": (30.0, 70.0, 45.0),
        "HEIGHT": (15.0, 40.0, 25.0),
        "FILLET_R": (2.0, 8.0, 4.0),
    },
    semantic_names={
        "LENGTH": ["block length", "base length"],
        "WIDTH": ["block width", "base width"],
        "HEIGHT": ["block height", "extrusion thickness"],
        "FILLET_R": ["top edge fillet radius", "rounding radius", "edge blend radius", "fillet"],
    },
    code_generator=_gen_filleted_block,
    constraints_fn=lambda p: p["FILLET_R"] <= min(p["LENGTH"], p["WIDTH"], p["HEIGHT"]) / 3.0,
    feature_flags={"has_fillet": True}
)

# 5. Chamfered Prismatic Block
def _gen_chamfered_block(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    has_chamfer = feat.get("has_chamfer", True)
    if has_chamfer:
        return f"""import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = {params['LENGTH']:.1f}
WIDTH = {params['WIDTH']:.1f}
HEIGHT = {params['HEIGHT']:.1f}
CHAMFER_D = {params['CHAMFER_D']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .edges()
    .chamfer(CHAMFER_D)
)
"""
    else:
        return f"""import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = {params['LENGTH']:.1f}
WIDTH = {params['WIDTH']:.1f}
HEIGHT = {params['HEIGHT']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
)
"""

TEMPLATE_CHAMFERED_BLOCK = CADTemplate(
    name="chamfered_block",
    category="chamfer",
    param_specs={
        "LENGTH": (40.0, 90.0, 60.0),
        "WIDTH": (30.0, 70.0, 45.0),
        "HEIGHT": (20.0, 50.0, 30.0),
        "CHAMFER_D": (2.0, 7.0, 3.5),
    },
    semantic_names={
        "LENGTH": ["block length", "base length"],
        "WIDTH": ["block width", "base width"],
        "HEIGHT": ["block height", "thickness"],
        "CHAMFER_D": ["chamfer size", "bevel width", "edge chamfer distance", "chamfer"],
    },
    code_generator=_gen_chamfered_block,
    constraints_fn=lambda p: p["CHAMFER_D"] <= min(p["LENGTH"], p["WIDTH"], p["HEIGHT"]) / 3.5,
    feature_flags={"has_chamfer": True}
)

# 6. L-Bracket Structural Mount
def _gen_l_bracket(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
BASE_LEN = {params['BASE_LEN']:.1f}
UPRIGHT_H = {params['UPRIGHT_H']:.1f}
WIDTH = {params['WIDTH']:.1f}
THICKNESS = {params['THICKNESS']:.1f}
HOLE_DIA = {params['HOLE_DIA']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(BASE_LEN, WIDTH, THICKNESS, centered=(False, True, False))
    .union(
        cq.Workplane("XY")
        .box(THICKNESS, WIDTH, UPRIGHT_H, centered=(False, True, False))
    )
    .faces(">Z")
    .workplane()
    .center(BASE_LEN / 2.0, 0)
    .hole(HOLE_DIA)
)
"""

TEMPLATE_L_BRACKET = CADTemplate(
    name="l_bracket",
    category="boolean",
    param_specs={
        "BASE_LEN": (40.0, 90.0, 60.0),
        "UPRIGHT_H": (40.0, 90.0, 50.0),
        "WIDTH": (25.0, 60.0, 35.0),
        "THICKNESS": (5.0, 15.0, 8.0),
        "HOLE_DIA": (4.0, 10.0, 6.0),
    },
    semantic_names={
        "BASE_LEN": ["base foot length", "horizontal flange length", "bracket base length"],
        "UPRIGHT_H": ["vertical leg height", "upright wall height", "bracket height"],
        "WIDTH": ["bracket width", "face width"],
        "THICKNESS": ["bracket wall thickness", "flange thickness"],
        "HOLE_DIA": ["base mounting hole diameter", "fastener hole size"],
    },
    code_generator=_gen_l_bracket,
    constraints_fn=lambda p: (
        p["THICKNESS"] <= min(p["BASE_LEN"], p["UPRIGHT_H"]) / 2.5 and
        p["HOLE_DIA"] <= min(p["WIDTH"], p["BASE_LEN"]) / 2.0
    )
)

# 7. Flange with Bolt Circle Pattern
def _gen_flange_disc(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    bolt_count = int(params.get("BOLT_COUNT", 4))
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
FLANGE_DIA = {params['FLANGE_DIA']:.1f}
BORE_DIA = {params['BORE_DIA']:.1f}
THICKNESS = {params['THICKNESS']:.1f}
BOLT_CIRCLE_DIA = {params['BOLT_CIRCLE_DIA']:.1f}
BOLT_DIA = {params['BOLT_DIA']:.1f}
BOLT_COUNT = {bolt_count}
# ====================================================

result = (
    cq.Workplane("XY")
    .circle(FLANGE_DIA / 2.0)
    .extrude(THICKNESS)
    .faces(">Z")
    .workplane()
    .hole(BORE_DIA)
    .faces(">Z")
    .workplane()
    .polarArray(BOLT_CIRCLE_DIA / 2.0, 0, 360, BOLT_COUNT)
    .hole(BOLT_DIA)
)
"""

TEMPLATE_FLANGE_DISC = CADTemplate(
    name="flange_disc",
    category="flange",
    param_specs={
        "FLANGE_DIA": (70.0, 140.0, 100.0),
        "BORE_DIA": (20.0, 40.0, 25.0),
        "THICKNESS": (8.0, 25.0, 12.0),
        "BOLT_CIRCLE_DIA": (45.0, 95.0, 65.0),
        "BOLT_DIA": (4.0, 10.0, 6.0),
        "BOLT_COUNT": (4.0, 8.0, 4.0),
    },
    semantic_names={
        "FLANGE_DIA": ["flange outer diameter", "disc diameter", "overall diameter"],
        "BORE_DIA": ["central bore diameter", "pipe bore", "center hole diameter"],
        "THICKNESS": ["flange thickness", "disc thickness"],
        "BOLT_CIRCLE_DIA": ["bolt circle diameter", "pitch circle diameter (PCD)"],
        "BOLT_DIA": ["bolt hole diameter", "stud hole size"],
        "BOLT_COUNT": ["number of bolt holes", "bolt count"],
    },
    code_generator=_gen_flange_disc,
    constraints_fn=lambda p: (
        p["BORE_DIA"] + 12.0 <= p["BOLT_CIRCLE_DIA"] <= p["FLANGE_DIA"] - 14.0 and
        p["BOLT_DIA"] <= 12.0
    )
)

# 8. Shelled Hollow Enclosure Box
def _gen_shelled_box(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
LENGTH = {params['LENGTH']:.1f}
WIDTH = {params['WIDTH']:.1f}
HEIGHT = {params['HEIGHT']:.1f}
WALL_THICK = {params['WALL_THICK']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces("+Z")
    .shell(-WALL_THICK)
)
"""

TEMPLATE_SHELLED_BOX = CADTemplate(
    name="shelled_box",
    category="shell",
    param_specs={
        "LENGTH": (40.0, 100.0, 70.0),
        "WIDTH": (30.0, 80.0, 50.0),
        "HEIGHT": (20.0, 50.0, 30.0),
        "WALL_THICK": (2.0, 6.0, 3.0),
    },
    semantic_names={
        "LENGTH": ["enclosure length", "outer box length"],
        "WIDTH": ["enclosure width", "outer box width"],
        "HEIGHT": ["enclosure depth", "box height", "overall height"],
        "WALL_THICK": ["enclosure wall thickness", "casing shell thickness"],
    },
    code_generator=_gen_shelled_box,
    constraints_fn=lambda p: p["WALL_THICK"] <= min(p["LENGTH"], p["WIDTH"], p["HEIGHT"]) / 4.0
)

# 9. Slotted Plate
def _gen_slotted_plate(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
PLATE_LEN = {params['PLATE_LEN']:.1f}
PLATE_WID = {params['PLATE_WID']:.1f}
PLATE_THICK = {params['PLATE_THICK']:.1f}
SLOT_LEN = {params['SLOT_LEN']:.1f}
SLOT_WID = {params['SLOT_WID']:.1f}
# ====================================================

result = (
    cq.Workplane("XY")
    .box(PLATE_LEN, PLATE_WID, PLATE_THICK)
    .faces(">Z")
    .workplane()
    .slot2D(SLOT_LEN, SLOT_WID)
    .cutThruAll()
)
"""

TEMPLATE_SLOTTED_PLATE = CADTemplate(
    name="slotted_plate",
    category="slot",
    param_specs={
        "PLATE_LEN": (60.0, 120.0, 80.0),
        "PLATE_WID": (40.0, 80.0, 50.0),
        "PLATE_THICK": (6.0, 18.0, 10.0),
        "SLOT_LEN": (20.0, 50.0, 35.0),
        "SLOT_WID": (6.0, 16.0, 10.0),
    },
    semantic_names={
        "PLATE_LEN": ["guide plate length", "base length"],
        "PLATE_WID": ["guide plate width", "base width"],
        "PLATE_THICK": ["guide plate thickness", "plate gauge"],
        "SLOT_LEN": ["central slot length", "elongated slot length"],
        "SLOT_WID": ["slot aperture width", "slot opening width"],
    },
    code_generator=_gen_slotted_plate,
    constraints_fn=lambda p: (
        p["SLOT_LEN"] <= p["PLATE_LEN"] - 18.0 and
        p["SLOT_WID"] <= p["PLATE_WID"] - 18.0 and
        p["SLOT_LEN"] >= p["SLOT_WID"] + 4.0
    )
)

# 10. Revolved V-Groove Pulley
def _gen_revolve_pulley(params: Dict[str, float], feat: Dict[str, Any]) -> str:
    return f"""import cadquery as cq

# ==================== PARAMETERS ====================
OUTER_RADIUS = {params['OUTER_RADIUS']:.1f}
BORE_RADIUS = {params['BORE_RADIUS']:.1f}
WIDTH = {params['WIDTH']:.1f}
GROOVE_DEPTH = {params['GROOVE_DEPTH']:.1f}
GROOVE_WIDTH = {params['GROOVE_WIDTH']:.1f}
# ====================================================

r_inner = OUTER_RADIUS - GROOVE_DEPTH
w_half = WIDTH / 2.0
gw_half = GROOVE_WIDTH / 2.0

pts = [
    (BORE_RADIUS, -w_half),
    (OUTER_RADIUS, -w_half),
    (OUTER_RADIUS, -gw_half),
    (r_inner, 0.0),
    (OUTER_RADIUS, gw_half),
    (OUTER_RADIUS, w_half),
    (BORE_RADIUS, w_half),
]

result = (
    cq.Workplane("XZ")
    .polyline(pts)
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)
"""

TEMPLATE_REVOLVE_PULLEY = CADTemplate(
    name="revolve_pulley",
    category="revolve",
    param_specs={
        "OUTER_RADIUS": (35.0, 65.0, 45.0),
        "BORE_RADIUS": (6.0, 14.0, 10.0),
        "WIDTH": (18.0, 35.0, 24.0),
        "GROOVE_DEPTH": (4.0, 8.0, 5.0),
        "GROOVE_WIDTH": (5.0, 12.0, 8.0),
    },
    semantic_names={
        "OUTER_RADIUS": ["pulley outer radius", "sheave pitch radius", "wheel radius"],
        "BORE_RADIUS": ["shaft bore radius", "center axle radius", "mounting bore radius"],
        "WIDTH": ["pulley face width", "overall rim width", "sheave width"],
        "GROOVE_DEPTH": ["V-groove notch depth", "belt groove depth"],
        "GROOVE_WIDTH": ["V-groove top width", "belt slot width"],
    },
    code_generator=_gen_revolve_pulley,
    constraints_fn=lambda p: (
        p["BORE_RADIUS"] + 8.0 <= p["OUTER_RADIUS"] - p["GROOVE_DEPTH"] and
        p["GROOVE_WIDTH"] <= p["WIDTH"] - 4.0
    )
)

# Register all 10 templates
ALL_TEMPLATES = [
    TEMPLATE_BOX_PLATE,
    TEMPLATE_CYLINDER_BUSHING,
    TEMPLATE_PATTERN_PLATE,
    TEMPLATE_FILLETED_BLOCK,
    TEMPLATE_CHAMFERED_BLOCK,
    TEMPLATE_L_BRACKET,
    TEMPLATE_FLANGE_DISC,
    TEMPLATE_SHELLED_BOX,
    TEMPLATE_SLOTTED_PLATE,
    TEMPLATE_REVOLVE_PULLEY,
]

for t in ALL_TEMPLATES:
    register_template(t)
