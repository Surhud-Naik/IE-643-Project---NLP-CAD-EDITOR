"""
Standardized prompt formatters for patch prediction, full regeneration, and locate-then-infill.
"""

from typing import Dict, Any

SYSTEM_PROMPT_PATCH = (
    "You are an expert mechanical engineer and CAD programmer specializing in CadQuery. "
    "Given an original parametric CadQuery Python script and a natural-language editing instruction, "
    "output ONLY a targeted SEARCH/REPLACE code patch that executes the requested modification. "
    "Do not output markdown explanations or regenerate unmodified code.\n\n"
    "Patch Format:\n"
    "<<<<<<< SEARCH\n"
    "[exact lines from original to replace]\n"
    "=======\n"
    "[replacement lines]\n"
    ">>>>>>> REPLACE"
)

SYSTEM_PROMPT_FULL = (
    "You are an expert mechanical engineer and CAD programmer specializing in CadQuery. "
    "Given an original parametric CadQuery Python script and a natural-language editing instruction, "
    "regenerate the complete edited CadQuery Python script incorporating the requested modifications. "
    "Output ONLY the python code."
)

SYSTEM_PROMPT_LOCATE = (
    "You are an expert CAD engineer. Given an original CadQuery program and an edit instruction, "
    "identify the exact line number range (1-indexed start and end) in the code that needs modification. "
    "Output format: START_LINE:END_LINE"
)

SYSTEM_PROMPT_INFILL = (
    "You are an expert CAD engineer. Given a CadQuery program where the target edit region has been replaced "
    "by <<<< MASK >>>>, and an editing instruction, predict ONLY the replacement code lines to fill the mask."
)


def format_patch_prompt(original_code: str, instruction: str) -> str:
    """Formats the instruction-tuning prompt for the patch prediction model."""
    prompt = (
        f"<|im_start|>system\n{SYSTEM_PROMPT_PATCH}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"### ORIGINAL CADQUERY SCRIPT:\n{original_code}\n\n"
        f"### INSTRUCTION:\n{instruction}\n<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    return prompt


def format_full_prompt(original_code: str, instruction: str) -> str:
    """Formats the instruction-tuning prompt for the full-regeneration model."""
    prompt = (
        f"<|im_start|>system\n{SYSTEM_PROMPT_FULL}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"### ORIGINAL CADQUERY SCRIPT:\n{original_code}\n\n"
        f"### INSTRUCTION:\n{instruction}\n<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    return prompt


def format_locate_prompt(original_code: str, instruction: str) -> str:
    lines = original_code.splitlines()
    numbered_code = "\n".join(f"{i+1:3d}: {line}" for i, line in enumerate(lines))
    prompt = (
        f"<|im_start|>system\n{SYSTEM_PROMPT_LOCATE}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"### CODE:\n{numbered_code}\n\n"
        f"### INSTRUCTION:\n{instruction}\n<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    return prompt


def format_infill_prompt(masked_code: str, instruction: str) -> str:
    prompt = (
        f"<|im_start|>system\n{SYSTEM_PROMPT_INFILL}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"### MASKED CODE:\n{masked_code}\n\n"
        f"### INSTRUCTION:\n{instruction}\n<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    return prompt
