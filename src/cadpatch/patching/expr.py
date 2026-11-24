"""
Safe AST-based arithmetic expression evaluation and parameter resolution utilities.
"""

from typing import Dict, Any, Optional, List, Tuple
import ast
import re
from cadpatch.eval.program_metrics import extract_top_level_params
from cadpatch.patching.patch import make_patch


ALLOWED_BIN_OPS = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
)

ALLOWED_UNARY_OPS = (
    ast.UAdd,
    ast.USub,
)


def _eval_ast_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ALLOWED_UNARY_OPS):
            raise ValueError(f"Disallowed unary operator: {type(node.op).__name__}")
        operand = _eval_ast_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ALLOWED_BIN_OPS):
            raise ValueError(f"Disallowed binary operator: {type(node.op).__name__}")
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left // right
        if isinstance(node.op, ast.Mod):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left % right
        if isinstance(node.op, ast.Pow):
            if abs(right) > 10 or abs(left) > 1e4:
                raise ValueError("Exponent or base too large for safe evaluation")
            return float(left ** right)

    raise ValueError(f"Disallowed or unsupported AST node: {type(node).__name__}")


def safe_eval_arithmetic(expr_str: str) -> Optional[float]:
    """
    Safely evaluates simple mathematical expressions using Python's AST parser in mode='eval'.
    Supports binary ops (+, -, *, /, //, %, **), unary ops (+, -), and numeric constants.
    Never uses eval(). Returns float value or None if invalid.
    """
    if not expr_str or not isinstance(expr_str, str):
        return None
    cleaned = expr_str.strip().rstrip(".").rstrip(",")
    if not cleaned:
        return None
    try:
        tree = ast.parse(cleaned, mode="eval")
        return _eval_ast_node(tree)
    except Exception:
        return None


def extract_numeric_expressions(text: str) -> List[Tuple[str, float]]:
    """
    Finds arithmetic expressions or numbers in text and evaluates them safely.
    Matches expressions like '10/2', '20 / 4', '4*2', '12-4', '5.5', '8'.
    Returns list of (matched_text, evaluated_float).
    """
    results: List[Tuple[str, float]] = []
    # Pattern to capture binary/unary arithmetic expressions and plain numbers
    pattern = r"\b\d+(?:\.\d+)?(?:\s*(?:[\+\*\/]|\-(?=\d|\s))\s*\d+(?:\.\d+)?)*\b"
    for match in re.finditer(pattern, text):
        expr = match.group(0).strip()
        val = safe_eval_arithmetic(expr)
        if val is not None:
            results.append((expr, val))
    return results


def resolve_parameter_target(clause: str, available_params: Dict[str, Any]) -> Optional[str]:
    """
    Resolves which parameter in available_params a natural-language clause refers to.
    Avoids keyword-order collisions (such as 'widen' incorrectly matching HOLE_DIA).
    """
    c_lower = clause.lower().strip()

    # 1. Exact match for parameter name or clean underscore-separated name
    for p in available_params:
        p_clean = p.lower().replace("_", " ")
        # Check as exact phrase or word
        if re.search(rf"\b{re.escape(p_clean)}\b", c_lower) or re.search(rf"\b{re.escape(p.lower())}\b", c_lower):
            return p

    # 2. Semantic category mappings with unambiguous keyword checks
    has_hole_kw = any(w in c_lower for w in ["hole", "bore", "drill"])
    has_fillet_kw = any(w in c_lower for w in ["fillet", "round", "rounding"])
    has_chamfer_kw = any(w in c_lower for w in ["chamfer", "bevel"])
    has_radius_kw = "radius" in c_lower
    has_dia_kw = any(w in c_lower for w in ["diameter", "dia"])
    has_width_kw = any(w in c_lower for w in ["width", "wide"]) or ("widen" in c_lower and not has_hole_kw)
    has_length_kw = any(w in c_lower for w in ["length", "longer", "lengthen", "extend"])
    has_height_kw = any(w in c_lower for w in ["height", "thickness", "thicker", "thinner", "tall", "depth"])
    has_margin_kw = any(w in c_lower for w in ["margin", "spacing", "offset", "pitch"])
    has_bolt_count_kw = any(w in c_lower for w in ["bolt count", "number of bolts", "bolts"])

    # Hole / Bore / Diameter
    if has_hole_kw or (has_dia_kw and not has_radius_kw):
        for candidate in ["HOLE_DIA", "HOLE_RADIUS", "INNER_RADIUS", "BORE_RADIUS", "DIAMETER"]:
            if candidate in available_params:
                return candidate

    # Inner vs Outer Radius
    if "inner" in c_lower and has_radius_kw:
        for candidate in ["INNER_RADIUS", "BORE_RADIUS", "HOLE_RADIUS"]:
            if candidate in available_params:
                return candidate
    if "outer" in c_lower and has_radius_kw:
        for candidate in ["OUTER_RADIUS", "CYL_RADIUS"]:
            if candidate in available_params:
                return candidate
    if has_radius_kw and not has_fillet_kw:
        for candidate in ["INNER_RADIUS", "HOLE_RADIUS", "OUTER_RADIUS", "RADIUS", "CYL_RADIUS"]:
            if candidate in available_params:
                return candidate

    # Fillet
    if has_fillet_kw:
        for candidate in ["FILLET_R", "FILLET_RADIUS", "FILLET", "CORNER_FILLET"]:
            if candidate in available_params:
                return candidate

    # Chamfer
    if has_chamfer_kw:
        for candidate in ["CHAMFER_D", "CHAMFER_DIST", "CHAMFER"]:
            if candidate in available_params:
                return candidate

    # Width
    if has_width_kw:
        for candidate in ["WIDTH", "BASE_WIDTH", "PLATE_WIDTH", "BOX_WIDTH", "W"]:
            if candidate in available_params:
                return candidate

    # Length
    if has_length_kw:
        for candidate in ["LENGTH", "BASE_LENGTH", "PLATE_LENGTH", "BOX_LENGTH", "L"]:
            if candidate in available_params:
                return candidate

    # Height / Thickness
    if has_height_kw:
        for candidate in ["HEIGHT", "THICKNESS", "BASE_HEIGHT", "PLATE_THICKNESS", "DEPTH", "H", "T"]:
            if candidate in available_params:
                return candidate

    # Margin / Spacing
    if has_margin_kw:
        for candidate in ["MARGIN", "SPACING", "PITCH"]:
            if candidate in available_params:
                return candidate

    # Bolt count
    if has_bolt_count_kw:
        for candidate in ["BOLT_COUNT", "HOLE_COUNT"]:
            if candidate in available_params:
                return candidate

    return None


