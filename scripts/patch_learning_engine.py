#!/usr/bin/env python3
"""
Patch learning_engine.py:
1. Add import logging and logger instance
2. Replace hashlib.md5 -> hashlib.sha256
3. Replace all print() -> logger calls with appropriate levels

Run: python scripts/patch_learning_engine.py
"""
import re, sys

FILE = "backend/core/learning_engine.py"

with open(FILE, "r", encoding="utf-8") as f:
    content = f.read()

original = content

# ── Step 1: Add imports ──────────────────────────────────────────────
if "import logging" not in content:
    # Add hashlib and logging after asyncio import
    content = content.replace(
        "import asyncio\nimport json",
        "import asyncio\nimport hashlib\nimport json\nimport logging",
        1,
    )

# ── Step 2: Add logger instance after knowledge_graph import ─────────
if 'logger = logging.getLogger("LearningEngine")' not in content:
    content = content.replace(
        'from backend.core.unified_knowledge_graph import knowledge_graph\n',
        'from backend.core.unified_knowledge_graph import knowledge_graph\n\nlogger = logging.getLogger("LearningEngine")\n',
        1,
    )

# ── Step 3: Replace hashlib.md5 -> hashlib.sha256 ────────────────────
content = content.replace(
    "hashlib.md5(pattern['domain'].encode())",
    "hashlib.sha256(pattern['domain'].encode())",
)

# ── Step 4: Replace print() -> logger calls ──────────────────────────
# Each tuple: (exact_old_string, replacement)
# We replace from most-specific to least-specific to avoid partial matches.

replacements = [
    # ContinuousLearningEngine methods
    ('print(f"[LearningEngine] Loaded {len(self.patterns)} patterns from disk")',
     'logger.debug(f"[LearningEngine] Loaded {len(self.patterns)} patterns from disk")'),

    ('print(f"[LearningEngine] Failed to load patterns: {e}")',
     'logger.warning(f"[LearningEngine] Failed to load patterns: {e}")'),

    ('print(f"[LearningEngine] Failed to save patterns: {e}")',
     'logger.error(f"[LearningEngine] Failed to save patterns: {e}")'),

    ('print(f"[LearningEngine] Failed to load metrics: {e}")',
     'logger.warning(f"[LearningEngine] Failed to load metrics: {e}")'),

    ('print(f"[LearningEngine] Failed to save metrics: {e}")',
     'logger.error(f"[LearningEngine] Failed to save metrics: {e}")'),

    ('print(f"[LearningEngine] Learning from {vuln_type} vulnerability at {url}")',
     'logger.info(f"[LearningEngine] Learning from {vuln_type} vulnerability at {url}")'),

    ('print(f"[LearningEngine] Failed to learn correlations: {e}")',
     'logger.warning(f"[LearningEngine] Failed to learn correlations: {e}")'),

    ('print("[LearningEngine] Consolidating patterns...")',
     'logger.debug("[LearningEngine] Consolidating patterns...")'),

    ('print(f"[LearningEngine] Consolidated {consolidated_count} patterns")',
     'logger.debug(f"[LearningEngine] Consolidated {consolidated_count} patterns")'),

    ('print(f"[LearningEngine] Analyzing completed scan: {scan_id}")',
     'logger.info(f"[LearningEngine] Analyzing completed scan: {scan_id}")'),

    # Browser-vulnerability learning
    ('print(f"[LearningEngine] browser-vuln persist failed: {e}")',
     'logger.warning(f"[LearningEngine] browser-vuln persist failed: {e}")'),

    ('print(f"[LearningEngine] learn_from_browser_vulnerability failed: {e}")',
     'logger.error(f"[LearningEngine] learn_from_browser_vulnerability failed: {e}")'),

    # Lock helpers
    ('print(f"[LearningEngine] lock acquire failed: {e}")',
     'logger.warning(f"[LearningEngine] lock acquire failed: {e}")'),

    ('print(f"[LearningEngine] lock clear failed: {e}")',
     'logger.warning(f"[LearningEngine] lock clear failed: {e}")'),

    # Browser-workflow learning
    ('print(f"[LearningEngine] browser-workflow persist failed: {e}")',
     'logger.warning(f"[LearningEngine] browser-workflow persist failed: {e}")'),

    ('print(f"[LearningEngine] learn_browser_workflow failed: {e}")',
     'logger.error(f"[LearningEngine] learn_browser_workflow failed: {e}")'),

    # Framework-pattern learning
    ('print(f"[LearningEngine] framework-pattern persist failed: {e}")',
     'logger.warning(f"[LearningEngine] framework-pattern persist failed: {e}")'),

    ('print(f"[LearningEngine] learn_framework_pattern failed: {e}")',
     'logger.error(f"[LearningEngine] learn_framework_pattern failed: {e}")'),

    # BrowserLearningExtension
    ('print(f"[BrowserLearning] Lock acquisition failed: {e}")',
     'logger.warning(f"[BrowserLearning] Lock acquisition failed: {e}")'),

    ('print(f"[BrowserLearning] Lock release failed: {e}")',
     'logger.warning(f"[BrowserLearning] Lock release failed: {e}")'),

    ('print(f"[BrowserLearning] Duplicate vulnerability, skipping: {idem_key}")',
     'logger.debug(f"[BrowserLearning] Duplicate vulnerability, skipping: {idem_key}")'),

    ("print(f\"[BrowserLearning] Learned from browser vulnerability: {vuln_data.get('type')}\")",
     "logger.info(f\"[BrowserLearning] Learned from browser vulnerability: {vuln_data.get('type')}\")"),

    ('print(f"[BrowserLearning] Failed to store workflow stats: {e}")',
     'logger.warning(f"[BrowserLearning] Failed to store workflow stats: {e}")'),

    ('print(f"[BrowserLearning] Promoted workflow to skill: {workflow_id}")',
     'logger.info(f"[BrowserLearning] Promoted workflow to skill: {workflow_id}")'),

    ('print(f"[BrowserLearning] Failed to store framework routes: {e}")',
     'logger.warning(f"[BrowserLearning] Failed to store framework routes: {e}")'),

    ("print(f\"[BrowserLearning] Learned {len(new_routes)} new routes for {framework}\")",
     "logger.info(f\"[BrowserLearning] Learned {len(new_routes)} new routes for {framework}\")"),

    # CrossSystemLearningExtension
    ('print(f"[CrossSystemLearning] Identified {len(hybrid_patterns)} hybrid patterns")',
     'logger.info(f"[CrossSystemLearning] Identified {len(hybrid_patterns)} hybrid patterns")'),

    ("print(f\"[CrossSystemLearning] Extracted HTTP payload from browser workflow: {workflow.get('id')}\")",
     "logger.info(f\"[CrossSystemLearning] Extracted HTTP payload from browser workflow: {workflow.get('id')}\")"),

    ("print(f\"[CrossSystemLearning] Tracked HTTP-browser correlation: {correlation_data['overlap_rate']:.1%} overlap\")",
     "logger.info(f\"[CrossSystemLearning] Tracked HTTP-browser correlation: {correlation_data['overlap_rate']:.1%} overlap\")"),
]

count = 0
not_found = []
for old, new in replacements:
    if old in content:
        content = content.replace(old, new, 1)
        count += 1
    else:
        not_found.append(old[:60] + "...")

if content != original:
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"SUCCESS: Applied {count}/{len(replacements)} replacements")
    if not_found:
        print(f"  Already converted or not found ({len(not_found)}):")
        for nf in not_found:
            print(f"    - {nf}")
else:
    print("NO_CHANGES: File unchanged (all replacements already applied)")
