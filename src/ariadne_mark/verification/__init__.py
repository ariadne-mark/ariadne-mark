"""Per-method verifier result contract (partial REQ-008), not a detector.

Adapters must supply actual observations. This class checks consistency only;
constructing a result does not perform cryptographic or media verification.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ariadne_mark.provenance import ProvenanceRecord, _text


class CheckStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    NOT_FOUND = "not_found"
    INVALID = "invalid"
    RECOVERED_CLAIM = "recovered_claim"
    VERIFIED_CLAIM = "verified_claim"


class SignatureStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    ABSENT = "absent"
    INVALID = "invalid"
    VALID = "valid"


class IssuerTrust(str, Enum):
    NOT_CHECKED = "not_checked"
    UNTRUSTED = "untrusted"
    TRUSTED = "trusted"


@dataclass(frozen=True)
class VerificationResult:
    method: str
    status: CheckStatus
    signature: SignatureStatus = SignatureStatus.NOT_CHECKED
    issuer_trust: IssuerTrust = IssuerTrust.NOT_CHECKED
    record: Optional[ProvenanceRecord] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        _text(self.method, "method")
        for field, enum in (("status", CheckStatus), ("signature", SignatureStatus), ("issuer_trust", IssuerTrust)):
            if not isinstance(getattr(self, field), enum):
                raise ValueError(f"{field} must be a {enum.__name__}")
        if self.reason is not None:
            _text(self.reason, "reason")
        if self.record is not None and not isinstance(self.record, ProvenanceRecord):
            raise ValueError("record must be a ProvenanceRecord")
        if self.status in {CheckStatus.NOT_CHECKED, CheckStatus.INVALID} and not self.reason:
            raise ValueError("not_checked and invalid require a reason")
        if self.status in {CheckStatus.NOT_CHECKED, CheckStatus.NOT_FOUND}:
            if self.record is not None or self.signature is not SignatureStatus.NOT_CHECKED:
                raise ValueError("unchecked/absent claims cannot contain a record or signature result")
            if self.issuer_trust is not IssuerTrust.NOT_CHECKED:
                raise ValueError("unchecked/absent claims cannot have an issuer trust result")
        if self.status is CheckStatus.RECOVERED_CLAIM:
            if self.record is None or self.signature not in {SignatureStatus.ABSENT, SignatureStatus.NOT_CHECKED}:
                raise ValueError("recovered_claim requires a record with an absent/unchecked signature")
        if self.status is CheckStatus.VERIFIED_CLAIM:
            if self.record is None or self.signature is not SignatureStatus.VALID:
                raise ValueError("verified_claim requires a record and a valid signature")
        if self.signature is SignatureStatus.INVALID and self.status is not CheckStatus.INVALID:
            raise ValueError("invalid signatures require invalid status")
        if self.issuer_trust is not IssuerTrust.NOT_CHECKED:
            if self.status is not CheckStatus.VERIFIED_CLAIM or self.signature is not SignatureStatus.VALID:
                raise ValueError("issuer trust is evaluated only for verified signed claims")
        if self.status is CheckStatus.INVALID and self.signature is SignatureStatus.VALID:
            raise ValueError("invalid result cannot report a valid content-bound signature")

    def to_dict(self) -> dict:
        return {
            "schema_version": 1, "method": self.method, "status": self.status.value,
            "signature": self.signature.value, "issuer_trust": self.issuer_trust.value,
            "record": self.record.to_dict() if self.record else None, "reason": self.reason,
        }
