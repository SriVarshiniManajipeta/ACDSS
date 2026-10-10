

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PatientInfo(BaseModel):
    name:   Optional[str] = None
    age:    Optional[int] = None
    gender: Optional[str] = None
    phone:  Optional[str] = None


class UiEvent(BaseModel):
    """A card for the frontend to render. `kind` maps to a React component."""

    kind: str              
    data: Any


class ChatResponse(BaseModel):
    """Note what's absent: no diagnosis, treatment, or chat history round-trip.
    The session holds those, so the client only carries a session_id."""

    session_id: str
    reply:      str
    events:     List[UiEvent] = []
    tools_used: List[str] = []   


class DoctorOut(BaseModel):
    id:               int
    name:             str
    specialization:   str
    hospital:         str
    location:         str
    experience_years: int
    rating:           float
    available_slots:  List[str]


class AppointmentCreate(BaseModel):
    patient_name: str
    age:          Optional[int] = None
    gender:       Optional[str] = None
    phone:        Optional[str] = None
    doctor_id:    int
    slot:         str
    session_id:   Optional[str] = None


class AppointmentOut(BaseModel):
    id:           int
    doctor_name:  str
    patient_name: str
    slot:         str
    status:       str


class LabMarker(BaseModel):
    test_name:        str
    patient_value:    str
    reference_range:  str
    status:           str                
    potential_causes: List[str] = []


class TreatmentStep(BaseModel):
    medication_or_action: str
    dosage_or_detail:     str
    rationale:            str


class MetaEvaluation(BaseModel):
    """Output of the Final Meta-Evaluator — the pipeline-level quality gate."""

    overall_quality_score:    int       = 80
    consistency_verdict:      str       = "minor_gaps"
    safety_verdict:           str       = "review_recommended"
    safety_flags:             List[str] = []
    clinical_summary:         str       = ""
    pipeline_recommendations: str       = ""

