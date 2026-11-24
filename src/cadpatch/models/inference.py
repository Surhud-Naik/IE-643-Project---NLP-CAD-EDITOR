"""
Inference engine for fine-tuned LoRA models with greedy decoding and constrained retry.
"""

from typing import Dict, Any, Tuple, Optional
import os
import torch
import re
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from cadpatch.patching import apply_patch, make_patch, STATUS_SUCCESS
from .prompt_formatter import format_patch_prompt, format_full_prompt


def resolve_device_and_dtype(device_pref: str = "auto") -> Tuple[torch.device, torch.dtype]:
    pref = (device_pref or "auto").lower()
    if (pref in ("cuda", "auto")) and torch.cuda.is_available():
        return torch.device("cuda"), torch.float16
    elif (pref in ("mps", "auto")) and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps"), torch.bfloat16
    else:
        return torch.device("cpu"), torch.float32


def empty_device_cache(device: torch.device):
    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif device.type == "mps" and hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
        torch.mps.empty_cache()


class LoRAPatchPredictor:
    """
    Inference predictor for the LoRA patch model.
    Generates search/replace code patches with greedy decoding and optional retry.
    """
    def __init__(
        self,
        base_model_name: str,
        adapter_path: Optional[str] = None,
        max_new_tokens: int = 256,
        retry_attempts: int = 1,
        device: str = "auto"
    ):
        self.device, self.dtype = resolve_device_and_dtype(device)
        self.tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=self.dtype,
            trust_remote_code=True
        )

        if adapter_path and os.path.exists(adapter_path):
            self.model = PeftModel.from_pretrained(base_model, adapter_path)
            self.has_lora = True
        else:
            self.model = base_model
            self.has_lora = False

        self.model.to(self.device)
        self.model.eval()
        self.max_new_tokens = max_new_tokens
        self.retry_attempts = retry_attempts

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        orig_code = sample["original"]
        instruction = sample["instruction"]
        prompt = format_patch_prompt(orig_code, instruction)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        # 1. Greedy decoding first attempt
        for attempt in range(self.retry_attempts):
            do_sample = (attempt > 0)
            temp = 0.3 if do_sample else None

            with torch.no_grad():
                gen_tokens = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=do_sample,
                    temperature=temp,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )

            # Slice out generated completion
            completion_tokens = gen_tokens[0][inputs["input_ids"].shape[1]:]
            raw_output = self.tokenizer.decode(completion_tokens, skip_special_tokens=True).strip()

            # Clean and extract search/replace block
            patch = self._clean_patch(raw_output)
            applied_code, status = apply_patch(orig_code, patch)

            if status == STATUS_SUCCESS:
                empty_device_cache(self.device)
                return patch, applied_code

        empty_device_cache(self.device)
        # If patch failed after retries, return last attempt or ground-truth format attempt
        return patch, orig_code

    def _clean_patch(self, text: str) -> str:
        # Match from <<<<<<< SEARCH to >>>>>>> REPLACE
        match = re.search(r"(<<<<<<< SEARCH.*?>>>>>>> REPLACE)", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Fallback
        return text.strip()


class LoRAFullRegenPredictor:
    """
    Inference predictor for the full-regeneration model.
    """
    def __init__(
        self,
        base_model_name: str,
        adapter_path: Optional[str] = None,
        max_new_tokens: int = 512,
        device: str = "auto"
    ):
        self.device, self.dtype = resolve_device_and_dtype(device)
        self.tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=self.dtype,
            trust_remote_code=True
        )

        if adapter_path and os.path.exists(adapter_path):
            self.model = PeftModel.from_pretrained(base_model, adapter_path)
        else:
            self.model = base_model

        self.model.to(self.device)
        self.model.eval()
        self.max_new_tokens = max_new_tokens

    def predict(self, sample: Dict[str, Any]) -> Tuple[str, str]:
        orig_code = sample["original"]
        instruction = sample["instruction"]
        prompt = format_full_prompt(orig_code, instruction)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            gen_tokens = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        completion_tokens = gen_tokens[0][inputs["input_ids"].shape[1]:]
        raw_output = self.tokenizer.decode(completion_tokens, skip_special_tokens=True).strip()

        # Clean code markdown blocks if present
        pred_code = re.sub(r"^```python\s*", "", raw_output, flags=re.MULTILINE)
        pred_code = re.sub(r"```$", "", pred_code, flags=re.MULTILINE).strip()

        patch = make_patch(orig_code, pred_code)
        empty_device_cache(self.device)
        return patch, pred_code
