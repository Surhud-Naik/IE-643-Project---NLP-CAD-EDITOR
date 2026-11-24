"""
PyTorch and PEFT model backend implementation for live web inference.
Integrates LoRA patch model and full regeneration baseline with retry-with-sampling.
"""

from typing import Dict, Any, Tuple, Optional
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from ..models.prompt_formatter import format_patch_prompt, format_full_prompt
from .model_service import ModelBackend
from .config import WebConfig


def resolve_device_and_dtype(device_pref: str = "auto") -> Tuple[torch.device, torch.dtype]:
    pref = (device_pref or "auto").lower()
    if pref in ("cuda", "auto") and torch.cuda.is_available():
        return torch.device("cuda"), torch.float16
    elif pref in ("mps", "auto") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps"), torch.bfloat16
    else:
        return torch.device("cpu"), torch.float32


def empty_device_cache(device: torch.device):
    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif device.type == "mps" and hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
        torch.mps.empty_cache()


class LocalPeftModelBackend(ModelBackend):
    def __init__(
        self,
        base_model_name: str,
        patch_adapter_path: Optional[str] = None,
        full_adapter_path: Optional[str] = None,
        load_in_4bit: bool = False,
        device: str = "auto",
        max_new_tokens: int = 256
    ):
        self.max_new_tokens = max_new_tokens
        self.device, self.dtype = resolve_device_and_dtype(device)
        
        self.tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Model loading kwargs
        model_kwargs = {"trust_remote_code": True}
        if self.device.type == "cuda":
            if load_in_4bit:
                try:
                    from transformers import BitsAndBytesConfig
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16
                    )
                except Exception:
                    model_kwargs["torch_dtype"] = torch.float16
            else:
                model_kwargs["torch_dtype"] = torch.float16
        else:
            model_kwargs["torch_dtype"] = self.dtype

        base_model = AutoModelForCausalLM.from_pretrained(base_model_name, **model_kwargs)

        # Load LoRA patch adapter and full regen adapter onto single base model
        if patch_adapter_path and os.path.exists(patch_adapter_path):
            self.model = PeftModel.from_pretrained(base_model, patch_adapter_path, adapter_name="patch")
            self.has_patch_adapter = True
            if full_adapter_path and os.path.exists(full_adapter_path):
                try:
                    self.model.load_adapter(full_adapter_path, adapter_name="full_regen")
                    self.has_full_adapter = True
                except Exception:
                    self.has_full_adapter = False
            else:
                self.has_full_adapter = False
        elif full_adapter_path and os.path.exists(full_adapter_path):
            self.model = PeftModel.from_pretrained(base_model, full_adapter_path, adapter_name="full_regen")
            self.has_patch_adapter = False
            self.has_full_adapter = True
        else:
            self.model = base_model
            self.has_patch_adapter = False
            self.has_full_adapter = False

        if not load_in_4bit:
            self.model.to(self.device)
        self.model.eval()

        self.patch_model = self.model
        self.full_model = self.model if self.has_full_adapter else None

    def generate(
        self,
        script: str,
        instruction: str,
        mode: str = "patch",
        temperature: float = 0.2,
        attempt: int = 1
    ) -> Tuple[str, str]:
        if mode == "full_regen":
            prompt = format_full_prompt(script, instruction)
            if hasattr(self.model, "set_adapter") and self.has_full_adapter:
                self.model.set_adapter("full_regen")
        else:
            prompt = format_patch_prompt(script, instruction)
            if hasattr(self.model, "set_adapter") and self.has_patch_adapter:
                self.model.set_adapter("patch")

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        # Attempt 1: greedy (temp=None, do_sample=False)
        # Attempt >= 2: sampling with temperature
        do_sample = (attempt > 1)
        temp = temperature if do_sample else None

        with torch.no_grad():
            gen_tokens = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=do_sample,
                temperature=temp,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        completion_tokens = gen_tokens[0][inputs["input_ids"].shape[1]:]
        raw_output = self.tokenizer.decode(completion_tokens, skip_special_tokens=True).strip()
        empty_device_cache(self.device)

        if mode == "full_regen":
            cleaned = self._clean_code(raw_output)
            return cleaned, raw_output
        else:
            cleaned = self._clean_patch(raw_output)
            return cleaned, raw_output

    def _clean_patch(self, text: str) -> str:
        match = re.search(r"(<<<<<<< SEARCH.*?>>>>>>> REPLACE)", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _clean_code(self, text: str) -> str:
        match = re.search(r"```python(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"```(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()


class MergedModelBackend(ModelBackend):
    def __init__(self, model_path: str, max_new_tokens: int = 256, device: str = "auto"):
        self.max_new_tokens = max_new_tokens
        self.device, self.dtype = resolve_device_and_dtype(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=self.dtype,
            trust_remote_code=True
        ).to(self.device)
        self.model.eval()

    def generate(
        self,
        script: str,
        instruction: str,
        mode: str = "patch",
        temperature: float = 0.2,
        attempt: int = 1
    ) -> Tuple[str, str]:
        prompt = format_patch_prompt(script, instruction)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        do_sample = (attempt > 1)
        temp = temperature if do_sample else None

        with torch.no_grad():
            gen_tokens = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=do_sample,
                temperature=temp,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        completion_tokens = gen_tokens[0][inputs["input_ids"].shape[1]:]
        raw_output = self.tokenizer.decode(completion_tokens, skip_special_tokens=True).strip()
        empty_device_cache(self.device)
        match = re.search(r"(<<<<<<< SEARCH.*?>>>>>>> REPLACE)", raw_output, re.DOTALL)
        cleaned = match.group(1).strip() if match else raw_output.strip()
        return cleaned, raw_output


def create_peft_backend(config: WebConfig) -> ModelBackend:
    if config.model_backend == "merged_model":
        return MergedModelBackend(
            model_path=config.base_model,
            max_new_tokens=config.max_new_tokens
        )
    return LocalPeftModelBackend(
        base_model_name=config.base_model,
        patch_adapter_path=config.adapter_path,
        full_adapter_path=config.full_regen_adapter_path,
        load_in_4bit=config.load_in_4bit,
        device=config.device,
        max_new_tokens=config.max_new_tokens
    )
