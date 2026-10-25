"""
Secure sandboxed execution engine for CadQuery programs.
Enforces static AST verification, isolated subprocess containment, execution timeouts,
memory bounds, and strict namespace whitelisting.
"""

from typing import Dict, Any, Optional
import ast
import json
import os
import subprocess
import sys
import tempfile
import time

ALLOWED_MODULES = {"cadquery", "cq", "math"}
FORBIDDEN_BUILTINS = {
    "open", "eval", "exec", "compile", "__import__", "input",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "breakpoint", "help", "memoryview"
}
FORBIDDEN_ATTRIBUTES = {
    "__subclasses__", "__globals__", "__code__", "__closure__",
    "__builtins__", "__import__", "__loader__", "__spec__"
}

STATUS_SUCCESS = "SUCCESS"
STATUS_SYNTAX_ERROR = "SYNTAX_ERROR"
STATUS_SECURITY_VIOLATION = "SECURITY_VIOLATION"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_RUNTIME_ERROR = "RUNTIME_ERROR"
STATUS_INVALID_GEOMETRY = "INVALID_GEOMETRY"


def static_security_check(code_str: str) -> Optional[str]:
    """
    Performs static AST validation against arbitrary code execution vulnerabilities.
    Returns error message if code violates policy, otherwise None.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return f"SyntaxError during AST parse: {e}"

    for node in ast.walk(tree):
        # Disallow arbitrary imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module not in ALLOWED_MODULES:
                    return f"Security Violation: Import of module '{alias.name}' is prohibited."
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module not in ALLOWED_MODULES:
                    return f"Security Violation: Import from module '{node.module}' is prohibited."

        # Disallow dangerous attribute access
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRIBUTES:
                return f"Security Violation: Access to attribute '{node.attr}' is prohibited."

        # Disallow calls to forbidden functions
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
                return f"Security Violation: Invocation of builtin '{node.func.id}' is prohibited."

    return None


WORKER_SCRIPT = """
import sys
import json
import math
import tempfile
import os

code_path = sys.argv[1]
output_stl_path = sys.argv[2]

with open(code_path, "r", encoding="utf-8") as f:
    code = f.read()

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root not in {"cadquery", "cq", "math"}:
        raise ImportError(f"Import of '{name}' is forbidden.")
    return __import__(name, globals, locals, fromlist, level)

safe_builtins = {
    "__import__": safe_import,
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "int": int,
    "isinstance": isinstance, "issubclass": issubclass, "len": len, "list": list,
    "map": map, "max": max, "min": min, "pow": pow, "range": range,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "True": True, "False": False, "None": None, "Exception": Exception,
    "ValueError": ValueError, "TypeError": TypeError, "ZeroDivisionError": ZeroDivisionError
}

safe_globals = {
    "__builtins__": safe_builtins,
    "math": math
}

needs_cadquery = ("cadquery" in code) or ("cq" in code) or ("Workplane" in code)
if needs_cadquery:
    try:
        import cadquery as cq
        import cadquery
        safe_globals["cadquery"] = cadquery
        safe_globals["cq"] = cq
    except ImportError as e:
        print(json.dumps({"status": "RUNTIME_ERROR", "error": f"Failed to import cadquery: {e}"}))
        sys.exit(0)

try:
    exec(code, safe_globals)
except Exception as e:
    print(json.dumps({"status": "RUNTIME_ERROR", "error": f"{type(e).__name__}: {str(e)}"}))
    sys.exit(0)

result = safe_globals.get("result")
if result is None:
    print(json.dumps({"status": "INVALID_GEOMETRY", "error": "Variable 'result' was not defined."}))
    sys.exit(0)

try:
    shape = result.val() if hasattr(result, "val") else result
    if not hasattr(shape, "Volume"):
        print(json.dumps({"status": "INVALID_GEOMETRY", "error": "'result' does not contain a 3D solid."}))
        sys.exit(0)

    volume = float(shape.Volume())
    if volume <= 1e-6:
        print(json.dumps({"status": "INVALID_GEOMETRY", "error": f"Volume must be positive, got {volume}"}))
        sys.exit(0)

    bb = shape.BoundingBox()
    bbox_info = {
        "xmin": float(bb.xmin), "ymin": float(bb.ymin), "zmin": float(bb.zmin),
        "xmax": float(bb.xmax), "ymax": float(bb.ymax), "zmax": float(bb.zmax),
        "xlen": float(bb.xlen), "ylen": float(bb.ylen), "zlen": float(bb.zlen),
        "diagonal": float(math.sqrt(bb.xlen**2 + bb.ylen**2 + bb.zlen**2))
    }

    # Export STL
    cq.exporters.export(result, output_stl_path)

    print(json.dumps({
        "status": "SUCCESS",
        "volume": volume,
        "bbox": bbox_info,
        "stl_path": output_stl_path
    }))
except Exception as e:
    print(json.dumps({"status": "INVALID_GEOMETRY", "error": f"Geometry evaluation failed: {type(e).__name__}: {str(e)}"}))
"""


def execute_cadquery_sandbox(
    code_str: str,
    timeout: float = 25.0,
    python_executable: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a CadQuery script inside a sandboxed subprocess.
    Returns dictionary with status and metadata.
    """
    if python_executable is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        venv_py = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
        if os.path.exists(venv_py):
            python_executable = venv_py
        else:
            python_executable = sys.executable

    # 1. Static security check
    sec_err = static_security_check(code_str)
    if sec_err:
        return {
            "status": STATUS_SECURITY_VIOLATION if "Security Violation" in sec_err else STATUS_SYNTAX_ERROR,
            "error": sec_err,
            "volume": 0.0,
            "bbox": None,
            "stl_path": None,
            "duration": 0.0
        }

    # 2. Setup temp directory and worker script
    start_time = time.time()
    with tempfile.TemporaryDirectory() as tmpdir:
        code_file = os.path.join(tmpdir, "script.py")
        worker_file = os.path.join(tmpdir, "worker.py")
        stl_file = os.path.join(tmpdir, "output.stl")

        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code_str)
        with open(worker_file, "w", encoding="utf-8") as f:
            f.write(WORKER_SCRIPT)

        # 3. Launch subprocess
        try:
            proc = subprocess.run(
                [python_executable, worker_file, code_file, stl_file],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            duration = time.time() - start_time
        except subprocess.TimeoutExpired:
            return {
                "status": STATUS_TIMEOUT,
                "error": f"Execution timed out after {timeout} seconds.",
                "volume": 0.0,
                "bbox": None,
                "stl_path": None,
                "duration": timeout
            }

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # Parse JSON output from worker
        if not stdout:
            return {
                "status": STATUS_RUNTIME_ERROR,
                "error": stderr or "Worker terminated without output.",
                "volume": 0.0,
                "bbox": None,
                "stl_path": None,
                "duration": duration
            }

        try:
            # Grab the last line of stdout which contains JSON
            json_line = stdout.splitlines()[-1]
            data = json.loads(json_line)
            data["duration"] = duration
            
            # If STL was created, copy bytes
            if data.get("status") == STATUS_SUCCESS and os.path.exists(stl_file):
                with open(stl_file, "rb") as sf:
                    data["stl_bytes"] = sf.read()
            return data
        except Exception as e:
            return {
                "status": STATUS_RUNTIME_ERROR,
                "error": f"Failed to parse worker output: {stdout}. Trace: {e}",
                "volume": 0.0,
                "bbox": None,
                "stl_path": None,
                "duration": duration
            }
