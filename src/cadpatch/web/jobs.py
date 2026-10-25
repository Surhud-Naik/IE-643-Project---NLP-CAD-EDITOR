"""
Job management, artifact storage, TTL cleanup, and Server-Sent Events (SSE) streaming.
"""

from typing import Dict, Any, Optional, List, AsyncGenerator
import asyncio
import json
import os
import shutil
import time
import uuid
from .schemas import (
    JobStatus, JobResult, EditMode, GeometryMetrics, ChangeSummary,
    ParameterChange, BaselineComparison
)
from .geometry_service import GeometryService
from .model_service import AsyncModelQueue
from ..patching.patch import apply_patch, make_patch, STATUS_SUCCESS as PATCH_SUCCESS
from ..sandbox.executor import STATUS_SUCCESS as SANDBOX_SUCCESS


class JobRecord:
    def __init__(
        self,
        job_id: str,
        script: str,
        instruction: str,
        mode: EditMode = EditMode.PATCH,
        retry_count: int = 3,
        temperature: float = 0.2
    ):
        self.job_id = job_id
        self.script = script
        self.instruction = instruction
        self.mode = mode
        self.retry_count = retry_count
        self.temperature = temperature
        self.status = JobStatus.QUEUED
        self.current_attempt = 1
        self.message = "Job queued."
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self.cancelled = False
        self.result: Optional[JobResult] = None
        self.error: Optional[str] = None
        self.subscribers: List[asyncio.Queue] = []
        self.raw_patch: Optional[str] = None


