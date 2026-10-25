"""
Dataset preparation with completion-only loss masking for Supervised Fine-Tuning.
"""

from typing import List, Dict, Any, Optional
import json
import torch
from torch.utils.data import Dataset
from .prompt_formatter import format_patch_prompt, format_full_prompt


class SFTCADDataset(Dataset):
    """
    Dataset wrapper for training code LLMs with completion-only loss masking.
    Prompt tokens receive label -100, so loss is computed exclusively on the target patch or code.
    """
    def __init__(
        self,
        jsonl_path: str,
        tokenizer: Any,
        task: str = "patch",  # "patch" or "full"
        max_length: int = 1024,
        max_samples: Optional[int] = None
    ):
        self.tokenizer = tokenizer
        self.task = task
        self.max_length = max_length

        self.samples = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.samples.append(json.loads(line))

        if max_samples:
            self.samples = self.samples[:max_samples]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = self.samples[idx]
        orig_code = item["original"]
        instruction = item["instruction"]

        if self.task == "patch":
            prompt = format_patch_prompt(orig_code, instruction)
            completion = item["patch"] + "<|im_end|>"
        else:
            prompt = format_full_prompt(orig_code, instruction)
            completion = item["edited"] + "<|im_end|>"

        prompt_ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        completion_ids = self.tokenizer.encode(completion, add_special_tokens=False)

        input_ids = prompt_ids + completion_ids
        # Mask out prompt tokens so loss is only on completion
        labels = [-100] * len(prompt_ids) + completion_ids

        # Truncate if necessary
        if len(input_ids) > self.max_length:
            input_ids = input_ids[:self.max_length]
            labels = labels[:self.max_length]

        attention_mask = [1] * len(input_ids)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def collate_sft_batch(batch: List[Dict[str, torch.Tensor]], pad_token_id: int = 0) -> Dict[str, torch.Tensor]:
    """Pads batch to longest sequence."""
    max_len = max(len(item["input_ids"]) for item in batch)
    batch_input_ids = []
    batch_attention_mask = []
    batch_labels = []

    for item in batch:
        cur_len = len(item["input_ids"])
        pad_len = max_len - cur_len

        # Right padding
        padded_ids = torch.cat([item["input_ids"], torch.full((pad_len,), pad_token_id, dtype=torch.long)])
        padded_mask = torch.cat([item["attention_mask"], torch.zeros(pad_len, dtype=torch.long)])
        padded_labels = torch.cat([item["labels"], torch.full((pad_len,), -100, dtype=torch.long)])

        batch_input_ids.append(padded_ids)
        batch_attention_mask.append(padded_mask)
        batch_labels.append(padded_labels)

    return {
        "input_ids": torch.stack(batch_input_ids),
        "attention_mask": torch.stack(batch_attention_mask),
        "labels": torch.stack(batch_labels),
    }
