from pydantic_ai.agent import Agent
from typing import List, Dict, Any
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

class BaseAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_queue: List[Dict[str, Any]] = []
    
    def send_message(self, to_agent: str, message: Dict[str, Any]):
        """Send a message to another agent."""
        self.message_queue.append({
            "from": self.__class__.__name__,
            "to": to_agent,
            "content": message
        })
    
    def receive_message(self) -> Dict[str, Any]:
        """Receive a message from the queue."""
        return self.message_queue.pop(0) if self.message_queue else None
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a request using the agent's LLM and tools."""
        try:
            # Use the LLM to process the request and invoke tools as needed
            return await self.run(request)
        except Exception as e:
            return {"error": str(e)}

class InventoryAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        check_stock_tool,
        create_transaction_tool,
        get_all_inventory_tool,
        get_supplier_delivery_date_tool
    ]
    system_prompt = (
        "You are the Inventory Agent for Munder Difflin Paper Company. "
        "Always use the provided tools to check stock, assess reorder needs, get inventory status, and estimate supplier delivery dates. "
        "Do not make up information—invoke the tools to answer all inventory-related questions."
    )

class QuotingAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        get_item_price_tool,
        check_stock_tool,
        search_quote_history_tool,
        get_cash_balance_tool
    ]
    system_prompt = (
        "You are the Quoting Agent for Munder Difflin Paper Company. "
        "Always use the provided tools to generate quotes, check item prices, search quote history, and check cash balance. "
        "Do not make up information—invoke the tools to answer all quoting-related questions."
    )

class SalesAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        check_stock_tool,
        create_transaction_tool,
        get_item_price_tool,
        generate_financial_report_tool
    ]
    system_prompt = (
        "You are the Sales Agent for Munder Difflin Paper Company. "
        "Always use the provided tools to process sales, create transactions, check stock, and generate financial reports. "
        "Do not make up information—invoke the tools to answer all sales-related questions."
    )

class FinanceAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        get_cash_balance_tool,
        generate_financial_report_tool,
        create_transaction_tool
    ]
    system_prompt = (
        "You are the Finance Agent for Munder Difflin Paper Company. "
        "Handle all financial operations including cash balance checks, financial reporting, "
        "and transaction processing. Coordinate with other agents for financial approvals. "
        "Do not make up information—invoke the tools to answer all finance-related questions."
    )

class CustomerServiceAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        check_stock_tool,
        get_item_price_tool,
        search_quote_history_tool
    ]
    system_prompt = (
        "You are the Customer Service Agent for Munder Difflin Paper Company. "
        "Handle customer inquiries, provide product information, and coordinate with other agents "
        "to resolve customer issues. Always maintain a professional and helpful demeanor. "
        "Do not make up information—invoke the tools to answer all customer-related questions."
    ) 