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
    search_quote_history_tool,
    check_stock,
    get_item_price
)
from datetime import datetime
import asyncio
import logging
from message_queue import Message, MessageQueue, AgentError, ErrorType
from config import AgentConfig, SystemConfig

logger = logging.getLogger(__name__)

class BaseAgent(Agent):
    def __init__(self, config: AgentConfig, system_config: SystemConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.system_config = system_config
        self.message_queue = MessageQueue()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def send_message(self, to_agent: str, content: Dict[str, Any], priority: int = 0) -> str:
        """Send a message to another agent."""
        message = Message(
            to_agent=to_agent,
            from_agent=self.__class__.__name__,
            content=content,
            priority=priority
        )
        return self.message_queue.send(message)
    
    def receive_message(self) -> Message:
        """Receive a message from the queue."""
        return self.message_queue.receive()
    
    async def process_with_retry(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a request with retry logic."""
        for attempt in range(self.config.retry_attempts):
            try:
                return await self.process(request)
            except AgentError as e:
                if not e.retryable or attempt == self.config.retry_attempts - 1:
                    self.logger.error(f"Error processing request: {str(e)}")
                    raise
                self.logger.warning(f"Retrying request (attempt {attempt + 1}/{self.config.retry_attempts})")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}")
                raise AgentError(ErrorType.SYSTEM, str(e), retryable=False)
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a request using the agent's LLM and tools."""
        try:
            # Validate request
            if not self._validate_request(request):
                raise AgentError(
                    ErrorType.VALIDATION,
                    "Invalid request format",
                    retryable=False
                )
            
            # Check business rules
            if not self.system_config.business_rules.evaluate(request):
                raise AgentError(
                    ErrorType.BUSINESS,
                    "Request violates business rules",
                    retryable=False
                )
            
            # Process the request
            result = await self.run(request)
            
            # Validate result
            if not self._validate_result(result):
                raise AgentError(
                    ErrorType.VALIDATION,
                    "Invalid result format",
                    retryable=True
                )
            
            return result
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(
                ErrorType.SYSTEM,
                str(e),
                retryable=True
            )
    
    def _validate_request(self, request: Dict[str, Any]) -> bool:
        """Validate the request format."""
        required_fields = ["type"]
        return all(field in request for field in required_fields)
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate the result format."""
        required_fields = ["status"]
        return all(field in result for field in required_fields)

    async def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Override the run method to call the local Python function directly."""
        tool_name = request.get("tool")
        if not tool_name:
            return {"error": "No tool specified in request"}
        
        # Map tool names to local functions
        tool_map = {
            "check_stock": check_stock,
            "get_item_price": get_item_price,
            "create_transaction": create_transaction_tool,
            "get_all_inventory": get_all_inventory_tool,
            "get_supplier_delivery_date": get_supplier_delivery_date_tool,
            "get_cash_balance": get_cash_balance_tool,
            "generate_financial_report": generate_financial_report_tool,
            "search_quote_history": search_quote_history_tool
        }
        
        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}
        
        # Call the local function
        try:
            result = await tool_map[tool_name](**request)
            return result
        except Exception as e:
            return {"error": f"Error executing tool {tool_name}: {str(e)}"}

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
        "For each request:\n"
        "1. Check stock levels for requested items\n"
        "2. If stock is low, check supplier delivery dates\n"
        "3. Return inventory status and reorder recommendations\n"
        "Do not make up information—invoke the tools to answer all inventory-related questions."
    )
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process an inventory request using the agent's tools."""
        try:
            request_type = request.get("type")
            if request_type not in ["quote_request", "sale_request", "inquiry"]:
                return {"error": "Invalid request type for InventoryAgent"}
            
            items = request.get("items", [])
            if not items:
                return {"error": "No items specified in request"}
            
            inventory_status = []
            
            for item in items:
                # Check stock
                stock_result = await self.run({
                    "tool": "check_stock",
                    "item_name": item["name"],
                    "as_of_date": request.get("delivery_date", datetime.now().isoformat())
                })
                
                if not isinstance(stock_result, dict) or "error" in stock_result:
                    return {"error": f"Could not check stock for {item['name']}"}
                
                stock_level = stock_result.get("stock", 0)
                quantity_needed = item.get("quantity", 0)
                
                # If stock is low, check supplier delivery date
                if stock_level < quantity_needed:
                    delivery_result = await self.run({
                        "tool": "get_supplier_delivery_date",
                        "input_date_str": datetime.now().isoformat(),
                        "quantity": quantity_needed
                    })
                    
                    if not isinstance(delivery_result, dict) or "error" in delivery_result:
                        return {"error": f"Could not get delivery date for {item['name']}"}
                    
                    delivery_date = delivery_result.get("delivery_date")
                else:
                    delivery_date = None
                
                inventory_status.append({
                    "item_name": item["name"],
                    "current_stock": stock_level,
                    "quantity_needed": quantity_needed,
                    "supplier_delivery_date": delivery_date,
                    "needs_reorder": stock_level < quantity_needed
                })
            
            return {
                "inventory_status": inventory_status,
                "status": "completed"
            }
            
        except Exception as e:
            return {"error": str(e)}

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
        "For each quote request:\n"
        "1. Check stock levels for requested items\n"
        "2. Get current prices for items\n"
        "3. Calculate total amount\n"
        "4. Return the quote details including prices and availability\n"
        "Do not make up information—invoke the tools to answer all quote-related questions."
    )
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a quote request using the agent's tools."""
        try:
            if request.get("type") != "quote_request":
                return {"error": "Invalid request type for QuotingAgent"}
                
            items = request.get("items", [])
            if not items:
                return {"error": "No items specified in quote request"}
            
            quote_details = []
            total_amount = 0
            can_fulfill = True
            
            for item in items:
                # Check stock
                stock_result = await self.run({
                    "tool": "check_stock",
                    "item_name": item["name"],
                    "as_of_date": request.get("delivery_date", datetime.now().isoformat())
                })
                
                if not isinstance(stock_result, dict) or "error" in stock_result:
                    return {"error": f"Could not check stock for {item['name']}"}
                
                stock_level = stock_result.get("stock", 0)
                
                # Get price
                price_result = await self.run({
                    "tool": "get_item_price",
                    "item_name": item["name"]
                })
                
                if not isinstance(price_result, dict) or "error" in price_result:
                    return {"error": f"Could not get price for {item['name']}"}
                
                unit_price = price_result.get("unit_price", 0)
                quantity = item.get("quantity", 0)
                item_total = unit_price * quantity
                total_amount += item_total
                
                # Check if we can fulfill this item
                if stock_level < quantity:
                    can_fulfill = False
                
                quote_details.append({
                    "item_name": item["name"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "item_total": item_total,
                    "stock_available": stock_level,
                    "can_fulfill": stock_level >= quantity
                })
            
            return {
                "quote_details": quote_details,
                "total_amount": total_amount,
                "can_fulfill": can_fulfill,
                "status": "completed"
            }
            
        except Exception as e:
            return {"error": str(e)}

class SalesAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        check_stock_tool,
        get_item_price_tool,
        create_transaction_tool,
        get_cash_balance_tool,
        generate_financial_report_tool
    ]
    system_prompt = (
        "You are the Sales Agent for Munder Difflin Paper Company. "
        "Always use the provided tools to process sales requests. "
        "For each sale request:\n"
        "1. Check stock levels for requested items\n"
        "2. Get current prices for items\n"
        "3. Create transaction records\n"
        "4. Generate financial report\n"
        "5. Return sale details including total amount and transactions\n"
        "Do not make up information—invoke the tools to answer all sales-related questions."
    )
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a sale request using the agent's tools."""
        try:
            if request.get("type") != "sale_request":
                return {"error": "Invalid request type for SalesAgent"}
            
            items = request.get("items", [])
            if not items:
                return {"error": "No items specified in sale request"}
            
            sale_details = []
            total_amount = 0
            transactions = []
            
            # First check if we can fulfill all items
            for item in items:
                stock_result = await self.run({
                    "tool": "check_stock",
                    "item_name": item["name"],
                    "as_of_date": request.get("delivery_date", datetime.now().isoformat())
                })
                
                if not isinstance(stock_result, dict) or "error" in stock_result:
                    return {"error": f"Could not check stock for {item['name']}"}
                
                stock_level = stock_result.get("stock", 0)
                if stock_level < item.get("quantity", 0):
                    return {
                        "error": f"Insufficient stock for {item['name']}. Available: {stock_level}, Requested: {item.get('quantity', 0)}",
                        "status": "failed"
                    }
            
            # If we can fulfill all items, process the sale
            for item in items:
                # Get price
                price_result = await self.run({
                    "tool": "get_item_price",
                    "item_name": item["name"]
                })
                
                if not isinstance(price_result, dict) or "error" in price_result:
                    return {"error": f"Could not get price for {item['name']}"}
                
                unit_price = price_result.get("unit_price", 0)
                quantity = item.get("quantity", 0)
                item_total = unit_price * quantity
                total_amount += item_total
                
                # Create transaction
                transaction_result = await self.run({
                    "tool": "create_transaction",
                    "item_name": item["name"],
                    "transaction_type": "sales",
                    "quantity": quantity,
                    "price": item_total,
                    "date": request.get("delivery_date", datetime.now().isoformat())
                })
                
                if not isinstance(transaction_result, dict) or "error" in transaction_result:
                    return {"error": f"Could not create transaction for {item['name']}"}
                
                transactions.append(transaction_result)
                
                sale_details.append({
                    "item_name": item["name"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "item_total": item_total
                })
            
            # Generate financial report
            report_result = await self.run({
                "tool": "generate_financial_report",
                "as_of_date": request.get("delivery_date", datetime.now().isoformat())
            })
            
            if not isinstance(report_result, dict) or "error" in report_result:
                return {"error": "Could not generate financial report"}
            
            return {
                "sale_details": sale_details,
                "total_amount": total_amount,
                "transactions": transactions,
                "financial_report": report_result,
                "status": "completed"
            }
            
        except Exception as e:
            return {"error": str(e)}

class FinanceAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        get_cash_balance_tool,
        generate_financial_report_tool,
        create_transaction_tool
    ]
    system_prompt = (
        "You are the Finance Agent for Munder Difflin Paper Company. "
        "Always use the provided tools to check cash balance, create transactions, and generate financial reports. "
        "For quote requests:\n"
        "1. Check cash balance\n"
        "2. Verify quote details\n"
        "3. Generate financial report\n"
        "For sale requests:\n"
        "1. Check cash balance\n"
        "2. Create transaction records\n"
        "3. Generate financial report\n"
        "Do not make up information—invoke the tools to answer all finance-related questions."
    )
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a financial request using the agent's tools."""
        try:
            request_type = request.get("type")
            if request_type not in ["quote_request", "sale_request"]:
                return {"error": "Invalid request type for FinanceAgent"}
            
            # Check cash balance
            balance_result = await self.run({
                "tool": "get_cash_balance",
                "as_of_date": request.get("delivery_date", datetime.now().isoformat())
            })
            
            if not isinstance(balance_result, dict) or "error" in balance_result:
                return {"error": "Could not check cash balance"}
            
            cash_balance = balance_result.get("balance", 0)
            
            if request_type == "quote_request":
                quote_details = request.get("quote_details", [])
                if not quote_details:
                    return {"error": "Invalid quote details"}
                
                total_amount = request.get("total_amount", 0)
                
                # Generate financial report
                report_result = await self.run({
                    "tool": "generate_financial_report",
                    "as_of_date": request.get("delivery_date", datetime.now().isoformat())
                })
                
                if not isinstance(report_result, dict) or "error" in report_result:
                    return {"error": "Could not generate financial report"}
                
                return {
                    "cash_balance": cash_balance,
                    "quote_total": total_amount,
                    "financial_report": report_result,
                    "status": "completed"
                }
            
            elif request_type == "sale_request":
                items = request.get("items", [])
                if not items:
                    return {"error": "No items specified in sale request"}
                
                total_amount = 0
                transactions = []
                
                for item in items:
                    # Get price for each item
                    price_result = await self.run({
                        "tool": "get_item_price",
                        "item_name": item["name"]
                    })
                    
                    if not isinstance(price_result, dict) or "error" in price_result:
                        return {"error": f"Could not get price for {item['name']}"}
                    
                    unit_price = price_result.get("unit_price", 0)
                    quantity = item.get("quantity", 0)
                    item_total = unit_price * quantity
                    total_amount += item_total
                    
                    # Create transaction record
                    transaction_result = await self.run({
                        "tool": "create_transaction",
                        "customer_id": request.get("customer_id"),
                        "item_name": item["name"],
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_amount": item_total,
                        "payment_method": request.get("payment_method", "credit_card"),
                        "transaction_date": request.get("delivery_date", datetime.now().isoformat())
                    })
                    
                    if not isinstance(transaction_result, dict) or "error" in transaction_result:
                        return {"error": f"Could not create transaction for {item['name']}"}
                    
                    transactions.append(transaction_result)
                
                # Generate financial report
                report_result = await self.run({
                    "tool": "generate_financial_report",
                    "as_of_date": request.get("delivery_date", datetime.now().isoformat())
                })
                
                if not isinstance(report_result, dict) or "error" in report_result:
                    return {"error": "Could not generate financial report"}
                
                return {
                    "cash_balance": cash_balance,
                    "sale_total": total_amount,
                    "transactions": transactions,
                    "financial_report": report_result,
                    "status": "completed"
                }
            
        except Exception as e:
            return {"error": str(e)}

