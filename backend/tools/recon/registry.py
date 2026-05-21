"""Alpha V6 Recon Tool Registry — Full 26-Tool Matrix."""
from __future__ import annotations
import shutil
from pathlib import Path
from backend.core.config import settings


RECON_TOOLS = {
    # Phase 1: Passive Intelligence
    "subfinder":    {"phase": "passive_intelligence",    "binary": "subfinder",    "modes": ["PASSIVE_ONLY", "STANDARD", "AGGRESSIVE"]},
    "amass":        {"phase": "passive_intelligence",    "binary": "amass",        "modes": ["PASSIVE_ONLY", "STANDARD", "AGGRESSIVE"]},
    "gau":          {"phase": "passive_intelligence",    "binary": "gau",          "modes": ["PASSIVE_ONLY", "STANDARD", "AGGRESSIVE"]},
    "waybackurls":  {"phase": "passive_intelligence",    "binary": "waybackurls",  "modes": ["PASSIVE_ONLY", "STANDARD", "AGGRESSIVE"]},
    "cloudlist":    {"phase": "passive_intelligence",    "binary": "cloudlist",    "modes": ["STANDARD", "AGGRESSIVE"]},
    "spiderfoot":   {"phase": "passive_intelligence",    "binary": "spiderfoot",   "modes": ["AGGRESSIVE"]},
    # Phase 2: DNS & Infrastructure
    "dnsx":         {"phase": "dns_infrastructure",      "binary": "dnsx",         "modes": ["STANDARD", "AGGRESSIVE"]},
    "shuffledns":   {"phase": "dns_infrastructure",      "binary": "shuffledns",   "modes": ["AGGRESSIVE"]},
    "naabu":        {"phase": "dns_infrastructure",      "binary": "naabu",        "modes": ["STANDARD", "AGGRESSIVE"]},
    "nmap":         {"phase": "dns_infrastructure",      "binary": "nmap",         "modes": ["AGGRESSIVE"]},
    "tlsx":         {"phase": "dns_infrastructure",      "binary": "tlsx",         "modes": ["STANDARD", "AGGRESSIVE"]},
    # Phase 3: HTTP & Browser Intelligence
    "httpx":        {"phase": "http_browser_intelligence","binary": "httpx",       "modes": ["STANDARD", "AGGRESSIVE"]},
    "katana":       {"phase": "http_browser_intelligence","binary": "katana",      "modes": ["STANDARD", "AGGRESSIVE"]},
    "hakrawler":    {"phase": "http_browser_intelligence","binary": "hakrawler",   "modes": ["STANDARD", "AGGRESSIVE"]},
    "linkfinder":   {"phase": "http_browser_intelligence","binary": "python",      "modes": ["STANDARD", "AGGRESSIVE"]},
    "secretfinder": {"phase": "http_browser_intelligence","binary": "python",      "modes": ["STANDARD", "AGGRESSIVE"]},
    # Phase 4: Directory & Route Discovery
    "feroxbuster":  {"phase": "directory_route_discovery","binary": "feroxbuster", "modes": ["STANDARD", "AGGRESSIVE"]},
    "ffuf":         {"phase": "directory_route_discovery","binary": "ffuf",        "modes": ["STANDARD", "AGGRESSIVE"]},
    "dirsearch":    {"phase": "directory_route_discovery","binary": "python",      "modes": ["STANDARD", "AGGRESSIVE"]},
    "gobuster":     {"phase": "directory_route_discovery","binary": "gobuster",    "modes": ["STANDARD", "AGGRESSIVE"]},
    # Phase 5: API Reconnaissance
    "kiterunner":   {"phase": "api_reconnaissance",      "binary": "kr",          "modes": ["STANDARD", "AGGRESSIVE"]},
    "inql":         {"phase": "api_reconnaissance",      "binary": "python",      "modes": ["AGGRESSIVE"]},
    # Phase 6: Visual Documentation
    "gowitness":    {"phase": "visual_documentation",    "binary": "gowitness",    "modes": ["STANDARD", "AGGRESSIVE"]},
    # Phase 7: Template Validation
    "nuclei":       {"phase": "template_validation",     "binary": "nuclei",       "modes": ["STANDARD", "AGGRESSIVE"]},
    "interactsh":   {"phase": "template_validation",     "binary": "interactsh-client", "modes": ["AGGRESSIVE"]},
}


def check_tool_availability(name: str) -> dict:
    """Check if a tool is installed and accessible."""
    spec = RECON_TOOLS.get(name)
    if not spec:
        return {"installed": False, "reason": f"unknown_tool:{name}"}
    binary = spec["binary"]
    tool_root = Path(getattr(settings, "ALPHA_TOOL_ROOT", r"D:\projects"))

    # Check PATH first
    path = shutil.which(binary)
    if path:
        return {"installed": True, "path": path, "source": "PATH"}

    # Check tool_root for Go binaries
    go_bin = tool_root / binary
    if go_bin.exists():
        return {"installed": True, "path": str(go_bin), "source": "tool_root"}

    # Check for Python scripts
    if binary == "python":
        script_map = {
            "linkfinder": tool_root / "LinkFinder" / "linkfinder.py",
            "secretfinder": tool_root / "SecretFinder" / "SecretFinder.py",
            "dirsearch": tool_root / "dirsearch" / "dirsearch.py",
            "inql": tool_root / "inql" / "inql.py",
            "spiderfoot": tool_root / "spiderfoot" / "sf.py",
        }
        script = script_map.get(name)
        if script and script.exists():
            return {"installed": True, "path": str(script), "source": "python_script"}
        return {"installed": False, "reason": f"script_not_found:{name}"}

    return {"installed": False, "reason": f"binary_not_in_path:{binary}"}
