#!/usr/bin/env python3
"""Patch cortex.py for HIGH-65: add nonce to second validation call.

The self-consistency validation calls _call_nvidia_validation_model twice
with identical prompts. The cache returns identical results, defeating
the entire dual-pass validation purpose. This patch adds a unique suffix
to the second call so it bypasses the cache.
"""
import re
import sys

path = "backend/ai/cortex.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

changed = False
for i, line in enumerate(lines):
    # Find the second validation call (result_pass_2) at line ~1112
    if 'result_pass_2 = await self._call_nvidia_validation_model(prompt,' in line:
        # Add nonce suffix to defeat cache on second pass
        lines[i] = line.replace(
            'result_pass_2 = await self._call_nvidia_validation_model(prompt,',
            '# HIGH-65: nonce suffix defeats cache on second pass for dual-pass validation\n'
            '        result_pass_2 = await self._call_nvidia_validation_model(prompt + "\\n[VALIDATION_PASS_2]",'
        )
        changed = True
        break

if changed:
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"HIGH-65 patched: {path} (nonce added to second validation call)")
else:
    print("Pattern not found in cortex.py - may already be patched or line numbers shifted")
    # Show diagnostic info
    for i, line in enumerate(lines):
        if 'result_pass_2' in line and 'validation_model' in line:
            print(f"  Found at line {i+1}: {line.rstrip()}")