class JobManager:
    def __init__(
        self,
        geometry_service: GeometryService,
        model_queue: AsyncModelQueue,
        artifact_dir: str = "outputs/web_jobs",
        ttl_seconds: int = 3600
    ):
        self.geometry_service = geometry_service
        self.model_queue = model_queue
        self.artifact_dir = os.path.abspath(artifact_dir)
        self.ttl_seconds = ttl_seconds
        self.jobs: Dict[str, JobRecord] = {}
        os.makedirs(self.artifact_dir, exist_ok=True)
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def create_job(
        self,
        script: str,
        instruction: str,
        mode: EditMode = EditMode.PATCH,
        retry_count: int = 3,
        temperature: float = 0.2
    ) -> JobRecord:
        job_id = str(uuid.uuid4())
        job = JobRecord(
            job_id=job_id,
            script=script,
            instruction=instruction,
            mode=mode,
            retry_count=retry_count,
            temperature=temperature
        )
        self.jobs[job_id] = job
        # Launch background processing task
        asyncio.create_task(self._process_job(job))
        return job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job and job.status not in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            job.cancelled = True
            job.status = JobStatus.CANCELLED
            job.message = "Job was cancelled by the user."
            self.publish_event(job, "Job was cancelled.")
            return True
        return False

    def publish_event(self, job: JobRecord, message: str):
        job.message = message
        event_data = {
            "job_id": job.job_id,
            "status": job.status.value,
            "current_attempt": job.current_attempt,
            "max_attempts": job.retry_count,
            "message": message,
            "error": job.error,
            "raw_patch": job.raw_patch,
            "result": job.result.model_dump() if job.result else None
        }
        for q in list(job.subscribers):
            try:
                q.put_nowait(event_data)
            except Exception:
                pass

    async def subscribe(self, job_id: str) -> AsyncGenerator[str, None]:
        job = self.jobs.get(job_id)
        if not job:
            return

        q: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(q)

        # Yield current initial state
        initial_data = {
            "job_id": job.job_id,
            "status": job.status.value,
            "current_attempt": job.current_attempt,
            "max_attempts": job.retry_count,
            "message": job.message,
            "error": job.error,
            "raw_patch": job.raw_patch,
            "result": job.result.model_dump() if job.result else None
        }
        yield f"data: {json.dumps(initial_data)}\n\n"

        try:
            while True:
                data = await q.get()
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
                    break
        finally:
            if q in job.subscribers:
                job.subscribers.remove(q)

    async def _process_job(self, job: JobRecord):
        loop = asyncio.get_running_loop()
        start_time = time.time()

        try:
            # 1. Pre-flight validation on original script
            job.status = JobStatus.VALIDATING
            self.publish_event(job, "Validating input script in sandbox...")

            orig_res = await loop.run_in_executor(
                None,
                self.geometry_service.execute_script,
                job.script,
                True
            )

            if orig_res.get("status") != SANDBOX_SUCCESS:
                job.status = JobStatus.FAILED
                job.error = f"Pre-flight verification failed: {orig_res.get('error', 'Execution failed')}"
                self.publish_event(job, job.error)
                return

            if job.cancelled:
                return

            # 2. Model inference loop with retry up to retry_count
            edited_script = None
            patch_text = None
            applied_success = False

            for attempt in range(1, job.retry_count + 1):
                if job.cancelled:
                    return

                job.current_attempt = attempt
                job.status = JobStatus.GENERATING
                msg = f"Generating code patch (attempt {attempt}/{job.retry_count})..."
                self.publish_event(job, msg)

                # Enqueue into single-worker inference queue
                future = await self.model_queue.enqueue(
                    job.job_id,
                    job.script,
                    job.instruction,
                    job.mode.value,
                    job.temperature,
                    attempt
                )
                pred_patch, raw_output = await future
                job.raw_patch = raw_output

                if job.cancelled:
                    return

                # 3. Apply patch
                job.status = JobStatus.APPLYING
                self.publish_event(job, f"Applying patch to script (attempt {attempt})...")

                if job.mode == EditMode.FULL_REGEN:
                    edited_script = pred_patch
                    patch_text = make_patch(job.script, edited_script)
                    applied_success = True
                    break
                else:
                    new_prog, patch_status = apply_patch(job.script, pred_patch)
                    if patch_status == PATCH_SUCCESS:
                        edited_script = new_prog
                        patch_text = pred_patch
                        applied_success = True
                        break
                    else:
                        job.message = f"Patch failed to apply on attempt {attempt}: {patch_status}"
                        self.publish_event(job, job.message)

            if not applied_success or not edited_script:
                job.status = JobStatus.FAILED
                job.error = f"Model generated non-applicable patch after {job.retry_count} attempts. Please refine the instruction or check the script."
                self.publish_event(job, job.error)
                return

            if job.cancelled:
                return

            # 4. Sandboxed execution of edited program
            job.status = JobStatus.EXECUTING
            self.publish_event(job, "Executing edited program in CadQuery sandbox...")

            edited_res = await loop.run_in_executor(
                None,
                self.geometry_service.execute_script,
                edited_script,
                True
            )

            if edited_res.get("status") != SANDBOX_SUCCESS:
                job.status = JobStatus.FAILED
                job.error = f"Edited program failed in sandbox: {edited_res.get('error', 'Execution error')}"
                self.publish_event(job, job.error)
                return

            # 5. Compute metrics & change summary
            change_summary, metrics = self.geometry_service.compute_summary_and_metrics(
                job.script,
                edited_script,
                orig_res,
                edited_res,
                patch_text or ""
            )

            # 6. Save artifacts to disk
            job_dir = os.path.join(self.artifact_dir, job.job_id)
            os.makedirs(job_dir, exist_ok=True)

            py_path = os.path.join(job_dir, "model_edited.py")
            with open(py_path, "w", encoding="utf-8") as f:
                f.write(edited_script)

            patch_path = os.path.join(job_dir, "patch.diff")
            with open(patch_path, "w", encoding="utf-8") as f:
                f.write(patch_text or "")

            stl_path = os.path.join(job_dir, "model.stl")
            if edited_res.get("stl_bytes"):
                with open(stl_path, "wb") as f:
                    f.write(edited_res["stl_bytes"])

            step_path = os.path.join(job_dir, "model.step")
            if edited_res.get("step_bytes"):
                with open(step_path, "wb") as f:
                    f.write(edited_res["step_bytes"])

            glb_path = os.path.join(job_dir, "model.glb")
            if edited_res.get("glb_bytes"):
                with open(glb_path, "wb") as f:
                    f.write(edited_res["glb_bytes"])

            # Also save original GLB for viewer
            orig_glb_path = os.path.join(job_dir, "original.glb")
            if orig_res.get("glb_bytes"):
                with open(orig_glb_path, "wb") as f:
                    f.write(orig_res["glb_bytes"])

            download_urls = {
                "py": f"/api/jobs/{job.job_id}/download/py",
                "patch": f"/api/jobs/{job.job_id}/download/patch",
                "stl": f"/api/jobs/{job.job_id}/download/stl",
                "step": f"/api/jobs/{job.job_id}/download/step",
                "glb": f"/api/jobs/{job.job_id}/download/glb",
                "original_glb": f"/api/jobs/{job.job_id}/download/original_glb"
            }

            end_time = time.time()
            job.status = JobStatus.COMPLETED
            job.completed_at = end_time
            job.result = JobResult(
                job_id=job.job_id,
                status=JobStatus.COMPLETED,
                original_script=job.script,
                edited_script=edited_script,
                patch_text=patch_text,
                raw_patch=job.raw_patch,
                attempts_used=job.current_attempt,
                metrics=metrics,
                change_summary=change_summary,
                download_urls=download_urls,
                created_at=start_time,
                completed_at=end_time,
                execution_time_seconds=round(end_time - start_time, 2)
            )

            self.publish_event(job, "Editing completed successfully.")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = f"Internal processing error: {str(e)}"
            self.publish_event(job, job.error)

    async def _periodic_cleanup(self):
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                cutoff = time.time() - self.ttl_seconds
                expired_ids = [
                    jid for jid, rec in self.jobs.items()
                    if rec.created_at < cutoff
                ]
                for jid in expired_ids:
                    self.jobs.pop(jid, None)
                    job_dir = os.path.join(self.artifact_dir, jid)
                    if os.path.exists(job_dir):
                        try:
                            shutil.rmtree(job_dir)
                        except Exception:
                            pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(60)
