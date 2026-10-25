"""
Live API smoke test script.
Sends 20 held-out test triplets through the CAD Patch Editor Web API,
evaluating validity rate, program exact-match rate, and p50/p95 latency.
"""

import json
import os
import sys
import time
import numpy as np
from fastapi.testclient import TestClient

from cadpatch.web.config import WebConfig
from cadpatch.web.app import create_app
from cadpatch.eval.program_metrics import normalize_code


def run_web_smoke_test(num_samples: int = 20):
    print(f"=== Starting Web API Live Smoke Test ({num_samples} samples) ===")
    
    # 1. Load held-out test dataset
    data_file = os.path.join("data", "test_heldout.jsonl")
    if not os.path.exists(data_file):
        print(f"Error: dataset file {data_file} not found.")
        sys.exit(1)

    samples = []
    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
                if len(samples) >= num_samples:
                    break

    print(f"Loaded {len(samples)} evaluation triplets from {data_file}.")

    # 2. Initialize web app client
    cfg = WebConfig({
        "server": {"host": "127.0.0.1", "port": 8000},
        "model": {"backend": os.environ.get("CADPATCH_MODEL_BACKEND", "mock")},
        "security": {"sandbox_timeout_seconds": 15.0, "rate_limit_per_minute": 100},
        "storage": {"artifact_dir": "outputs/web_smoke_artifacts"}
    })
    app = create_app(config=cfg)
    with TestClient(app) as client:
        # Verify health
        h_res = client.get("/api/health")
        assert h_res.status_code == 200, f"Health check failed: {h_res.text}"
        print(f"Server health check OK. Backend: {h_res.json()['model_backend']}", flush=True)

        # 3. Process samples through the API
        latencies = []
        valid_count = 0
        exact_match_count = 0
        results_log = []

        for idx, sample in enumerate(samples, 1):
            t0 = time.time()
            req_payload = {
                "script": sample["original"],
                "instruction": sample["instruction"],
                "mode": "patch",
                "retry_count": 3
            }
            res = client.post("/api/edit", json=req_payload)
            if res.status_code != 200:
                print(f"[{idx:02d}/{num_samples}] Submission error: {res.text}", flush=True)
                latencies.append(time.time() - t0)
                continue

            job_id = res.json()["job_id"]

            # Poll job status (up to 25s)
            job_result = None
            for _ in range(100):
                time.sleep(0.25)
                st_res = client.get(f"/api/jobs/{job_id}")
                st_data = st_res.json()
                if st_data["status"] in ["COMPLETED", "FAILED"]:
                    job_result = st_data.get("result")
                    break

            elapsed = time.time() - t0
            latencies.append(elapsed)

            is_valid = False
            is_em = False

            if job_result and job_result.get("status") == "COMPLETED":
                metrics = job_result.get("metrics") or {}
                is_valid = metrics.get("validity", False)
                if is_valid:
                    valid_count += 1

                pred_edited = job_result.get("edited_script") or ""
                gt_edited = sample["edited"]
                if normalize_code(pred_edited) == normalize_code(gt_edited):
                    exact_match_count += 1
                    is_em = True

            status_str = "OK" if (is_valid and is_em) else ("VALID" if is_valid else "FAIL")
            print(f"[{idx:02d}/{num_samples}] Template: {sample['template'][:14]:14s} | Edit: {sample['edit_type'][:12]:12s} | Status: {status_str:5s} | Time: {elapsed:.2f}s", flush=True)
            results_log.append({
                "idx": idx,
                "template": sample["template"],
                "edit_type": sample["edit_type"],
                "valid": is_valid,
                "exact_match": is_em,
                "latency": elapsed
            })

        # 4. Compute statistics
        val_rate = (valid_count / len(samples)) * 100.0
        em_rate = (exact_match_count / len(samples)) * 100.0
        p50_latency = float(np.percentile(latencies, 50))
        p95_latency = float(np.percentile(latencies, 95))
        mean_latency = float(np.mean(latencies))

        print("\n" + "=" * 50, flush=True)
        print("           LIVE WEB API SMOKE TEST RESULTS        ", flush=True)
        print("=" * 50, flush=True)
        print(f"Samples Evaluated : {len(samples)}", flush=True)
        print(f"Execution Validity: {valid_count}/{len(samples)} ({val_rate:.1f}%)", flush=True)
        print(f"Exact Match Rate  : {exact_match_count}/{len(samples)} ({em_rate:.1f}%)", flush=True)
        print(f"Latency p50       : {p50_latency:.2f} s", flush=True)
        print(f"Latency p95       : {p95_latency:.2f} s", flush=True)
        print(f"Latency Mean      : {mean_latency:.2f} s", flush=True)
        print("=" * 50, flush=True)

        # Save summary report
        out_dir = os.path.join("outputs", "eval")
        os.makedirs(out_dir, exist_ok=True)
        report_file = os.path.join(out_dir, "web_smoke_results.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump({
                "num_samples": len(samples),
                "validity_rate_pct": val_rate,
                "exact_match_rate_pct": em_rate,
                "latency_p50": p50_latency,
                "latency_p95": p95_latency,
                "latency_mean": mean_latency,
                "samples": results_log
            }, f, indent=2)
        print(f"Saved results summary to {report_file}", flush=True)


if __name__ == "__main__":
    run_web_smoke_test()
