#!/usr/bin/env python3
"""Fix all bare except:pass patterns and HIGH-65 in cortex.py directly.

This script handles the file being too large for str_replace by reading
and modifying it line by line.
"""
import re
import sys

FILEPATH = "backend/ai/cortex.py"

def main():
    with open(FILEPATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changes = 0
    
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        
        # Fix HIGH-65: Add nonce to second validation call
        if 'result_pass_2 = await self._call_nvidia_validation_model(prompt,' in line:
            indent = len(line) - len(line.lstrip())
            spaces = ' ' * indent
            lines[i] = (
                f'{spaces}# HIGH-65: nonce suffix defeats cache on second pass for dual-pass validation\n'
                f'{spaces}result_pass_2 = await self._call_nvidia_validation_model(prompt + "\\n[VALIDATION_PASS_2]", max_tokens=4096, scan_ctx=scan_ctx)\n'
            )
            changes += 1
            continue
        
        # Fix bare except Exception: pass (various spacing patterns)
        match = re.match(r'^(\s*)(except\s+Exception\s*:\s*)pass\s*$', stripped)
        if match:
            indent = match.group(1)
            lines[i] = f"{indent}except Exception:\n{indent}    logger.debug(\"Non-critical exception suppressed\")\n"
            changes += 1
            continue
        
        # Fix except Exception:return patterns (inline return)
        match = re.match(r'^(\s*)(except\s+Exception\s*:)\s*return\s*(.*)$', stripped)
        if match:
            indent = match.group(1)
            return_val = match.group(3).strip()
            lines[i] = f"{indent}except Exception as e:\n{indent}    logger.debug(\"Non-critical exception suppressed: %s\", e)\n{indent}    return {return_val}\n"
            changes += 1
            continue

    if changes == 0:
        print("WARNING: No patterns found to fix")
        sys.exit(1)

    with open(FILEPATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"SUCCESS: Fixed {changes} patterns in {FILEPATH}")

    # Verify
    remaining = 0
    with open(FILEPATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            stripped = line.rstrip()
            # Check for remaining bare except:pass
            if re.search(r'except\s+Exception\s*:\s*pass\s*$', stripped):
                remaining += 1
                print(f"  REMAINING bare except:pass at line {i}: {stripped}")
            # Check for remaining except Exception:return without logging
            if re.search(r'except\s+Exception\s*:\s*return\s', stripped):
                remaining += 1
                print(f"  REMAINING except Exception:return at line {i}: {stripped}")
    
    if remaining:
        print(f"WARNING: {remaining} patterns remain")
    else:
        print("VERIFIED: All bare except:pass patterns fixed in cortex.py")

if __name__ == "__main__":
    main()
