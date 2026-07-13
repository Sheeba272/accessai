"""
Pydantic models — request and response schemas
"""
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, List, Any
from enum import Enum


class WcagLevel(str, Enum):
    A   = "A"
    AA  = "AA"
    AAA = "AAA"


class ScanRequest(BaseModel):
    url:        str
    model:      str  = "llama3"
    depth:      int  = 1
    wcag_level: WcagLevel = WcagLevel.AA

    @field_validator("depth")
    def clamp_depth(cls, v):
        return max(1, min(v, 5))

    @field_validator("model")
    def validate_model(cls, v):
        allowed = {"llama3", "deepseek-r1", "qwen2.5", "mistral"}
        return v if v in allowed else "llama3"


class ScanStatusResponse(BaseModel):
    scan_id: str
    status:  str
    step:    str
    message: str = ""
    progress: int = 0
    error:   Optional[str] = None


class ViolationNode(BaseModel):
    html:    Optional[str] = None
    target:  Optional[List[str]] = None
    message: Optional[str] = None


class Violation(BaseModel):
    id:              str
    description:     str
    help:            Optional[str] = None
    helpUrl:         Optional[str] = None
    severity:        str  = "medium"
    wcag_reference:  Optional[str] = None
    tags:            List[str] = []
    nodes:           List[Any] = []


class AiAnalysis(BaseModel):
    issue_title:           str
    severity:              str
    wcag_reference:        str = ""
    business_impact:       str = ""
    affected_users:        str = ""
    technical_explanation: str = ""
    recommended_fix:       str = ""
    sample_code_fix:       str = ""
    priority:              str = "P3"
    description:           str = ""


class ScanMetrics(BaseModel):
    critical: int = 0
    high:     int = 0
    medium:   int = 0
    low:      int = 0
    passed:   int = 0
    total:    int = 0


class ExecutiveSummary(BaseModel):
    overview:           str = ""
    key_findings:       str = ""
    recommendations:    List[str] = []
    compliance_status:  str = ""
    score_reasoning:    str = ""


class ScanResultsResponse(BaseModel):
    scan_id:           str
    url:               str
    score:             float
    status:            str
    metrics:           dict
    violations:        List[Any] = []
    ai_analyses:       List[Any] = []
    executive_summary: dict = {}
    created_at:        Optional[str] = None
    completed_at:      Optional[str] = None


class ScanStartResponse(BaseModel):
    scan_id: str
    message: str


class HistoryScan(BaseModel):
    id:         str
    url:        str
    score:      float
    status:     str
    created_at: str


class HistoryResponse(BaseModel):
    scans: List[HistoryScan] = []
