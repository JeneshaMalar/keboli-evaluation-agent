"""Evaluation graph definition."""
from .workflow.builder import build_evaluation_workflow

evaluation_app = build_evaluation_workflow()

