from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ObjectivePhase(str, Enum):
    RECON = "recon"
    DETECTION = "detection"
    VERIFICATION = "verification"
    EXPLOIT_VERIFY = "exploit-verify"
    REPORT = "report"


class ObjectiveStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class FindingConfidence(str, Enum):
    VERIFIED = "verified"
    PROBABLE = "probable"
    UNVERIFIED = "unverified"


class RemediationPriority(str, Enum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short-term"
    LONG_TERM = "long-term"


class Evidence(BaseModel):
    type: str = Field(description="http-request, http-response, screenshot, terminal-log, scan-output")
    path: str = ""
    description: str = ""
    sha256: str = ""
    collected_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    id: str
    title: str
    severity: FindingSeverity
    affected_target: str
    affected_component: str = ""
    description: str
    cvss_score: float | None = None
    cvss_vector: str = ""
    cvss_version: str = "4.0"
    cwe: list[str] = Field(default_factory=list)
    mitre: list[str] = Field(default_factory=list)
    steps_to_reproduce: list[str] = Field(default_factory=list)
    impact: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    remediation: str = ""
    remediation_priority: RemediationPriority | None = None
    objective_id: str = ""
    phase: ObjectivePhase | None = None
    agent: str = ""
    confidence: FindingConfidence = FindingConfidence.VERIFIED
    verified_methods: list[str] = Field(default_factory=list)
    discovered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ScanObjective(BaseModel):
    id: str
    phase: ObjectivePhase
    title: str
    description: str = ""
    endpoint_group: str = ""
    status: ObjectiveStatus = ObjectiveStatus.PENDING
    owasp_category: str = ""
    priority: int = 5
    blocked_by: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    owner: str = ""
    notes: str = ""
    parent_id: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class AttackPathStep(BaseModel):
    order: int
    phase: ObjectivePhase
    technique: str
    source: str
    target: str
    tool: str = ""
    finding_id: str = ""


class AttackPath(BaseModel):
    id: str
    name: str
    description: str = ""
    steps: list[AttackPathStep] = Field(default_factory=list)
    combined_severity: FindingSeverity = FindingSeverity.CRITICAL
    finding_ids: list[str] = Field(default_factory=list)
