"""Tests for backend.modules.tech.jwt — JWT parsing, forging, cracking."""
import base64
import json
import hmac
import hashlib
import pytest
from backend.modules.tech.jwt import (
    parse_jwt, forge_alg_none, forge_hs256, crack_hs256_secret,
    _b64url_decode, _b64url_encode,
)


def _make_jwt(header_dict, payload_dict, secret=None, alg="HS256"):
    """Helper to create properly-encoded JWTs."""
    header_b64 = _b64url_encode(json.dumps(header_dict).encode())
    payload_b64 = _b64url_encode(json.dumps(payload_dict).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    if alg == "none":
        sig = ""
    elif secret:
        sig = _b64url_encode(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    else:
        sig = _b64url_encode(b"fake_signature_bytes")
    return f"{header_b64}.{payload_b64}.{sig}"


class TestB64UrlEncodeDecode:
    def test_roundtrip(self):
        original = b"hello world"
        encoded = _b64url_encode(original)
        decoded = _b64url_decode(encoded)
        assert decoded == original

    def test_encode_returns_string(self):
        result = _b64url_encode(b"test")
        assert isinstance(result, str)

    def test_empty_bytes(self):
        encoded = _b64url_encode(b"")
        decoded = _b64url_decode(encoded)
        assert decoded == b""


class TestParseJwt:
    def test_valid_jwt(self):
        token = _make_jwt({"alg": "HS256", "typ": "JWT"}, {"sub": "123"})
        result = parse_jwt(token)
        assert result["valid"] is True
        assert result["header"]["alg"] == "HS256"
        assert result["payload"]["sub"] == "123"

    def test_missing_parts(self):
        result = parse_jwt("only_header")
        assert result["valid"] is False

    def test_empty_token(self):
        result = parse_jwt("")
        assert result["valid"] is False

    def test_missing_alg(self):
        token = _make_jwt({"typ": "JWT"}, {"sub": "123"})
        result = parse_jwt(token)
        assert result["valid"] is False

    def test_none_token(self):
        result = parse_jwt(None)
        assert result["valid"] is False


class TestForgeAlgNone:
    def test_forge(self):
        token = _make_jwt({"alg": "HS256", "typ": "JWT"}, {"sub": "123"})
        forged = forge_alg_none(token)
        assert forged != token
        # Parse the forged token to verify alg is "none"
        result = parse_jwt(forged)
        assert result.get("alg", "").lower() == "none" or result["header"].get("alg", "").lower() == "none"


class TestForgeHs256:
    def test_forge(self):
        token = _make_jwt({"alg": "HS256", "typ": "JWT"}, {"sub": "123"})
        forged = forge_hs256(token, "secret123")
        assert forged != token
        result = parse_jwt(forged)
        assert result["valid"] is True


class TestCrackHs256:
    def test_crack_with_correct_secret(self):
        token = _make_jwt({"alg": "HS256", "typ": "JWT"}, {"sub": "123"}, secret="password")
        result = crack_hs256_secret(token, ["wrong", "password", "also_wrong"])
        assert result == "password"

    def test_crack_no_match(self):
        token = _make_jwt({"alg": "HS256", "typ": "JWT"}, {"sub": "123"}, secret="real_secret")
        result = crack_hs256_secret(token, ["a", "b", "c"])
        assert result is None

    def test_crack_empty_candidates(self):
        token = _make_jwt({"alg": "HS256"}, {"sub": "123"}, secret="secret")
        result = crack_hs256_secret(token, [])
        assert result is None
