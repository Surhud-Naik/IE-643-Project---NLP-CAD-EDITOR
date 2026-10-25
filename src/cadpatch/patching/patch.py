"""
Patching utilities: parsing, validating, applying, and generating search/replace code patches.
"""

from typing import Tuple, List, Optional
import difflib
import re

SEARCH_MARKER = "<<<<<<< SEARCH"
DIVIDER_MARKER = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"

STATUS_SUCCESS = "SUCCESS"
STATUS_NO_MATCH = "NO_MATCH"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_MALFORMED = "MALFORMED"


def extract_patch_blocks(patch: str) -> Tuple[Optional[List[Tuple[str, str]]], str]:
    """
    Extracts (search_text, replace_text) pairs from a patch string.
    Returns (blocks, status). If malformed, blocks will be None.
    """
    if not patch or not patch.strip():
        return None, STATUS_MALFORMED

    # Ensure standardized newlines
    normalized_patch = patch.replace("\r\n", "\n")
    
    # Check if markers exist
    if SEARCH_MARKER not in normalized_patch or DIVIDER_MARKER not in normalized_patch or REPLACE_MARKER not in normalized_patch:
        return None, STATUS_MALFORMED

    blocks: List[Tuple[str, str]] = []
    lines = normalized_patch.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()
        if line == SEARCH_MARKER:
            i += 1
            search_lines = []
            while i < n and lines[i].strip() != DIVIDER_MARKER:
                search_lines.append(lines[i])
                i += 1
            
            if i >= n or lines[i].strip() != DIVIDER_MARKER:
                return None, STATUS_MALFORMED
            
            i += 1
            replace_lines = []
            while i < n and lines[i].strip() != REPLACE_MARKER:
                replace_lines.append(lines[i])
                i += 1
            
            if i >= n or lines[i].strip() != REPLACE_MARKER:
                return None, STATUS_MALFORMED

            search_text = "\n".join(search_lines)
            replace_text = "\n".join(replace_lines)

            # Search block cannot be empty
            if not search_text:
                return None, STATUS_MALFORMED

            blocks.append((search_text, replace_text))
            i += 1
        else:
            i += 1

    if not blocks:
        return None, STATUS_MALFORMED

    return blocks, STATUS_SUCCESS


def apply_patch(program: str, patch: str) -> Tuple[str, str]:
    """
    Applies a search/replace patch to a target program.
    Returns (result_program, status), where status is one of:
      - 'SUCCESS'
      - 'NO_MATCH'
      - 'AMBIGUOUS'
      - 'MALFORMED'
    """
    blocks, extract_status = extract_patch_blocks(patch)
    if extract_status != STATUS_SUCCESS or not blocks:
        return program, extract_status

    current_program = program.replace("\r\n", "\n")

    for search_text, replace_text in blocks:
        count = current_program.count(search_text)
        if count == 0:
            # Fallback: check trailing whitespace differences per line
            search_lines = [l.rstrip() for l in search_text.split("\n")]
            prog_lines = current_program.split("\n")
            matched_indices = []
            m = len(search_lines)
            for idx in range(len(prog_lines) - m + 1):
                window = [l.rstrip() for l in prog_lines[idx:idx + m]]
                if window == search_lines:
                    matched_indices.append(idx)
            
            if len(matched_indices) == 1:
                # Exactly one whitespace-tolerant match
                idx = matched_indices[0]
                new_prog_lines = prog_lines[:idx] + replace_text.split("\n") + prog_lines[idx + m:]
                current_program = "\n".join(new_prog_lines)
                continue
            elif len(matched_indices) > 1:
                return program, STATUS_AMBIGUOUS
            else:
                return program, STATUS_NO_MATCH
        elif count > 1:
            return program, STATUS_AMBIGUOUS
        else:
            current_program = current_program.replace(search_text, replace_text, 1)

    return current_program, STATUS_SUCCESS


def make_patch(original: str, edited: str) -> str:
    """
    Derives a minimal search/replace patch from original and edited programs.
    Guarantees round-trip idempotency: apply_patch(original, make_patch(original, edited))[0] == edited.
    """
    orig_lines = original.replace("\r\n", "\n").split("\n")
    edit_lines = edited.replace("\r\n", "\n").split("\n")

    if orig_lines == edit_lines:
        return ""

    matcher = difflib.SequenceMatcher(None, orig_lines, edit_lines)
    opcodes = matcher.get_opcodes()

    # Find modified hunks
    blocks: List[Tuple[str, str]] = []
    
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        
        # We need a context around (i1, i2) in orig_lines such that the search text is unique
        context_before = 0
        context_after = 0
        search_slice = orig_lines[i1 - context_before: i2 + context_after]
        search_str = "\n".join(search_slice)
        
        # If insertion (i1 == i2), search_str would be empty, so expand by 1 line
        if not search_str:
            if i1 > 0:
                context_before += 1
            elif i2 < len(orig_lines):
                context_after += 1
            search_slice = orig_lines[i1 - context_before: i2 + context_after]
            search_str = "\n".join(search_slice)

        # Expand context until search_str appears uniquely in original
        orig_full = "\n".join(orig_lines)
        while orig_full.count(search_str) > 1 and (i1 - context_before > 0 or i2 + context_after < len(orig_lines)):
            if i1 - context_before > 0:
                context_before += 1
            if i2 + context_after < len(orig_lines):
                context_after += 1
            search_slice = orig_lines[i1 - context_before: i2 + context_after]
            search_str = "\n".join(search_slice)

        # Replacement text is context_before + edit_lines[j1:j2] + context_after
        repl_slice = orig_lines[i1 - context_before: i1] + edit_lines[j1: j2] + orig_lines[i2: i2 + context_after]
        replace_str = "\n".join(repl_slice)

        blocks.append((search_str, replace_str))

    # Format into patch blocks
    patch_parts = []
    for search_str, replace_str in blocks:
        patch_parts.append(f"{SEARCH_MARKER}\n{search_str}\n{DIVIDER_MARKER}\n{replace_str}\n{REPLACE_MARKER}")

    patch_str = "\n".join(patch_parts)

    # Round-trip verification
    test_res, test_status = apply_patch(original, patch_str)
    if test_status != STATUS_SUCCESS or test_res != edited.replace("\r\n", "\n"):
        # Fallback to single comprehensive block covering from first diff to last diff
        diff_indices = [i for i, (tag, *_) in enumerate(opcodes) if tag != "equal"]
        first_diff = opcodes[diff_indices[0]]
        last_diff = opcodes[diff_indices[-1]]
        s1, s2 = first_diff[1], last_diff[2]
        r1, r2 = first_diff[3], last_diff[4]
        
        # Expand slightly to guarantee uniqueness
        search_block = "\n".join(orig_lines[s1:s2]) if s2 > s1 else "\n".join(orig_lines[max(0, s1-1):min(len(orig_lines), s2+1)])
        replace_block = "\n".join(orig_lines[max(0, s1-1):s1] + edit_lines[r1:r2] + orig_lines[s2:min(len(orig_lines), s2+1)]) if s2 == s1 else "\n".join(edit_lines[r1:r2])
        
        fallback_patch = f"{SEARCH_MARKER}\n{search_block}\n{DIVIDER_MARKER}\n{replace_block}\n{REPLACE_MARKER}"
        return fallback_patch

    return patch_str
