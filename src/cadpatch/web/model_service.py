"""
Model service providing pluggable inference backends (mock, local_peft, merged_model)
and a single-worker async queue to prevent GPU memory exhaustion.
"""

from typing import Dict, Any, Tuple, Optional
import asyncio
import re
from ..eval.program_metrics import extract_top_level_params
from ..patching.patch import make_patch


class ModelBackend:
    """Base interface for model inference backends."""
    def generate(
        self,
        script: str,
        instruction: str,
        mode: str = "patch",
        temperature: float = 0.2,
        attempt: int = 1
    ) -> Tuple[str, str]:
        raise NotImplementedError


class MockModelBackend(ModelBackend):
    """
    Deterministic mock backend for UI development, automated testing, and CI.
    Supports simulated failure modes and keyword-based parameter modifications.
    """
    def generate(
        self,
        script: str,
        instruction: str,
        mode: str = "patch",
        temperature: float = 0.2,
        attempt: int = 1
    ) -> Tuple[str, str]:
        inst_lower = instruction.lower().strip()

        # Simulated test conditions
        if "simulate_malformed" in inst_lower:
            bad = "This is a malformed patch with no delimiters."
            return bad, bad

        if "simulate_no_match" in inst_lower:
            no_match = "<<<<<<< SEARCH\nNON_EXISTENT_VAR = 99999\n=======\nNON_EXISTENT_VAR = 88888\n>>>>>>> REPLACE"
            return no_match, no_match

        if "simulate_retry_success" in inst_lower:
            if attempt == 1:
                bad = "<<<<<<< SEARCH\nBAD_TARGET_LINE\n=======\nREPLACEMENT\n>>>>>>> REPLACE"
                return bad, bad
            # On attempt >= 2, fall through to valid edit

        # Semantic parameter editing
        params = extract_top_level_params(script)
        if not params:
            # Fallback if no top-level params found
            bad = "Error: No parameters found to modify."
            return bad, bad

        # Identify target parameter
        target_param = None
        delta = 2.0

        # Extract numeric magnitude if present in instruction
        num_matches = re.findall(r"[-+]?\d*\.?\d+", instruction)
        if num_matches:
            try:
                delta = float(num_matches[0])
            except ValueError:
                delta = 2.0

        if any(k in inst_lower for k in ["hole", "widen", "bore", "diameter", "radius", "drill"]):
            for p in ["HOLE_DIA", "HOLE_RADIUS", "INNER_RADIUS", "BORE_RADIUS", "DIAMETER", "RADIUS"]:
                if p in params:
                    target_param = p
                    break
        elif any(k in inst_lower for k in ["fillet", "round", "curve"]):
            for p in ["FILLET_RADIUS", "FILLET", "CORNER_FILLET"]:
                if p in params:
                    target_param = p
                    break
        elif any(k in inst_lower for k in ["chamfer", "bevel"]):
            for p in ["CHAMFER_DIST", "CHAMFER"]:
                if p in params:
                    target_param = p
                    break
        elif any(k in inst_lower for k in ["length", "longer", "extend"]):
            for p in ["LENGTH", "BASE_LENGTH", "PLATE_LENGTH"]:
                if p in params:
                    target_param = p
                    break
        elif any(k in inst_lower for k in ["width", "widen"]):
            for p in ["WIDTH", "BASE_WIDTH", "PLATE_WIDTH"]:
                if p in params:
                    target_param = p
                    break
        elif any(k in inst_lower for k in ["height", "thicker", "thickness", "tall"]):
            for p in ["HEIGHT", "THICKNESS", "BASE_HEIGHT", "PLATE_THICKNESS"]:
                if p in params:
                    target_param = p
                    break

        if not target_param:
            # Pick first numeric parameter
            for p, v in params.items():
                if isinstance(v, (int, float)):
                    target_param = p
                    break

        if not target_param:
            bad = "Error: Could not identify parameter to edit."
            return bad, bad

        old_val = params[target_param]
        # Calculate new value
        if any(w in inst_lower for w in ["reduce", "shrink", "narrow", "thinner", "decrease"]):
            new_val = max(1.0, old_val - abs(delta))
        elif any(w in inst_lower for w in ["double", "twice"]):
            new_val = old_val * 2.0
        else:
            new_val = old_val + abs(delta)

        # Match exact search line from script
        search_line = None
        for line in script.splitlines():
            if line.strip().startswith(f"{target_param}") and "=" in line:
                search_line = line
                break

        if not search_line:
            search_line = f"{target_param} = {old_val}"
            replace_line = f"{target_param} = {new_val}"
        else:
            # Preserve formatting / spacing
            eq_idx = search_line.find("=")
            prefix = search_line[:eq_idx + 1]
            replace_line = f"{prefix} {new_val}"

        if mode == "full_regen":
            edited_script = script.replace(search_line, replace_line, 1)
            return edited_script, edited_script

        patch = f"<<<<<<< SEARCH\n{search_line}\n=======\n{replace_line}\n>>>>>>> REPLACE"
        return patch, patch


class AsyncModelQueue:
    """
    Serializes inference requests through a single-worker async queue.
    """
    def __init__(self, backend: ModelBackend):
        self.backend = backend
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self._current_job_id: Optional[str] = None

    async def start(self):
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

    def get_queue_position(self, job_id: str) -> int:
        if self._current_job_id == job_id:
            return 0
        pos = 1
        # Inspect queue items without modifying
        for item in list(self.queue._queue):
            if item[0] == job_id:
                return pos
            pos += 1
        return 0

    async def enqueue(
        self,
        job_id: str,
        script: str,
        instruction: str,
        mode: str = "patch",
        temperature: float = 0.2,
        attempt: int = 1
    ) -> asyncio.Future:
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._process_queue())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put((job_id, script, instruction, mode, temperature, attempt, future))
        return future

    async def _process_queue(self):
        while True:
            try:
                item = await self.queue.get()
                job_id, script, instruction, mode, temperature, attempt, future = item
                self._current_job_id = job_id
                try:
                    # Run backend inference in thread pool if blocking
                    loop = asyncio.get_running_loop()
                    patch, raw = await loop.run_in_executor(
                        None,
                        self.backend.generate,
                        script,
                        instruction,
                        mode,
                        temperature,
                        attempt
                    )
                    if not future.done():
                        future.set_result((patch, raw))
                except Exception as e:
                    if not future.done():
                        future.set_exception(e)
                finally:
                    self._current_job_id = None
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)
