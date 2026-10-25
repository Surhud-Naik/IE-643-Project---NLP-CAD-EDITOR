"""
Built-in CAD examples for the Web interface.
Demonstrates diverse parametric operations: holes, fillets, chamfers, brackets, flanges, enclosures.
"""

from typing import List
from .schemas import ExampleItem

EXAMPLES: List[ExampleItem] = [
    ExampleItem(
        id="hole_widening",
        title="Mounting Plate Bore Expansion",
        category="Drill & Hole Operations",
        instruction="Widen the central mounting hole by 4 mm",
        description="A rectangular fixture plate with a central clearance hole through the thickness.",
        script="""import cadquery as cq

LENGTH = 60.0
WIDTH = 40.0
HEIGHT = 12.0
HOLE_DIA = 8.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .hole(HOLE_DIA)
)
"""
    ),
    ExampleItem(
        id="bushing_bore",
        title="Cylindrical Sleeve Bushing",
        category="Rotational Parts",
        instruction="Increase the inner bore radius by 2 mm",
        description="A cylindrical sleeve bushing with a precision concentric inner bore.",
        script="""import cadquery as cq

OUTER_RADIUS = 25.0
INNER_RADIUS = 12.0
HEIGHT = 35.0

result = (
    cq.Workplane("XY")
    .circle(OUTER_RADIUS)
    .circle(INNER_RADIUS)
    .extrude(HEIGHT)
)
"""
    ),
    ExampleItem(
        id="fillet_increase",
        title="Corner Filleted Block",
        category="Edge Treatments",
        instruction="Increase the top edge fillet radius to 6 mm",
        description="Machined solid block with corner blend radius to relieve stress concentrations.",
        script="""import cadquery as cq

LENGTH = 50.0
WIDTH = 30.0
HEIGHT = 20.0
FILLET_RADIUS = 3.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .edges()
    .fillet(FILLET_RADIUS)
)
"""
    ),
    ExampleItem(
        id="chamfer_adjustment",
        title="Beveled Guide Block",
        category="Edge Treatments",
        instruction="Increase the edge chamfer to 4 mm",
        description="Tooling block featuring lead-in edge chamfers for sliding alignment.",
        script="""import cadquery as cq

LENGTH = 45.0
WIDTH = 35.0
HEIGHT = 18.0
CHAMFER_DIST = 2.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .edges()
    .chamfer(CHAMFER_DIST)
)
"""
    ),
    ExampleItem(
        id="plate_resizing",
        title="4-Hole Base Flange Plate",
        category="Plate Patterns",
        instruction="Expand the plate width by 15 mm",
        description="Structural base plate with a 4-hole symmetric pattern for bolting.",
        script="""import cadquery as cq

LENGTH = 70.0
WIDTH = 50.0
HEIGHT = 8.0
HOLE_DIA = 6.0
PITCH_X = 25.0
PITCH_Y = 18.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces(">Z")
    .workplane()
    .rect(PITCH_X * 2, PITCH_Y * 2, forConstruction=True)
    .vertices()
    .hole(HOLE_DIA)
)
"""
    ),
    ExampleItem(
        id="bracket_extension",
        title="Structural L-Bracket",
        category="Structural Brackets",
        instruction="Make the horizontal bracket arm longer by 10 mm",
        description="Right-angle mounting bracket with base and upright vertical flanges.",
        script="""import cadquery as cq

ARM_LENGTH = 50.0
ARM_HEIGHT = 40.0
WIDTH = 30.0
THICKNESS = 6.0

result = (
    cq.Workplane("XY")
    .box(ARM_LENGTH, WIDTH, THICKNESS)
    .faces(">Z")
    .workplane()
    .transformed(offset=cq.Vector(-ARM_LENGTH / 2 + THICKNESS / 2, 0, 0))
    .box(THICKNESS, WIDTH, ARM_HEIGHT, combine=True)
)
"""
    ),
    ExampleItem(
        id="flange_expansion",
        title="Circular Bolt Flange",
        category="Flanges & Couplings",
        instruction="Increase the outer flange diameter by 10 mm",
        description="Circular pipe flange with a central bore and four bolt circle holes.",
        script="""import cadquery as cq

FLANGE_DIA = 60.0
BORE_DIA = 20.0
THICKNESS = 10.0
BOLT_CIRCLE_DIA = 42.0
BOLT_HOLE_DIA = 5.0

result = (
    cq.Workplane("XY")
    .circle(FLANGE_DIA / 2)
    .extrude(THICKNESS)
    .faces(">Z")
    .workplane()
    .hole(BORE_DIA)
    .faces(">Z")
    .workplane()
    .circle(BOLT_CIRCLE_DIA / 2)
    .vertices()
    .hole(BOLT_HOLE_DIA)
)
"""
    ),
    ExampleItem(
        id="shelled_enclosure",
        title="Electronics Enclosure Box",
        category="Enclosures & Housings",
        instruction="Make the enclosure wall thicker by 1 mm",
        description="Hollow electronics enclosure casing with open top and uniform shell thickness.",
        script="""import cadquery as cq

LENGTH = 55.0
WIDTH = 35.0
HEIGHT = 25.0
WALL_THICKNESS = 2.0

result = (
    cq.Workplane("XY")
    .box(LENGTH, WIDTH, HEIGHT)
    .faces("+Z")
    .shell(-WALL_THICKNESS)
)
"""
    )
]


def get_examples() -> List[ExampleItem]:
    return EXAMPLES
