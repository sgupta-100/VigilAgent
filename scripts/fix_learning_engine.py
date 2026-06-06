#!/usr/bin/env python3
"""Batch fix print→logger and hashlib.md5→sha256 in learning_engine.py."""
FILE = "backend/core/learning_engine.py"

with open(FILE, "r", encoding="utf-8") as f:
    content = f.read()

original = content

# 1. Add logging import after asyncio
if "import logging" not in content:
    content = content.replace(
        "import asyncio\n",
        "import asyncio\nimport logging\n"
    )

if "logger = logging.getLogger" not in content:
    content = content.replace(
        'from backend.core.unified_knowledge_graph import knowledge_graph\n',
        'from backend.core.unified_knowledge_graph import knowledge_graph\n\nlogger = logging.getLogger("LearningEngine")\n'
    )

# 2. Replace hashlib.md5 with hashlib.sha256
content = content.replace(
    "hashlib.md5(pattern['domain'].encode())",
    "hashlib.sha256(pattern['domain'].encode())"
)

# 3. Replace print() → logger calls
replacements = [
    ('print(f"[LearningEngine] Loaded {len(self.patterns)} patterns from disk")', 'logger.debug(f"[LearningEngine] Loaded {len(self.patterns)} patterns from disk")'),
    ('print(f"[LearningEngine] Failed to load patterns: {e}")', 'logger.warning(f"[LearningEngine] Failed to load patterns: {e}")'),
    ('print(f"[LearningEngine] Failed to save patterns: {e}")', 'logger.error(f"[LearningEngine] Failed to save patterns: {e}")'),
    ('print(f"[LearningEngine] Failed to load metrics: {e}")', 'logger.warning(f"[LearningEngine] Failed to load metrics: {e}")'),
    ('print(f"[LearningEngine] Failed to save metrics: {e}")', 'logger.error(f"[LearningEngine] Failed to save metrics: {e}")'),
    ('print(f"[LearningEngine] Learning from {vuln_type} vulnerability at {url}")', 'logger.info(f"[LearningEngine] Learning from {vuln_type} vulnerability at {url}")'),
    ('print(f"[LearningEngine] Failed to learn correlations: {e}")', 'logger.warning(f"[LearningEngine] Failed to learn correlations: {e}")'),
    ('print("[LearningEngine] Consolidating patterns...")', 'logger.debug("[LearningEngine] Consolidating patterns...")'),
    ('print(f"[LearningEngine] Consolidated {consolidated_count} patterns")', 'logger.debug(f"[LearningEngine] Consolidated {consolidated_count} patterns")'),
    ('print(f"[LearningEngine] Analyzing completed scan: {scan_id}")', 'logger.info(f"[LearningEngine] Analyzing completed scan: {scan_id}")'),
    ('print(f"[LearningEngine] browser-vuln persist failed: {e}")', 'logger.warning(f"[LearningEngine] browser-vuln persist failed: {e}")'),
    ('print(f"[LearningEngine] learn_from_browser_vulnerability failed: {e}")', 'logger.error(f"[LearningEngine] learn_from_browser_vulnerability failed: {e}")'),
    ('print(f"[LearningEngine] lock acquire failed: {e}")', 'logger.warning(f"[LearningEngine] lock acquire failed: {e}")'),
    ('print(f"[LearningEngine] lock clear failed: {e}")', 'logger.warning(f"[LearningEngine] lock clear failed: {e}")'),
    ('print(f"[LearningEngine] browser-workflow persist failed: {e}")', 'logger.warning(f"[LearningEngine] browser-workflow persist failed: {e}")'),
    ('print(f"[LearningEngine] learn_browser_workflow failed: {e}")', 'logger.error(f"[LearningEngine] learn_browser_workflow failed: {e}")'),
    ('print(f"[LearningEngine] framework-pattern persist failed: {e}")', 'logger.warning(f"[LearningEngine] framework-pattern persist failed: {e}")'),
    ('print(f"[LearningEngine] learn_framework_pattern failed: {e}")', 'logger.error(f"[LearningEngine] learn_framework_pattern failed: {e}")'),
    # BrowserLearningExtension
    ('print(f"[BrowserLearning] Lock acquisition failed: {e}")', 'logger.warning(f"[BrowserLearning] Lock acquisition failed: {e}")'),
    ('print(f"[BrowserLearning] Lock release failed: {e}")', 'logger.warning(f"[BrowserLearning] Lock release failed: {e}")'),
    # CrossSystemLearningExtension
    ('print(f"[CrossSystemLearning] Identified {len(hybrid_patterns)} hybrid patterns")', 'logger.info(f"[CrossSystemLearning] Identified {len(hybrid_patterns)} hybrid patterns")'),
    ('print(f"[CrossSystemLearning] Tracked HTTP-browser correlation: {correlation_data[\'overlap_rate\']:.1%} overlap")', 'logger.info(f"[CrossSystemLearning] Tracked HTTP-browser correlation: {correlation_data[\'overlap_rate\']:.1%} overlap")'),
]

count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        count += 1

if content != original:
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"SUCCESS: Applied {count} replacements")
else:
    print("NO_CHANGES: File unchanged")
