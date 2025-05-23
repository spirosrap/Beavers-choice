from pydantic_ai.agent import Agent
from typing import Dict, List, Any
import logging
from agents import (
    InventoryAgent,
    QuotingAgent,
    SalesAgent,
    FinanceAgent,
    CustomerServiceAgent
)
from tools import (
    check_stock_tool,
    get_item_price_tool,
    create_transaction_tool,
    get_all_inventory_tool,
    get_supplier_delivery_date_tool,
    get_cash_balance_tool,
    generate_financial_report_tool,
    search_quote_history_tool
)

logger = logging.getLogger(__name__)

class OrchestratorAgent(Agent):
    model = "gpt-3.5-turbo"
    temperature = 0.7
    max_tokens = 1000
    tools = [
        check_stock_tool,
        get_item_price_tool,
        create_transaction_tool,
        get_all_inventory_tool,
        get_supplier_delivery_date_tool,
        get_cash_balance_tool,
        generate_financial_report_tool,
        search_quote_history_tool
    ]
    
    def __init__(self, client=None, *args, **kwargs):
        super().__init__(client=client, *args, **kwargs)
        try:
            self.agents: Dict[str, Agent] = {
                "inventory": InventoryAgent(client=client, model="gpt-3.5-turbo"),
                "quoting": QuotingAgent(client=client, model="gpt-3.5-turbo"),
                "sales": SalesAgent(client=client, model="gpt-3.5-turbo"),
                "finance": FinanceAgent(client=client, model="gpt-3.5-turbo"),
                "customer_service": CustomerServiceAgent(client=client, model="gpt-3.5-turbo")
            }
            self.workflow_history: List[Dict[str, Any]] = []
            logger.debug("Successfully initialized OrchestratorAgent with all child agents")
        except Exception as e:
            logger.error(f"Error initializing OrchestratorAgent: {str(e)}", exc_info=True)
            raise
    
    async def coordinate_workflow(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate a workflow across multiple agents."""
        try:
            workflow = {
                "request": request,
                "steps": [],
                "status": "in_progress"
            }
            
            # Determine which agents need to be involved
            involved_agents = self._determine_agent_sequence(request)
            logger.debug(f"Determined agent sequence: {involved_agents}")
            
            # Execute the workflow
            for agent_name in involved_agents:
                agent = self.agents[agent_name]
                logger.debug(f"Executing step with agent: {agent_name}")
                step_result = await self._execute_agent_step(agent, request)
                workflow["steps"].append({
                    "agent": agent_name,
                    "result": step_result
                })
            
            workflow["status"] = "completed"
            self.workflow_history.append(workflow)
            return workflow
        except Exception as e:
            logger.error(f"Error in workflow coordination: {str(e)}", exc_info=True)
            return {
                "request": request,
                "steps": [],
                "status": "failed",
                "error": str(e)
            }
    
    def _determine_agent_sequence(self, request: Dict[str, Any]) -> List[str]:
        """Determine the sequence of agents needed for a request."""
        try:
            # This is a simplified example - in practice, this would be more sophisticated
            request_type = request.get("type", "").lower()
            if "quote" in request_type:
                return ["quoting", "inventory", "finance"]
            elif "sale" in request_type:
                return ["sales", "inventory", "finance"]
            elif "inquiry" in request_type:
                return ["customer_service", "inventory", "quoting"]
            return ["customer_service"]
        except Exception as e:
            logger.error(f"Error determining agent sequence: {str(e)}", exc_info=True)
            raise
    
    async def _execute_agent_step(self, agent: Agent, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step in the workflow with the given agent."""
        try:
            logger.debug(f"Processing request with agent: {agent.__class__.__name__}")
            result = await agent.process(request)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Error executing agent step: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    system_prompt = (
        "You are the Orchestrator Agent for Munder Difflin Paper Company. "
        "Coordinate with the Inventory, Quoting, Sales, Finance, and Customer Service Agents "
        "to fulfill customer requests. Manage workflows and ensure proper communication between agents. "
        "Always use the provided tools and delegate to worker agents as needed. "
        "Do not make up information—invoke the tools to answer all questions with real data."
    ) 