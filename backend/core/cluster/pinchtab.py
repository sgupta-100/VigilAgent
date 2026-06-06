"""
PINCHTAB BROWSER INSTANCE
Role: Isolated browser execution for complex DOM fuzzing and IDOR detection.
Extracted from orchestrator.py for clean architecture.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
from typing import Dict, List, Optional

logger = logging.getLogger("PinchTab")

from playwright.async_api import async_playwright

from backend.integrations.pinchtab_client import PinchTabClient


class PinchTabInstance:
    """Isolated browser execution for complex DOM fuzzing and IDOR detection."""

    def __init__(self, worker_id: str, port: int):
        # Sanitize worker_id to prevent path traversal (CRIT-07)
        self.worker_id = re.sub(r'[^a-zA-Z0-9_-]', '', worker_id)
        self.port = port
        self.profile_path = os.path.join(tempfile.gettempdir(), "pinchtab_profiles", self.worker_id)
        self.browser = None
        self.context = None
        self.page = None
        self.client = PinchTabClient()
        self.instance_id = ""
        self.profile_id = ""
        self.tab_id = ""
        self.using_control_plane = False
        # CRIT-15: Lock serializes start/stop to prevent race on using_control_plane
        self._lifecycle_lock = asyncio.Lock()
        os.makedirs(self.profile_path, exist_ok=True)

    async def start(self):
        # CRIT-15: Serialize lifecycle transitions under the same lock as stop()
        async with self._lifecycle_lock:
            try:
                await self.client.health()
                profile = await self.client.create_profile(f"worker-{self.worker_id}", "Vulagent worker browser profile")
                self.profile_id = str(profile.get("id") or profile.get("profileId") or "")
                instance = await self.client.start_instance(self.profile_id or None, mode="headless")
                self.instance_id = str(instance.get("id") or instance.get("instanceId") or "")
                self.using_control_plane = bool(self.instance_id)
                if self.using_control_plane:
                    logger.info(f"PinchTab control-plane instance online (Worker: {self.worker_id}, Instance: {self.instance_id})")
                    return
            except Exception as e:
                logger.warning(f"PinchTab control-plane unavailable for worker {self.worker_id}; using local Playwright fallback: {e}")

            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        f"--user-data-dir={self.profile_path}",
                        f"--remote-debugging-port={self.port}",
                        "--no-sandbox",
                        "--disable-dev-shm-usage"
                    ]
                )
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                logger.info(f"PinchTab Playwright fallback online (Worker: {self.worker_id}, Port: {self.port})")
            except Exception as e:
                logger.error(f"PinchTab failed to initialize: {e}")

    async def execute_flow(self, flow_config: Dict) -> Dict:
        results = {"steps": [], "findings": []}
        try:
            for step in flow_config.get("actions_mapped", []):
                step_result = await self._execute_semantic_step(step, flow_config.get("target_url"))
                if step_result:
                    results["steps"].append(step_result)

                if step_result and step_result.get("success"):
                    vulnerabilities = await self._check_vulnerabilities(step_result)
                    results["findings"].extend(vulnerabilities)
            results["post_state"] = await self._extract_state()
        except Exception as e:
            results["error"] = str(e)
        return results

    async def _execute_semantic_step(self, step: Dict, target_url: str) -> Optional[Dict]:
        result = {"action": step["type"], "target": step["target"], "success": False}
        try:
            if self.using_control_plane:
                if target_url and not self.tab_id:
                    nav = await self.client.navigate(target_url)
                    self.tab_id = str(nav.get("tabId") or nav.get("id") or nav.get("targetId") or "")
                    if self.tab_id:
                        await self.client.wait_for_load(self.tab_id)
                if not self.tab_id:
                    result["error"] = "pinchtab_tab_unavailable"
                    return result

                target_str = str(step["target"])
                if step["type"] == "input":
                    selector = f"input[name='{target_str}'], input[id='{target_str}'], *[placeholder*='{target_str}' i]"
                    await self.client.action(self.tab_id, "fill", selector=selector, value="xytherion_fuzz_payload")
                    result["success"] = True
                elif step["type"] == "click":
                    await self.client.action(self.tab_id, "click", selector=f"text:{target_str}", wait_nav=True)
                    result["success"] = True
                return result

            target_str = str(step["target"])
            if step["type"] == "input":
                selector = f"input[name='{target_str}'], input[id='{target_str}'], *[placeholder*='{target_str}' i]"
                if await self.page.locator(selector).count() > 0:
                    await self.page.fill(selector, "xytherion_fuzz_payload")
                    result["success"] = True
            elif step["type"] == "click":
                selector = f"button:text-matches('(?i){target_str}'), input[type='submit'][value*='(?i){target_str}']"
                if await self.page.locator(selector).count() > 0:
                    await self.page.click(selector)
                    result["success"] = True
        except Exception as e:
            result["error"] = str(e)
        return result

    async def _extract_state(self) -> Dict:
        state = {"cookies": [], "tokens": {}}
        try:
            if self.using_control_plane and self.tab_id:
                state["cookies"] = await self.client.cookies(self.tab_id)
                state["text"] = await self.client.text(self.tab_id)
                state["network"] = await self.client.network(self.tab_id)
                return state

            state["cookies"] = await self.context.cookies()
            local_storage = await self.page.evaluate("() => JSON.stringify(window.localStorage)")
            session_storage = await self.page.evaluate("() => JSON.stringify(window.sessionStorage)")
            state["tokens"]["local"] = json.loads(local_storage)
            state["tokens"]["session"] = json.loads(session_storage)
        except Exception as exc:
            import logging
            logging.getLogger("PinchTab").debug("PinchTab state extraction failed: %s", exc)
        return state

    async def _check_vulnerabilities(self, step_result: Dict) -> List[Dict]:
        vulns = []
        if self.using_control_plane and self.tab_id:
            content = str(await self.client.text(self.tab_id))
            if "<script>alert(1)</script>" in content:
                vulns.append({"type": "xss", "severity": "HIGH", "desc": "Reflected payload text detected."})
            return vulns

        content = await self.page.content()
        if "<script>alert(1)</script>" in content:
            vulns.append({"type": "xss", "severity": "HIGH", "desc": "Reflected Payload detected."})
        return vulns

    async def stop(self):
        # CRIT-15: Serialize lifecycle transitions under a lock
        async with self._lifecycle_lock:
            try:
                if self.using_control_plane and self.instance_id:
                    await self.client.stop_instance(self.instance_id)
                    self.using_control_plane = False
                    return

                if self.browser:
                    await self.browser.close()
                if hasattr(self, 'playwright'):
                    await self.playwright.stop()
                # Validate profile_path is within expected directory before deletion (CRIT-16)
                if os.path.exists(self.profile_path):
                    expected_base = os.path.normpath(os.path.join(tempfile.gettempdir(), "pinchtab_profiles"))
                    real_path = os.path.realpath(self.profile_path)
                    if real_path.startswith(expected_base):
                        shutil.rmtree(self.profile_path, ignore_errors=True)
            except Exception as exc:
                import logging
                logging.getLogger("PinchTab").error("PinchTab stop failed for %s: %s", self.worker_id, exc)