def resolve_instruction_edits(script: str, instruction: str) -> Dict[str, Any]:
    """
    Parses a natural-language instruction and computes the exact parameter updates.
    Handles arithmetic expressions (e.g. '10/2'), relative and absolute edits,
    and multi-clause sentences ('increase length by 10/2 and reduce thickness by 2').
    Returns:
      {
        "success": bool,
        "updates": Dict[str, float],
        "edited_script": str,
        "patch": str,
        "error": Optional[str]
      }
    """
    params = extract_top_level_params(script)
    if not params:
        return {
            "success": False,
            "updates": {},
            "edited_script": script,
            "patch": "",
            "error": "No top-level parameters found in script"
        }

    # Split instruction into clauses across common conjunctions
    clauses = re.split(r"\b(?:and|while|simultaneously|,|;)\b", instruction, flags=re.IGNORECASE)
    clauses = [c.strip() for c in clauses if c.strip()]
    if not clauses:
        clauses = [instruction.strip()]

    matched_updates: Dict[str, float] = {}

    for clause in clauses:
        target_param = resolve_parameter_target(clause, params)
        if not target_param:
            continue

        old_val = float(params[target_param])
        c_lower = clause.lower()
        extracted = extract_numeric_expressions(clause)

        if "double" in c_lower or "twice" in c_lower:
            new_val = old_val * 2.0
        elif "halve" in c_lower or "half" in c_lower:
            new_val = max(1.0, old_val * 0.5)
        elif extracted:
            # Use the numeric expression
            delta = extracted[-1][1]  # value of the evaluated expression

            # Check if absolute assignment
            is_absolute = bool(re.search(r"\b(?:to|equal to|set)\b", c_lower)) and not bool(re.search(r"\b(?:by|add|scale)\b", c_lower))
            is_decrease = any(w in c_lower for w in ["reduce", "decrease", "shrink", "narrow", "thinner", "subtract", "shorten"])

            if is_absolute:
                new_val = delta
            elif is_decrease:
                new_val = max(1.0, old_val - abs(delta))
            else:
                new_val = old_val + abs(delta)
        else:
            # No number extracted for this clause
            continue

        matched_updates[target_param] = round(new_val, 3)

    if not matched_updates:
        return {
            "success": False,
            "updates": {},
            "edited_script": script,
            "patch": "",
            "error": "Could not identify parameter to edit from instruction."
        }

    # Generate edited script by updating assignments
    edited_script = script
    for param, new_v in matched_updates.items():
        v_str = f"{new_v:.1f}" if new_v == int(new_v) else f"{new_v:.3f}".rstrip("0").rstrip(".")
        pattern = rf"^(\s*{re.escape(param)}\s*=\s*)([\d\.\+\-\*\/]+)"
        # Line-by-line replacement to preserve indentation and comments
        lines = edited_script.splitlines()
        new_lines = []
        for line in lines:
            if re.match(pattern, line):
                new_line = re.sub(pattern, rf"\g<1>{v_str}", line)
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        edited_script = "\n".join(new_lines)
        if script.endswith("\n") and not edited_script.endswith("\n"):
            edited_script += "\n"

    patch = make_patch(script, edited_script)
    return {
        "success": True,
        "updates": matched_updates,
        "edited_script": edited_script,
        "patch": patch,
        "error": None
    }
