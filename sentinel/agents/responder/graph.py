"""
SENTINEL Agent 3 — Response Graph

LangGraph definition for the multi-agent response workflow.
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import structlog

from sentinel.agents.responder.policy import ResponsePolicy

logger = structlog.get_logger(__name__)

class AgentState(TypedDict):
    """State maintained during a threat investigation."""
    event_id: str
    device_id: str
    severity: int
    tactic: str
    summary: str
    indicators: List[str]
    # Decision results
    rule_name: str
    actions: List[str]
    require_confirmation: bool
    status: str # "pending", "authorized", "blocked", "executed"

class ResponseGraph:
    """
    State machine for orchestrating the SENTINEL response.
    """
    def __init__(self):
        self.policy = ResponsePolicy()
        self.workflow = StateGraph(AgentState)
        
        # Define nodes
        self.workflow.add_node("evaluate_policy", self.evaluate_policy)
        self.workflow.add_node("security_gate", self.security_gate)
        
        # Define edges
        self.workflow.set_entry_point("evaluate_policy")
        self.workflow.add_edge("evaluate_policy", "security_gate")
        
        # Conditional edge for execution
        self.workflow.add_conditional_edges(
            "security_gate",
            self.should_execute,
            {
                "execute": END, # Worker will handle Redis publish for now
                "wait_for_user": END
            }
        )
        
        self.app = self.workflow.compile()

    def evaluate_policy(self, state: AgentState) -> Dict[str, Any]:
        """Node: Map severity to policy actions."""
        decision = self.policy.get_action_for_severity(state["severity"])
        logger.info("policy_evaluated", 
                    event_id=state["event_id"], 
                    rule=decision["rule_name"],
                    actions=decision["actions"])
        
        return {
            "rule_name": decision["rule_name"],
            "actions": decision["actions"],
            "require_confirmation": decision["require_confirmation"],
            "status": "pending"
        }

    def security_gate(self, state: AgentState) -> Dict[str, Any]:
        """Node: Verify if human-in-the-loop is required."""
        if state["require_confirmation"]:
            logger.warning("security_gate_active", 
                           msg="High severity action requires user confirmation",
                           event_id=state["event_id"])
            return {"status": "wait_for_user"}
        
        return {"status": "authorized"}

    def should_execute(self, state: AgentState) -> str:
        """Condition: Decide if we can proceed to execution."""
        if state["status"] == "authorized":
            return "execute"
        return "wait_for_user"

    async def run(self, threat_event: Dict[str, Any]) -> AgentState:
        """Run the graph for a specific threat."""
        initial_state: AgentState = {
            "event_id": threat_event["event_id"],
            "device_id": threat_event["device_id"],
            "severity": threat_event["severity"],
            "tactic": threat_event.get("tactic", "Unknown"),
            "summary": threat_event.get("summary", ""),
            "indicators": threat_event.get("indicators", []),
            "rule_name": "",
            "actions": [],
            "require_confirmation": False,
            "status": "pending"
        }
        
        return await self.app.ainvoke(initial_state)
