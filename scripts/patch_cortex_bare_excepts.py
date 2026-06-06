#!/usr/bin/env python3
"""Fix bare except:pass patterns in cortex.py by adding logging.

The cortex.py file exceeds the 100K character limit for str_replace,
so we use this script to apply the fix directly.

This script handles varying indentation levels correctly.
"""
import re
import sys

FILEPATH = "backend/ai/cortex.py"

def main():
    with open(FILEPATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    original = lines.copy()
    changes = 0

    for i, line in enumerate(lines):
        stripped = line.rstrip()
        # Match lines like "except Exception:pass" or "except Exception: pass"
        # with any leading whitespace
        match = re.match(r'^(\s*)(except\s+Exception\s*:\s*)pass\s*$', stripped)
        if match:
            indent = match.group(1)
            # Replace pass with a logged debug message at the same indentation
            lines[i] = f"{indent}except Exception:\n{indent}    logger.debug(\"Non-critical exception suppressed\")\n"
            changes += 1
            continue

        # Also handle "except Exception as e: pass" pattern
        match = re.match(r'^(\s*)(except\s+Exception\s+as\s+\w+\s*:\s*)pass\s*$', stripped)
        if match:
            indent = match.group(1)
            lines[i] = f"{indent}except Exception as e:\n{indent}    logger.debug(\"Non-critical exception suppressed: %s\", e)\n"
            changes += 1

    if changes == 0:
        print("WARNING: No bare except:pass patterns found. File may already be fixed.")
        # Show current state for debugging
        for i, line in enumerate(lines):
            if 'except' in line.lower() and 'pass' in line.lower():
                print(f"  Line {i+1}: {line.rstrip()}")
        sys.exit(1)

    with open(FILEPATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"SUCCESS: Fixed {changes} bare except:pass patterns in {FILEPATH}")

    # Verify
    remaining = 0
    with open(FILEPATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if re.search(r'except.*:\s*pass\s*$', line.rstrip()):
                remaining += 1
                print(f"  REMAINING at line {i}: {line.rstrip()}")
    if remaining:
        print(f"WARNING: {remaining} bare except:pass patterns remain")
    else:
        print("VERIFIED: No bare except:pass patterns remain in cortex.py")

if __name__ == "__main__":
    main()
