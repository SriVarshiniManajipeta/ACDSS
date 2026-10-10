"""
architecture.py
===============
Builds and compiles the Treatment Agent LangGraph.

Graph flow:
    constraint_check → clinical_context → treatment_generation → evaluate_treatment → END
"""

from langgraph.graph import StateGraph, END

from .model import TreatmentAgentState
from .node_tools import (
    _constraint_check_node,
    _clinical_context_node,
    _treatment_generation_node,
    _treatment_evaluation_node,
)

_workflow = StateGraph(TreatmentAgentState)

_workflow.add_node("constraint_check",     _constraint_check_node)
_workflow.add_node("clinical_context",     _clinical_context_node)
_workflow.add_node("treatment_generation", _treatment_generation_node)
_workflow.add_node("evaluate_treatment",   _treatment_evaluation_node)

_workflow.set_entry_point("constraint_check")
_workflow.add_edge("constraint_check",     "clinical_context")
_workflow.add_edge("clinical_context",     "treatment_generation")
_workflow.add_edge("treatment_generation", "evaluate_treatment")
_workflow.add_edge("evaluate_treatment",   END)

treatment_agent = _workflow.compile()
