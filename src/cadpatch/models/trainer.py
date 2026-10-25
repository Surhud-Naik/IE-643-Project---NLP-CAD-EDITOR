"""
LoRA Fine-tuning engine for CadQuery patch prediction and full program regeneration.
"""

from typing import Dict, Any, Optional
import os
import json
import torch
from torch.utils.data import DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    get_cosine_schedule_with_warmup,
)
from peft import LoraConfig, get_peft_model, TaskType
from .dataset import SFTCADDataset, collate_sft_batch


def train_lora_model(
    config: Dict[str, Any],
    task: str = "patch"
) -> Dict[str, Any]:
    """
    Trains a LoRA model on the CAD editing dataset.
    config keys:
      - base_model: e.g. "Qwen/Qwen2.5-Coder-0.5B-Instruct"
      - train_data_path: "data/train.jsonl"
      - val_data_path: "data/val.jsonl"
      - output_dir: "outputs/models/patch_lora"
      - lora_r: 16
      - lora_alpha: 32
      - lora_dropout: 0.05
      - learning_rate: 2e-4
      - epochs: 3
      - batch_size: 2
      - grad_accum: 4
      - max_samples: Optional[int] (for quick testing/CPU)
    """
    base_model_name = config.get("base_model", "Qwen/Qwen2.5-Coder-0.5B-Instruct")
    output_dir = config.get("output_dir", f"outputs/models/{task}_lora")
    train_path = config.get("train_data_path", "data/train.jsonl")
    val_path = config.get("val_data_path", "data/val.jsonl")

    lora_r = config.get("lora_r", 16)
    lora_alpha = config.get("lora_alpha", 32)
    lora_dropout = config.get("lora_dropout", 0.05)
    lr = float(config.get("learning_rate", 2e-4))
    epochs = config.get("epochs", 3)
    batch_size = config.get("batch_size", 2)
    grad_accum = config.get("grad_accum", 4)
    max_samples = config.get("max_samples", None)

    os.makedirs(output_dir, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Starting LoRA Training ({task.upper()} Model) ===")
    print(f"Base Model:       {base_model_name}")
    print(f"Device:           {device}")
    print(f"LoRA config:      r={lora_r}, alpha={lora_alpha}, dropout={lora_dropout}")
    print(f"Batch size:       {batch_size} (effective: {batch_size * grad_accum})")
    print(f"Epochs:           {epochs}")

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load base model
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch_dtype,
        trust_remote_code=True
    )
    model.to(device)

    # Configure LoRA
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # Create Datasets
    train_dataset = SFTCADDataset(train_path, tokenizer, task=task, max_samples=max_samples)
    val_dataset = SFTCADDataset(val_path, tokenizer, task=task, max_samples=max_samples // 4 if max_samples else None)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=lambda b: collate_sft_batch(b, pad_token_id=tokenizer.pad_token_id)
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=lambda b: collate_sft_batch(b, pad_token_id=tokenizer.pad_token_id)
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = (len(train_loader) // grad_accum) * epochs
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * 0.05),
        num_training_steps=total_steps
    )

    history = {"train_loss": [], "val_loss": [], "epochs": []}
    global_step = 0

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss / grad_accum
            loss.backward()

            running_loss += outputs.loss.item()

            if (step + 1) % grad_accum == 0 or (step + 1) == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

        avg_train_loss = running_loss / max(len(train_loader), 1)

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                val_loss += outputs.loss.item()
        avg_val_loss = val_loss / max(len(val_loader), 1)

        history["epochs"].append(epoch)
        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)

        print(f"Epoch {epoch}/{epochs} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}")

    # Save adapter
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    history_path = os.path.join(output_dir, "training_history.json")
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    print(f"Model and training curves saved to: {output_dir}")
    return history
