#!/usr/bin/env python3
"""Batch fix bare except blocks in cortex.py by adding logging."""
FILE = "backend/ai/cortex.py"

with open(FILE, "r", encoding="utf-8") as f:
    content = f.read()

original = content

# Fix pattern: `except Exception: pass` → `except Exception as e:\n                logger.debug(f"...")`
replacements = [
    ('except Exception: pass\n', 'except Exception as e:\n                logger.debug(f"CORTEX: exception: {e}")\n'),
    ('except Exception:pass\n', 'except Exception as e:\n                logger.debug(f"CORTEX: exception: {e}")\n'),
]

# Fix single-line except Exception:return patterns
import re
# Pattern: `except Exception:return {}` etc
def fix_inline_excepts(text):
    pattern = r'except Exception:return (\{?\}?\[?\]?)'
    def replacer(m):
        ret_val = m.group(1)
        return f'except Exception as e:\n                logger.debug(f"GI5 exception: {{e}}")\n                return {ret_val}'
    return re.sub(pattern, replacer, text)

content = fix_inline_excepts(content)

# Count changes
for old, new in replacements:
    count = content.count(old)
    content = content.replace(old, new)

if content != original:
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: cortex.py bare except blocks fixed")
else:
    print("NO_CHANGES: File unchanged")
