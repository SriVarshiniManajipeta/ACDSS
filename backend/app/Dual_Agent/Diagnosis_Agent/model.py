
from typing import TypedDict, Dict, Any

class DiagnosisAgentState(TypedDict):

    doctor_explanation:str
    raw_lab_text:str
    extracted_lab_values:Dict[str, str]
    retrieved_lab_guidelines:str 
    evaluation_results:Dict[str, Any]
    evaluation_summary:Dict[str, Any]
    retry_count:int