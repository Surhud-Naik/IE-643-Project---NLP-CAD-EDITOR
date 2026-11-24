"""
Model service providing pluggable inference backends (mock, local_peft, merged_model)
and a single-worker async queue to prevent GPU memory exhaustion.
"""

from typing import Dict, Any, Tuple, Optional
import asyncio
import re
from ..eval.program_metrics import extract_top_level_params
from ..patching.patch import make_patch
from ..patching.expr import resolve_instruction_edits


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

        # Semantic parameter editing using safe AST expression evaluator
        res = resolve_instruction_edits(script, instruction)
        if not res["success"]:
            bad = f"Error: {res.get('error', 'Could not identify parameter to edit.')}"
            return bad, bad

        if mode == "full_regen":
            return res["edited_script"], res["edited_script"]

        return res["patch"], res["patch"]


class AsyncModelQueue:
    """
    Serializes inference requests through a single-worker async queue.
    """
    def __init__(self, backend: ModelBackend):
        self.backend = backend
        self.queue: Optional[asyncio.Queue] = None
        self.worker_task: Optional[asyncio.Task] = None
        self._current_job_id: Optional[str] = None

    def _get_queue(self) -> asyncio.Queue:
        if self.queue is None:
            self.queue = asyncio.Queue()
        return self.queue

    async def start(self):
        self._get_queue()
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
        if self.queue is None:
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
        q = self._get_queue()
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._process_queue())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await q.put((job_id, script, instruction, mode, temperature, attempt, future))
        return future

    async def _process_queue(self):
        q = self._get_queue()
        while True:
            try:
                item = await q.get()
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
                    q.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)