class CustomerServiceAgent(BaseAgent):
    model = "gpt-3.5-turbo"
    tools = [
        check_stock_tool,
        get_item_price_tool
    ]
    system_prompt = (
        "You are the Customer Service Agent for Munder Difflin Paper Company. "
        "Always use the provided tools to handle customer inquiries about delivery times and prices. "
        "For delivery time inquiries:\n"
        "1. Identify the item from the inquiry\n"
        "2. Check stock levels\n"
        "3. Return delivery time based on stock availability\n"
        "For price inquiries:\n"
        "1. Identify the item from the inquiry\n"
        "2. Get current price\n"
        "3. Return price information\n"
        "Do not make up information—invoke the tools to answer all customer questions."
    )
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a customer inquiry using the agent's tools."""
        try:
            if request.get("type") != "inquiry":
                return {"error": "Invalid request type for CustomerServiceAgent"}
            
            customer_id = request.get("customer_id")
            if not customer_id:
                return {"error": "No customer ID provided"}
            
            question = request.get("question", "").lower()
            
            # Check if it's a delivery time inquiry
            if "delivery" in question or "when" in question or "time" in question:
                # Extract item name from the question
                item_name = None
                for word in question.split():
                    if word.lower() in ["paper", "pens", "pencils", "notebooks", "a4"]:
                        item_name = word.lower()
                        if item_name == "a4":
                            item_name = "a4 paper"
                        break
                
                if not item_name:
                    return {"error": "Could not identify item in inquiry"}
                
                # Check stock
                stock_result = await self.run({
                    "tool": "check_stock",
                    "item_name": item_name,
                    "as_of_date": datetime.now().isoformat()
                })
                
                if not isinstance(stock_result, dict) or "error" in stock_result:
                    return {"error": f"Could not check stock for {item_name}"}
                
                stock_level = stock_result.get("stock", 0)
                
                # Get price for additional context
                price_result = await self.run({
                    "tool": "get_item_price",
                    "item_name": item_name
                })
                
                if not isinstance(price_result, dict) or "error" in price_result:
                    return {"error": f"Could not get price for {item_name}"}
                
                unit_price = price_result.get("unit_price", 0)
                
                return {
                    "item_name": item_name,
                    "stock_available": stock_level,
                    "unit_price": unit_price,
                    "delivery_time": "immediate" if stock_level > 0 else "out of stock",
                    "status": "completed"
                }
            
            # Check if it's a price inquiry
            elif "price" in question or "cost" in question or "how much" in question:
                # Extract item name from the question
                item_name = None
                for word in question.split():
                    if word.lower() in ["paper", "pens", "pencils", "notebooks", "a4"]:
                        item_name = word.lower()
                        if item_name == "a4":
                            item_name = "a4 paper"
                        break
                
                if not item_name:
                    return {"error": "Could not identify item in inquiry"}
                
                # Get price
                price_result = await self.run({
                    "tool": "get_item_price",
                    "item_name": item_name
                })
                
                if not isinstance(price_result, dict) or "error" in price_result:
                    return {"error": f"Could not get price for {item_name}"}
                
                unit_price = price_result.get("unit_price", 0)
                
                # Check stock for additional context
                stock_result = await self.run({
                    "tool": "check_stock",
                    "item_name": item_name,
                    "as_of_date": datetime.now().isoformat()
                })
                
                if not isinstance(stock_result, dict) or "error" in stock_result:
                    return {"error": f"Could not check stock for {item_name}"}
                
                stock_level = stock_result.get("stock", 0)
                
                return {
                    "item_name": item_name,
                    "unit_price": unit_price,
                    "stock_available": stock_level,
                    "status": "completed"
                }
            
            else:
                return {"error": "Please specify whether you are asking about delivery time or price"}
            
        except Exception as e:
            return {"error": str(e)} 