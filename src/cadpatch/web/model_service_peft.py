"""
PyTorch and PEFT model backend implementation for live web inference.
Integrates LoRA patch model and full regeneration baseline with retry-with-sampling.
"""

from typing import Dict, Any, Tuple, Optional
import os
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from ..models.prompt_formatter import format_patch_prompt, format_full_prompt
from .model_service import ModelBackend
from .config import WebConfig


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
        self.device = torch.device("cuda" if (device == "auto" and torch.cuda.is_available()) or device == "cuda" else "cpu")
        
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
            model_kwargs["torch_dtype"] = torch.float32

        base_model = AutoModelForCausalLM.from_pretrained(base_model_name, **model_kwargs)

        # Load LoRA patch adapter if available
        if patch_adapter_path and os.path.exists(patch_adapter_path):
            self.patch_model = PeftModel.from_pretrained(base_model, patch_adapter_path)
            self.has_patch_adapter = True
        else:
            self.patch_model = base_model
            self.has_patch_adapter = False

        if not load_in_4bit:
            self.patch_model.to(self.device)
        self.patch_model.eval()

        # Optional full-regeneration model adapter
        self.full_model = None
        if full_adapter_path and os.path.exists(full_adapter_path):
            try:
                base_full = AutoModelForCausalLM.from_pretrained(base_model_name, **model_kwargs)
                self.full_model = PeftModel.from_pretrained(base_full, full_adapter_path)
                if not load_in_4bit:
                    self.full_model.to(self.device)
                self.full_model.eval()
            except Exception:
                self.full_model = None

    def generate(
        self,
        script: str,
        instruction: str,
        mode: str = "patch",
        temperature: float = 0.2,
        attempt: int = 1
    ) -> Tuple[str, str]:
        if mode == "full_regen" and self.full_model is not None:
            model = self.full_model
            prompt = format_full_prompt(script, instruction)
        else:
            model = self.patch_model
            prompt = format_patch_prompt(script, instruction)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        # Attempt 1: greedy (temp=None, do_sample=False)
        # Attempt >= 2: sampling with temperature
        do_sample = (attempt > 1)
        temp = temperature if do_sample else None

        with torch.no_grad():
            gen_tokens = model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=do_sample,
                temperature=temp,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        completion_tokens = gen_tokens[0][inputs["input_ids"].shape[1]:]
        raw_output = self.tokenizer.decode(completion_tokens, skip_special_tokens=True).strip()

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
    def __init__(self, model_path: str, max_new_tokens: int = 256):
        self.max_new_tokens = max_new_tokens
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
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
