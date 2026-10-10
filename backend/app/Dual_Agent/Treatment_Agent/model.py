
from typing import TypedDict, Dict, Any, List


class TreatmentAgentState(TypedDict):
    doctor_explanation:       str
    extracted_lab_values:     Dict[str, str]
    primary_diagnosis:        str
    patient_symptoms:         str

    patient_constraints:      List[str]
    clinical_context:         str
    optimized_treatment_plan: Dict[str, Any]

    severity_level:           str
    follow_up_question:       str
