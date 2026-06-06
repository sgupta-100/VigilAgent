"""Fix HIGH-85: Replace hashlib.md5 with hashlib.sha256 in learning_engine.py"""
import sys
import os

path = os.path.join(os.path.dirname(__file__), "..", "backend", "core", "learning_engine.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = "hashlib.md5(pattern['domain'].encode()).hexdigest()[:12]"
new = "hashlib.sha256(pattern['domain'].encode()).hexdigest()[:12]"

count = content.count(old)
if count == 0:
    print("Already fixed or pattern not found")
    sys.exit(0)

content = content.replace(old, new, 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)

# Verify
with open(path, "r", encoding="utf-8") as f:
    verify = f.read()

if "hashlib.md5" not in verify and "hashlib.sha256(pattern" in verify:
    print("SUCCESS: hashlib.md5 replaced with hashlib.sha256 in learning_engine.py")
else:
    print("FAILED: Verification did not pass")
    sys.exit(1)
