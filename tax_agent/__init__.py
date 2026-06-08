"""TaxAgent Global — 多国自动报税智能体"""

from tax_agent.registry import JurisdictionRegistry
from tax_agent.orchestrator import Orchestrator

__version__ = "0.1.0"
__all__ = ["JurisdictionRegistry", "Orchestrator"]