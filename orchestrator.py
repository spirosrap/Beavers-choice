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
    search_quote_history_tool,
    check_stock_func,
    get_item_price_func,
    create_transaction_tool_func,
    get_all_inventory_tool_func,
    get_supplier_delivery_date_tool_func,
    get_cash_balance_tool_func,
    generate_financial_report_tool_func,
    search_quote_history_tool_func
)
from datetime import datetime
import inspect

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
    
    def __init__(self, client=None, agent_configs=None, system_config=None, *args, **kwargs):
        super().__init__(client=client, *args, **kwargs)
        try:
            self.agents: Dict[str, Agent] = {
                "inventory": InventoryAgent(client=client, config=agent_configs["inventory"], system_config=system_config, model="gpt-3.5-turbo"),
                "quoting": QuotingAgent(client=client, config=agent_configs["quoting"], system_config=system_config, model="gpt-3.5-turbo"),
                "sales": SalesAgent(client=client, config=agent_configs["sales"], system_config=system_config, model="gpt-3.5-turbo"),
                "finance": FinanceAgent(client=client, config=agent_configs["finance"], system_config=system_config, model="gpt-3.5-turbo"),
                "customer_service": CustomerServiceAgent(client=client, config=agent_configs["customer_service"], system_config=system_config, model="gpt-3.5-turbo")
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
                "status": "in_progress",
                "initial_cash_balance": None,
                "final_cash_balance": None,
                "cash_balance_changed": False
            }
            
            # Get initial cash balance
            initial_balance_result = await self.run({
                "tool": "get_cash_balance",
                "as_of_date": request.get("delivery_date", datetime.now().isoformat())
            })
            if isinstance(initial_balance_result, dict) and "balance" in initial_balance_result:
                workflow["initial_cash_balance"] = initial_balance_result["balance"]
            elif isinstance(initial_balance_result, dict) and "error" in initial_balance_result:
                workflow["status"] = "failed"
                workflow["error"] = initial_balance_result["error"]
                return workflow
            
            # Determine which agents need to be involved
            involved_agents = self._determine_agent_sequence(request)
            logger.debug(f"Determined agent sequence: {involved_agents}")
            
            # Execute the workflow
            for agent_name in involved_agents:
                agent = self.agents[agent_name]
                logger.debug(f"Executing step with agent: {agent_name}")
                
                # For quote requests, pass quote details between agents
                if request.get("type") == "quote_request":
                    if agent_name == "finance" and workflow["steps"]:
                        # Get quote details from previous step
                        quote_step = next((step for step in workflow["steps"] if step["agent"] == "quoting"), None)
                        if quote_step and quote_step.get("result", {}).get("data"):
                            quote_data = quote_step["result"]["data"]
                            request["quote_details"] = quote_data.get("quote_details", [])
                            request["total_amount"] = quote_data.get("total_amount", 0)
                            request["can_fulfill"] = quote_data.get("can_fulfill", False)
                
                step_result = await self._execute_agent_step(agent, request)
                workflow["steps"].append({
                    "agent": agent_name,
                    "result": step_result
                })
                
                # Check for failures in critical steps
                if not step_result.get("success", True):
                    workflow["status"] = "failed"
                    workflow["error"] = step_result.get("error", "Unknown error")
                    break
                
                # For quote requests, check if we should proceed with fulfillment
                if request.get("type") == "quote_request":
                    if agent_name == "quoting":
                        # Check if we should reject this quote
                        if not request.get("can_fulfill", False):
                            workflow["status"] = "rejected"
                            workflow["reason"] = "Insufficient stock or business constraints"
                            break
            
            # Only mark as completed if we haven't failed or been rejected
            if workflow["status"] == "in_progress":
                workflow["status"] = "completed"
            
            # Get final cash balance
            final_balance_result = await self.run({
                "tool": "get_cash_balance",
                "as_of_date": request.get("delivery_date", datetime.now().isoformat())
            })
            if isinstance(final_balance_result, dict) and "balance" in final_balance_result:
                workflow["final_cash_balance"] = final_balance_result["balance"]
                workflow["cash_balance_changed"] = (
                    workflow["initial_cash_balance"] != workflow["final_cash_balance"]
                )
            elif isinstance(final_balance_result, dict) and "error" in final_balance_result:
                # Don't fail the workflow for balance check errors
                logger.warning(f"Error getting final balance: {final_balance_result['error']}")
            
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
    
    def _should_reject_quote(self, request: Dict[str, Any]) -> bool:
        """Determine if a quote request should be rejected based on business rules."""
        try:
            # Get the items from the request
            items = request.get("items", [])
            if not items:
                return True
            
            # Check if any item has a very large quantity
            for item in items:
                if item.get("quantity", 0) > 10000:  # Reject very large orders
                    return True
            
            # Check if the event type is a high-risk event
            event_type = request.get("event_type", "").lower()
            if "wedding" in event_type and len(items) > 5:  # Reject complex wedding orders
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error in quote rejection logic: {str(e)}", exc_info=True)
            return True
    
    def _determine_agent_sequence(self, request: Dict[str, Any]) -> List[str]:
        """Determine the sequence of agents needed for a request."""
        try:
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
            # Check if the result contains an error
            if isinstance(result, dict) and "error" in result:
                return {"success": False, "error": result["error"]}
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Error executing agent step: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        print(f"Orchestrator run method called with request: {request}")
        """Override the run method to call the local Python function directly."""
        tool_name = request.get("tool")
        if not tool_name:
            return {"error": "No tool specified in request"}
        
        # Map tool names to local functions
        tool_map = {
            "check_stock": check_stock_func,
            "get_item_price": get_item_price_func,
            "create_transaction": create_transaction_tool_func,
            "get_all_inventory": get_all_inventory_tool_func,
            "get_supplier_delivery_date": get_supplier_delivery_date_tool_func,
            "get_cash_balance": get_cash_balance_tool_func,
            "generate_financial_report": generate_financial_report_tool_func,
            "search_quote_history": search_quote_history_tool_func
        }
        
        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}
        
        # Filter request to only include arguments the tool function expects
        func = tool_map[tool_name]
        sig = inspect.signature(func)
        filtered_args = {k: v for k, v in request.items() if k in sig.parameters}
        try:
            result = await func(**filtered_args)
            if isinstance(result, dict) and "error" in result:
                return {"error": result["error"]}
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
            return {"error": f"Error executing tool {tool_name}: {str(e)}"}
    
    system_prompt = (
        "You are the Orchestrator Agent for Munder Difflin Paper Company. "
        "Coordinate with the Inventory, Quoting, Sales, Finance, and Customer Service Agents "
        "to fulfill customer requests. Manage workflows and ensure proper communication between agents. "
        "Always use the provided tools and delegate to worker agents as needed. "
        "Do not make up information—invoke the tools to answer all questions with real data."
    ) 