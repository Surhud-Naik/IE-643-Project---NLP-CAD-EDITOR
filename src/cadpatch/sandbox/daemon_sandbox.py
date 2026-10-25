"""
High-performance persistent CadQuery sandbox daemon.
Keeps a persistent subprocess alive so OpenCASCADE / VTK libraries are loaded only once,
reducing execution overhead from ~6 seconds per script to ~5 milliseconds per script.
"""

from typing import Dict, Any, Optional
import json
import subprocess
import sys
import os
import time
from .executor import static_security_check, STATUS_SUCCESS, STATUS_SECURITY_VIOLATION, STATUS_RUNTIME_ERROR, STATUS_TIMEOUT, STATUS_INVALID_GEOMETRY

DAEMON_WORKER_CODE = """
import sys
import json
import math
import traceback
import cadquery as cq
import cadquery

safe_builtins = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "int": int,
    "isinstance": isinstance, "issubclass": issubclass, "len": len, "list": list,
    "map": map, "max": max, "min": min, "pow": pow, "range": range,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "True": True, "False": False, "None": None, "Exception": Exception,
    "ValueError": ValueError, "TypeError": TypeError, "ZeroDivisionError": ZeroDivisionError
}

# Signal ready
print(json.dumps({"status": "READY"}), flush=True)

while True:
    line = sys.stdin.readline()
    if not line:
        break
    try:
        req = json.loads(line.strip())
        code = req.get("code", "")
        export_stl = req.get("export_stl", False)
        stl_path = req.get("stl_path", "")

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".")[0]
            if root not in {"cadquery", "cq", "math"}:
                raise ImportError(f"Import of '{name}' is forbidden.")
            return __import__(name, globals, locals, fromlist, level)

        builtins_dict = dict(safe_builtins)
        builtins_dict["__import__"] = safe_import

        safe_globals = {
            "__builtins__": builtins_dict,
            "math": math,
            "cadquery": cadquery,
            "cq": cq
        }

        exec(code, safe_globals)
        result = safe_globals.get("result")
        if result is None:
            print(json.dumps({"status": "INVALID_GEOMETRY", "error": "Variable 'result' not found."}), flush=True)
            continue

        shape = result.val() if hasattr(result, "val") else result
        if not hasattr(shape, "Volume"):
            print(json.dumps({"status": "INVALID_GEOMETRY", "error": "'result' does not contain a solid."}), flush=True)
            continue

        volume = float(shape.Volume())
        if volume <= 1e-6:
            print(json.dumps({"status": "INVALID_GEOMETRY", "error": f"Volume must be positive, got {volume}"}), flush=True)
            continue

        bb = shape.BoundingBox()
        bbox_info = {
            "xmin": float(bb.xmin), "ymin": float(bb.ymin), "zmin": float(bb.zmin),
            "xmax": float(bb.xmax), "ymax": float(bb.ymax), "zmax": float(bb.zmax),
            "xlen": float(bb.xlen), "ylen": float(bb.ylen), "zlen": float(bb.zlen),
            "diagonal": float(math.sqrt(bb.xlen**2 + bb.ylen**2 + bb.zlen**2))
        }

        if export_stl and stl_path:
            cq.exporters.export(result, stl_path)

        export_step = req.get("export_step", False)
        step_path = req.get("step_path", "")
        if export_step and step_path:
            cq.exporters.export(result, step_path)

        print(json.dumps({
            "status": "SUCCESS",
            "volume": volume,
            "bbox": bbox_info
        }), flush=True)

    except Exception as e:
        print(json.dumps({
            "status": "RUNTIME_ERROR",
            "error": f"{type(e).__name__}: {str(e)}"
        }), flush=True)
"""


class CadQueryDaemonSandbox:
    """
    Persistent sandbox worker daemon.
    """
    def __init__(self, python_executable: Optional[str] = None):
        if python_executable is None:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            venv_py = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
            self.python_executable = venv_py if os.path.exists(venv_py) else sys.executable
        else:
            self.python_executable = python_executable

        self.proc: Optional[subprocess.Popen] = None
        self._start_process()

    def _start_process(self):
        if self.proc is not None:
            try:
                self.proc.kill()
            except Exception:
                pass

        self.proc = subprocess.Popen(
            [self.python_executable, "-u", "-c", DAEMON_WORKER_CODE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        # Wait for READY signal
        ready_line = self.proc.stdout.readline().strip()
        try:
            msg = json.loads(ready_line)
            if msg.get("status") != "READY":
                raise RuntimeError(f"Unexpected worker handshake: {ready_line}")
        except Exception as e:
            err = self.proc.stderr.read()
            raise RuntimeError(f"Worker daemon failed to initialize: {e}. Stderr: {err}")

    def execute(
        self,
        code_str: str,
        timeout: float = 10.0,
        export_stl: bool = False,
        stl_path: str = "",
        export_step: bool = False,
        step_path: str = ""
    ) -> Dict[str, Any]:
        """Executes code via the daemon worker with AST security pre-check."""
        # 1. Static security check
        sec_err = static_security_check(code_str)
        if sec_err:
            return {
                "status": STATUS_SECURITY_VIOLATION if "Security Violation" in sec_err else STATUS_RUNTIME_ERROR,
                "error": sec_err,
                "volume": 0.0,
                "bbox": None
            }

        temp_stl = None
        temp_step = None
        import tempfile
        if export_stl and not stl_path:
            temp_stl = tempfile.mktemp(suffix=".stl")
            stl_path = temp_stl

        if export_step and not step_path:
            temp_step = tempfile.mktemp(suffix=".step")
            step_path = temp_step

        req = json.dumps({
            "code": code_str,
            "export_stl": export_stl,
            "stl_path": stl_path,
            "export_step": export_step,
            "step_path": step_path
        })

        try:
            t0 = time.time()
            self.proc.stdin.write(req + "\n")
            self.proc.stdin.flush()

            resp_line = self.proc.stdout.readline()
            duration = time.time() - t0
            if not resp_line:
                # Process crashed, restart
                self._start_process()
                return {
                    "status": STATUS_RUNTIME_ERROR,
                    "error": "Daemon worker process crashed and was restarted.",
                    "volume": 0.0,
                    "bbox": None,
                    "duration": duration
                }

            data = json.loads(resp_line.strip())
            data["duration"] = duration

            if data.get("status") == "SUCCESS":
                if export_stl and os.path.exists(stl_path):
                    with open(stl_path, "rb") as f:
                        data["stl_bytes"] = f.read()
                if export_step and os.path.exists(step_path):
                    with open(step_path, "rb") as f:
                        data["step_bytes"] = f.read()

            # Clean up temp files if created
            if temp_stl and os.path.exists(temp_stl):
                try:
                    os.remove(temp_stl)
                except Exception:
                    pass
            if temp_step and os.path.exists(temp_step):
                try:
                    os.remove(temp_step)
                except Exception:
                    pass

            return data

        except Exception as e:
            self._start_process()
            return {
                "status": STATUS_RUNTIME_ERROR,
                "error": f"Daemon execution error: {e}",
                "volume": 0.0,
                "bbox": None,
                "duration": 0.0
            }

    def close(self):
        if self.proc is not None:
            try:
                self.proc.kill()
            except Exception:
                pass
            self.proc = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
