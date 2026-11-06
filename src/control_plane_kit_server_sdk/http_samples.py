"""Optional signed HTTP samples bound to independent installed product values."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from control_plane_kit_core import DelegationKeyPurpose
from control_plane_kit_core.http_verification_samples import (
    HttpVerificationSampleGrantCodec, HttpVerificationSampleResult,
    HttpVerificationSampleResultCodec, verify_http_verification_sample_grant,
)
from control_plane_kit_core.http_verification_sample_installation import HttpVerificationSampleReceiverBinding
from control_plane_kit_server_sdk.verification import _decode_read_compact, _decode_structural_json
from control_plane_kit_server_sdk._http_sample_probe import _probe, _safe_path

HTTP_SAMPLE_TOKEN_TYPE = "CPK-WORKLOAD-HTTP-VERIFICATION-SAMPLE+JWT"
HTTP_SAMPLE_PAYLOAD_KEY = "workload_http_verification_sample"
# Core grant <=8192 decoded bytes; duplicated outer claims fit the remaining
# payload space. Header/payload/signature bounds apply to encoded segments.
_MAX_CREDENTIAL = 16384
_SEGMENTS = (1024, 15104, 128)
_OUTER = frozenset(("iss", "aud", "iat", "nbf", "exp", "jti", HTTP_SAMPLE_PAYLOAD_KEY))


class HttpVerificationSampleCredentialError(ValueError):
    """Fixed admission refusal; no credential, key material or diagnostics."""


@dataclass(frozen=True, slots=True, repr=False)
class HttpVerificationSampleReceiver:
    binding: HttpVerificationSampleReceiverBinding = field(repr=False)
    clock: object = field(default=time.time, repr=False)

    def __post_init__(self):
        valid = False
        try:
            if type(self.binding) is not HttpVerificationSampleReceiverBinding or not callable(self.clock):
                raise ValueError
            for entry in self.binding.checks:
                _safe_path(entry.check.path)
            for key in self.binding.configuration.verifier.public_keys:
                parsed = serialization.load_pem_public_key(key.public_key_pem.encode("ascii"))
                if not isinstance(parsed, Ed25519PublicKey):
                    raise ValueError
            valid = True
        except Exception:
            valid = False
        if not valid:
            raise ValueError("HTTP sample receiver setup is invalid")

    def __repr__(self):
        return "HttpVerificationSampleReceiver()"

    def require_host(self, target, declaration):
        receiver = self.binding.receiver_configuration
        if receiver.target != target or receiver.declaration != declaration:
            raise ValueError("HTTP sample receiver host is invalid")
        # Revalidate the binding before publication; audience equality is weaker.
        self.binding.checks

    def _admit(self, credential):
        header_bytes, payload_bytes, _ = _decode_read_compact(credential, _MAX_CREDENTIAL, _SEGMENTS)
        header = _decode_structural_json(header_bytes)
        payload = _decode_structural_json(payload_bytes)
        if (type(header) is not dict or set(header) != {"alg", "typ", "kid"}
                or header["alg"] != "EdDSA" or header["typ"] != HTTP_SAMPLE_TOKEN_TYPE
                or type(header["kid"]) is not str or type(payload) is not dict or frozenset(payload) != _OUTER):
            raise ValueError
        binding = self.binding
        key = binding.key(header["kid"])
        issuer = binding.configuration.verifier.issuer
        claims = jwt.decode(credential, key.public_key_pem, algorithms=["EdDSA"],
            issuer=issuer, audience=binding.audience, options={
                "require": ["iss", "aud", "iat", "nbf", "exp", "jti"],
                "verify_exp": False, "verify_nbf": False, "verify_iat": False, "strict_aud": True})
        if type(claims) is not dict or frozenset(claims) != _OUTER:
            raise ValueError
        grant = HttpVerificationSampleGrantCodec().decode(claims[HTTP_SAMPLE_PAYLOAD_KEY])
        if (key.key_id != grant.key_id or any(claims[outer] != getattr(grant, inner)
                or type(claims[outer]) is not type(getattr(grant, inner))
                for outer, inner in (("iss", "issuer"), ("aud", "audience"), ("iat", "issued_at"),
                                     ("nbf", "not_before"), ("exp", "expires_at"), ("jti", "jti")))):
            raise ValueError
        started = time.monotonic()
        now = self.clock()
        if (type(now) not in (int, float) or not math.isfinite(now) or not 0 <= now <= 2**53 - 1
                or not verify_http_verification_sample_grant(grant, grant.request,
                    expected_purpose=DelegationKeyPurpose.WORKLOAD_HTTP_VERIFICATION_SAMPLE,
                    expected_issuer=issuer, expected_key_id=key.key_id,
                    expected_audience=binding.audience, now=math.floor(now))):
            raise ValueError
        entry = binding.check_for_request(grant.request)
        _safe_path(entry.check.path)
        deadline = started + min(entry.check.policy.timeout_seconds, grant.expires_at - now)
        return grant.request, entry, deadline

    def read(self, credential: bytes) -> bytes:
        admitted = None
        try:
            admitted = self._admit(credential)
        except Exception:
            admitted = None
        if admitted is None:
            raise HttpVerificationSampleCredentialError("HTTP sample credential was rejected")
        request, entry, deadline = admitted
        outcome, evidence = _probe(entry, deadline)
        result = HttpVerificationSampleResult(request, outcome, evidence)
        return result.canonical_bytes(installed_check=entry.check)


__all__ = ["HTTP_SAMPLE_TOKEN_TYPE", "HTTP_SAMPLE_PAYLOAD_KEY", "HttpVerificationSampleCredentialError",
           "HttpVerificationSampleReceiver"]
