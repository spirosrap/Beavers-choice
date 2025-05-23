# main.py
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime
from smolagents.agents import MultiStepAgent, Message, Model
from smolagents.tools import Tool
import pandas as pd
from sqlalchemy import create_engine, Engine, text
from project_starter import (
    init_database,
    get_stock_level,
    create_transaction,
    get_cash_balance,
    generate_financial_report,
    paper_supplies,
    generate_sample_inventory,
    get_all_inventory,
    get_supplier_delivery_date,
    search_quote_history
)
import os
from openai import OpenAI
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
try:
    logger.info("Initializing database...")
    db_engine = create_engine("sqlite:///munder_difflin.db")
    
    # Generate initial inventory
    logger.info("Generating initial inventory...")
    inventory_df = generate_sample_inventory(paper_supplies, coverage=0.4)
    
    # Initialize database with the generated inventory
    logger.info("Setting up database tables...")
    init_database(db_engine)
    
    # Save the inventory to the database
    logger.info("Saving inventory to database...")
    inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)
    
    # Create initial transactions for each item
    logger.info("Creating initial transactions...")
    initial_date = datetime(2025, 1, 1).isoformat()
    for _, item in inventory_df.iterrows():
        try:
            create_transaction(
                item_name=item["item_name"],
                transaction_type="stock_orders",
                quantity=item["current_stock"],
                price=item["current_stock"] * item["unit_price"],
                date=initial_date
            )
        except Exception as e:
            logger.error(f"Error creating initial transaction for {item['item_name']}: {str(e)}", exc_info=True)
    
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
    raise

# Create a simple model for our agents
class SimpleModel(Model):
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openai.vocareum.com/v1",
            api_key="voc-21376185381266773654634673458a21cca09.30251877"
        )
        self.model = "gpt-4-turbo-preview"

    async def generate(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        try:
            # Convert messages to OpenAI format
            openai_messages = [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in messages
            ]

            # Add system message for context
            system_message = {
                "role": "system",
                "content": """You are an AI assistant for a paper supply company. 
                You help with inventory management, quoting, and sales processing.
                Be concise and professional in your responses."""
            }
            openai_messages.insert(0, system_message)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=0.7,
                max_tokens=150
            )

            # Extract and return the response
            return {
                "role": "assistant",
                "content": response.choices[0].message.content
            }

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}", exc_info=True)
            return {
                "role": "assistant",
                "content": f"I apologize, but I encountered an error: {str(e)}"
            }

class InventoryTool(Tool):
    """Tool for inventory management operations"""
    name = "inventory_tool"
    description = "Tool for managing inventory levels and checking stock"
    inputs = {
        "item": {"type": "string", "description": "The item to check or update"},
        "quantity": {
            "type": "integer", 
            "description": "The quantity to update (for update_stock only)",
            "nullable": True
        }
    }
    output_type = "object"
    
    def __init__(self):
        super().__init__()
        self.db_engine = db_engine  # Use the global db_engine
    
    async def forward(self, item: str, quantity: Optional[int] = None) -> Dict[str, Any]:
        try:
            logger.info(f"Checking inventory for item: {item}")
            if not isinstance(item, str):
                raise ValueError(f"Item must be a string, got {type(item)}")
            if not item:
                raise ValueError("Item name cannot be empty")
            
            # Get all inventory first
            all_inventory = get_all_inventory(datetime.now().isoformat())
            if item not in all_inventory:
                logger.error(f"Item '{item}' not found in inventory")
                return {
                    "stock_level": 0,
                    "needs_restock": True,
                    "status": "error",
                    "error": f"Item '{item}' not found in inventory",
                    "item": item
                }
            
            # Get stock level from database
            try:
                stock_info = get_stock_level(item, datetime.now().isoformat())
                stock_level = int(stock_info["current_stock"].iloc[0])
                logger.info(f"Current stock level for {item}: {stock_level}")
                
            except Exception as e:
                logger.error(f"Error getting stock level: {str(e)}", exc_info=True)
                return {
                    "stock_level": 0,
                    "needs_restock": True,
                    "status": "error",
                    "error": f"Error getting stock level: {str(e)}",
                    "item": item
                }
            
            # Validate stock level
            if stock_level < 0:
                logger.error(f"Invalid stock level: {stock_level}")
                return {
                    "stock_level": 0,
                    "needs_restock": True,
                    "status": "error",
                    "error": f"Invalid stock level: {stock_level}",
                    "item": item
                }
            
            # Get minimum stock level from inventory table
            try:
                inventory_info = pd.read_sql(
                    "SELECT min_stock_level FROM inventory WHERE item_name = :item",
                    self.db_engine,
                    params={"item": item}
                )
                
                if inventory_info.empty:
                    min_stock = 100  # Default minimum stock level
                else:
                    min_stock = int(inventory_info["min_stock_level"].iloc[0])
                
                needs_restock = stock_level < min_stock
                
                # If restock is needed, get supplier delivery date
                if needs_restock:
                    delivery_date = get_supplier_delivery_date(
                        datetime.now().isoformat(),
                        min_stock - stock_level
                    )
            except Exception as e:
                logger.error(f"Error getting minimum stock level: {str(e)}", exc_info=True)
                return {
                    "stock_level": stock_level,
                    "needs_restock": True,
                    "status": "error",
                    "error": f"Error getting minimum stock level: {str(e)}",
                    "item": item
                }
            
            if quantity is not None:
                if not isinstance(quantity, int):
                    raise ValueError(f"Quantity must be an integer, got {type(quantity)}")
                logger.info(f"Updating stock for {item} by {quantity}")
                if quantity < 0:
                    raise ValueError("Quantity cannot be negative")
                
                try:
                    # Create transaction for stock update
                    unit_price = pd.read_sql(
                        "SELECT unit_price FROM inventory WHERE item_name = :item",
                        self.db_engine,
                        params={"item": item}
                    )["unit_price"].iloc[0]
                    
                    create_transaction(
                        item_name=item,
                        transaction_type="stock_orders",
                        quantity=quantity,
                        price=quantity * unit_price,
                        date=datetime.now().isoformat()
                    )
                    
                    # Update stock level after transaction
                    stock_info = get_stock_level(item, datetime.now().isoformat())
                    stock_level = int(stock_info["current_stock"].iloc[0])
                    logger.info(f"Updated stock level for {item}: {stock_level}")
                except Exception as e:
                    logger.error(f"Error updating stock: {str(e)}", exc_info=True)
                    return {
                        "stock_level": stock_level,
                        "needs_restock": needs_restock,
                        "status": "error",
                        "error": f"Error updating stock: {str(e)}",
                        "item": item
                    }
            
            result = {
                "stock_level": stock_level,
                "needs_restock": needs_restock,
                "status": "success",
                "item": item
            }
            
            # Add delivery date if restock is needed
            if needs_restock:
                result["delivery_date"] = delivery_date
                
            return result
            
        except Exception as e:
            logger.error(f"Error in inventory tool: {str(e)}", exc_info=True)
            return {
                "stock_level": 0,
                "needs_restock": True,
                "status": "error",
                "error": str(e),
                "item": item
            }

class QuotingTool(Tool):
    """Tool for price and discount calculations"""
    name = "quoting_tool"
    description = "Tool for calculating prices and applying discounts"
    inputs = {
        "item": {"type": "string", "description": "The item to get price for"},
        "quantity": {"type": "integer", "description": "The quantity to calculate discount for"}
    }
    output_type = "object"
    
    async def forward(self, item: str, quantity: int) -> Dict[str, Any]:
        try:
            # Get base price from database
            price_info = pd.read_sql(
                "SELECT unit_price FROM inventory WHERE item_name = :item",
                db_engine,
                params={"item": item}
            )
            
            if price_info.empty:
                logger.error(f"Item '{item}' not found in inventory")
                return {
                    "base_price": 0.0,
                    "discount": 0.0,
                    "final_price": 0.0,
                    "status": "error",
                    "error": f"Item '{item}' not found in inventory"
                }
            
            base_price = float(price_info["unit_price"].iloc[0])
            discount = self.calculate_discount(quantity)
            final_price = base_price * quantity * (1 - discount)
            
            # Check cash balance for large orders
            cash_balance = get_cash_balance(datetime.now().isoformat())
            if final_price > cash_balance:
                logger.warning(f"Order value (${final_price:.2f}) exceeds cash balance (${cash_balance:.2f})")
            
            # Search quote history for similar quotes
            try:
                quote_history = search_quote_history([item], limit=5)
                logger.info(f"Raw quote history type: {type(quote_history)}")
                logger.info(f"Raw quote history length: {len(quote_history) if isinstance(quote_history, (list, tuple)) else 'N/A'}")
                if isinstance(quote_history, (list, tuple)) and quote_history:
                    logger.info(f"First quote entry type: {type(quote_history[0])}")
                    logger.info(f"First quote entry: {quote_history[0]}")
                    if hasattr(quote_history[0], '__dict__'):
                        logger.info(f"First quote entry __dict__: {quote_history[0].__dict__}")
                    if hasattr(quote_history[0], '_asdict'):
                        logger.info(f"First quote entry _asdict: {quote_history[0]._asdict()}")
                    if hasattr(quote_history[0], '_mapping'):
                        logger.info(f"First quote entry _mapping: {quote_history[0]._mapping}")
                    if hasattr(quote_history[0], '__iter__'):
                        logger.info(f"First quote entry as list: {list(quote_history[0])}")
                
                # Extra debug logging before formatting loop
                logger.info(f"quote_history type: {type(quote_history)}; length: {len(quote_history) if hasattr(quote_history, '__len__') else 'N/A'}")
                print(f"quote_history type: {type(quote_history)}; length: {len(quote_history) if hasattr(quote_history, '__len__') else 'N/A'}")
                for idx, q in enumerate(quote_history):
                    logger.info(f"quote_history[{idx}] type: {type(q)}; length: {len(q) if hasattr(q, '__len__') and not isinstance(q, str) else 'N/A'}; value: {str(q)[:200]}")
                    print(f"quote_history[{idx}] type: {type(q)}; length: {len(q) if hasattr(q, '__len__') and not isinstance(q, str) else 'N/A'}; value: {str(q)[:200]}")
                
                formatted_history = []
                
                # Handle case where quote_history is a string
                if isinstance(quote_history, str):
                    try:
                        quote_history = json.loads(quote_history)
                    except json.JSONDecodeError:
                        logger.warning("Quote history is a string but not valid JSON")
                        quote_history = []
                
                # Ensure quote_history is a list
                if not isinstance(quote_history, list):
                    quote_history = [quote_history] if quote_history else []
                
                # Format quote history according to the actual data structure
                for quote in quote_history:
                    try:
                        logger.info(f"Processing quote entry type: {type(quote)}")
                        logger.info(f"Quote entry: {quote}")
                        
                        # Handle different data formats
                        if isinstance(quote, str):
                            try:
                                quote = json.loads(quote)
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse quote string as JSON: {quote}")
                                continue
                        
                        # Convert SQLAlchemy Row to dict if needed
                        if hasattr(quote, '_asdict'):
                            quote = quote._asdict()
                            logger.info(f"Converted using _asdict: {quote}")
                        elif hasattr(quote, '_mapping'):
                            quote = dict(quote._mapping)
                            logger.info(f"Converted using _mapping: {quote}")
                        elif hasattr(quote, '__dict__'):
                            quote = quote.__dict__
                            logger.info(f"Converted using __dict__: {quote}")
                        elif not isinstance(quote, dict):
                            try:
                                # Try to convert to dict if it's a sequence
                                if hasattr(quote, '__iter__') and not isinstance(quote, (str, bytes)):
                                    # Get the keys from the first quote if available
                                    keys = ['original_request', 'total_amount', 'quote_explanation', 
                                           'job_type', 'order_size', 'event_type', 'order_date']
                                    # If we have more values than keys, create a new dictionary with just the first 7 values
                                    if len(quote) > len(keys):
                                        # Try to get the values in the correct order
                                        values = []
                                        for key in keys:
                                            if hasattr(quote, key):
                                                values.append(getattr(quote, key))
                                            else:
                                                values.append(None)
                                        # Create the dictionary one key-value pair at a time
                                        quote = {}
                                        for key, value in zip(keys, values):
                                            quote[key] = value
                                        logger.info(f"Converted sequence with extra values: {quote}")
                                    else:
                                        # If we have fewer values than keys, pad with None
                                        values = list(quote)
                                        while len(values) < len(keys):
                                            values.append(None)
                                        # Create the dictionary one key-value pair at a time
                                        quote = {}
                                        for key, value in zip(keys, values):
                                            quote[key] = value
                                        logger.info(f"Converted sequence with padded values: {quote}")
                                else:
                                    logger.warning(f"Could not convert quote to dict: {quote}")
                                    continue
                            except (TypeError, ValueError) as e:
                                logger.warning(f"Error converting quote to dict: {str(e)}")
                                continue
                            
                        # Ensure all required fields are present with default values
                        formatted_quote = {
                            "original_request": str(quote.get("original_request", "")),
                            "total_amount": float(quote.get("total_amount", 0.0)),
                            "quote_explanation": str(quote.get("quote_explanation", "")),
                            "job_type": str(quote.get("job_type", "")),
                            "order_size": str(quote.get("order_size", "")),
                            "event_type": str(quote.get("event_type", "")),
                            "order_date": str(quote.get("order_date", datetime.now().isoformat()))
                        }
                        formatted_history.append(formatted_quote)
                    except Exception as e:
                        logger.warning(f"Error formatting quote entry: {str(e)}")
                        continue
                
                if not formatted_history:
                    logger.info("No valid quote history found")
                
            except Exception as e:
                logger.warning(f"Could not retrieve quote history: {str(e)}")
                formatted_history = []
            
            result = {
                "base_price": base_price,
                "quantity": quantity,
                "discount": discount,
                "final_price": final_price,
                "status": "success",
                "cash_balance": cash_balance,
                "quote_history": formatted_history
            }
            
            return result
        except Exception as e:
            logger.error(f"Error in quoting tool: {str(e)}")
            return {
                "base_price": 0.0,
                "discount": 0.0,
                "final_price": 0.0,
                "status": "error",
                "error": str(e)
            }
    
    def calculate_discount(self, quantity: int) -> float:
        if quantity > 100:
            return 0.15
        elif quantity > 50:
            return 0.10
        return 0.0

class SalesTool(Tool):
    """Tool for sales processing"""
    name = "sales_tool"
    description = "Tool for processing sales orders and generating order IDs"
    inputs = {
        "order": {
            "type": "object",
            "description": "The order details with items and quantities",
            "properties": {
                "items": {
                    "type": "object",
                    "description": "Dictionary of item names and quantities"
                }
            }
        }
    }
    output_type = "object"
    
    def __init__(self):
        super().__init__()
        self.db_engine = db_engine  # Use the global db_engine
    
    async def forward(self, order: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Handle both direct order format and nested items format
            if isinstance(order, dict):
                if "items" in order:
                    items = order["items"]
                else:
                    items = order
            else:
                raise ValueError("Order must be a dictionary")
            
            if not items:
                raise ValueError("No items in order")
            
            total_price = 0.0
            order_details = []
            
            # Process each item in the order
            for item_name, quantity in items.items():
                # Check if item exists and get price
                item_info = pd.read_sql(
                    "SELECT unit_price FROM inventory WHERE item_name = :item",
                    self.db_engine,
                    params={"item": item_name}
                )
                
                if item_info.empty:
                    raise ValueError(f"Item '{item_name}' not found in inventory")
                
                unit_price = float(item_info["unit_price"].iloc[0])
                item_total = unit_price * quantity
                total_price += item_total
                
                # Create sales transaction
                try:
                    create_transaction(
                        item_name=item_name,
                        transaction_type="sales",
                        quantity=quantity,
                        price=item_total,
                        date=datetime.now().isoformat()
                    )
                except Exception as e:
                    logger.error(f"Error creating transaction for {item_name}: {str(e)}", exc_info=True)
                    raise ValueError(f"Failed to create transaction for {item_name}: {str(e)}")
                
                order_details.append({
                    "item": item_name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total": item_total
                })
            
            order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Generate financial report after processing the sale
            financial_report = generate_financial_report(datetime.now().isoformat())
            
            return {
                "order_id": order_id,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "total_price": total_price,
                "order_details": order_details,
                "financial_report": financial_report
            }
        except Exception as e:
            logger.error(f"Error in sales tool: {str(e)}", exc_info=True)
            return {
                "order_id": "ERROR",
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "total_price": 0.0,
                "error": str(e)
            }

class InventoryAgent(MultiStepAgent):
    """Agent for inventory management"""
    def __init__(self):
        self.inventory_tool = InventoryTool()
        super().__init__(
            model=SimpleModel(),
            name="inventory_agent",
            description="Manages inventory levels and reordering",
            tools=[self.inventory_tool]
        )
        self.db_engine = db_engine

    def initialize_system_prompt(self) -> str:
        return """You are an inventory management agent for a paper supply company. Your role is to:
        1. Analyze inventory levels and determine if reordering is needed
        2. Consider factors like current stock, minimum stock levels, and delivery times
        3. Make intelligent decisions about inventory management
        4. Communicate effectively with other agents about inventory status
        Be thorough in your analysis and provide detailed reasoning for your decisions."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            # Extract content safely
            if isinstance(message, dict):
                content = message
            else:
                content = getattr(message, 'content', {})
            
            # Get inventory data
            inventory_data = await self.inventory_tool.forward(item=content.get("item", "A4 paper"))
            
            # Create a detailed prompt for the LLM
            analysis_prompt = f"""Analyze the following inventory data and provide recommendations:
            Item: {inventory_data.get('item')}
            Current Stock: {inventory_data.get('stock_level')}
            Needs Restock: {inventory_data.get('needs_restock')}
            Delivery Date: {inventory_data.get('delivery_date', 'N/A')}
            
            Please provide:
            1. Analysis of the current situation
            2. Recommendation for action
            3. Reasoning for your decision
            """
            
            # Get LLM's analysis
            analysis = await self.model.generate([{"role": "user", "content": analysis_prompt}])
            
            return {
                "status": "success",
                "inventory_data": inventory_data,
                "analysis": analysis["content"],
                "recommendation": analysis["content"]
            }
        except Exception as e:
            logger.error(f"Error in inventory agent: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

class QuotingAgent(MultiStepAgent):
    """Agent for price quoting"""
    def __init__(self):
        self.quoting_tool = QuotingTool()
        super().__init__(
            model=SimpleModel(),
            name="quoting_agent",
            description="Generates quotes based on inventory status",
            tools=[self.quoting_tool]
        )

    def initialize_system_prompt(self) -> str:
        return """You are a quoting agent for a paper supply company. Your role is to:
        1. Analyze customer requirements and inventory status
        2. Consider market conditions and competitive pricing
        3. Make intelligent decisions about pricing and discounts
        4. Provide detailed quotes with clear reasoning
        Be strategic in your pricing decisions and consider long-term customer relationships."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            # Extract content safely
            if isinstance(message, dict):
                content = message
            else:
                content = getattr(message, 'content', {})
            
            # Get quote data
            quote_data = await self.quoting_tool.forward(
                item=content.get("item", "A4 paper"),
                quantity=content.get("quantity", 100)
            )
            
            # Create a detailed prompt for the LLM
            quote_prompt = f"""Analyze the following quote request and provide a strategic recommendation:
            Item: {content.get('item')}
            Quantity: {content.get('quantity')}
            Base Price: {quote_data.get('base_price')}
            Current Discount: {quote_data.get('discount')}
            Quote History: {quote_data.get('quote_history', [])}
            
            Please provide:
            1. Analysis of the pricing situation
            2. Recommendation for final price and discount
            3. Strategic reasoning for your decision
            """
            
            # Get LLM's analysis
            analysis = await self.model.generate([{"role": "user", "content": quote_prompt}])
            
            return {
                "status": "success",
                "quote_data": quote_data,
                "analysis": analysis["content"],
                "final_quote": analysis["content"]
            }
        except Exception as e:
            logger.error(f"Error in quoting agent: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

class SalesAgent(MultiStepAgent):
    """Agent for sales processing"""
    def __init__(self):
        self.sales_tool = SalesTool()
        super().__init__(
            model=SimpleModel(),
            name="sales_agent",
            description="Processes sales and calculates totals",
            tools=[self.sales_tool]
        )

    def initialize_system_prompt(self) -> str:
        return """You are a sales agent for a paper supply company. Your role is to:
        1. Process sales orders efficiently and accurately
        2. Consider customer history and preferences
        3. Make intelligent decisions about order processing
        4. Provide detailed order confirmations
        Be customer-focused and ensure a smooth sales process."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            # Extract content safely
            if isinstance(message, dict):
                content = message
            else:
                content = getattr(message, 'content', {})
            
            # Process the sale
            order = {
                "items": {
                    content.get("item", "A4 paper"): content.get("quantity", 100)
                }
            }
            sale_data = await self.sales_tool.forward(order=order)
            
            # Create a detailed prompt for the LLM
            sale_prompt = f"""Analyze the following sale and provide insights:
            Order ID: {sale_data.get('order_id')}
            Items: {order['items']}
            Total Price: {sale_data.get('total_price')}
            Financial Report: {sale_data.get('financial_report', {})}
            
            Please provide:
            1. Analysis of the sale
            2. Recommendations for follow-up
            3. Insights for future sales
            """
            
            # Get LLM's analysis
            analysis = await self.model.generate([{"role": "user", "content": sale_prompt}])
            
            return {
                "status": "success",
                "sale_data": sale_data,
                "analysis": analysis["content"],
                "recommendations": analysis["content"]
            }
        except Exception as e:
            logger.error(f"Error in sales agent: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

class SalesOrchestrator(MultiStepAgent):
    """Orchestrator for managing the sales workflow"""
    def __init__(self):
        super().__init__(
            model=SimpleModel(),
            name="sales_orchestrator",
            description="Orchestrates the sales workflow",
            tools=[]
        )
        self.agents = [
            InventoryAgent(),
            QuotingAgent(),
            SalesAgent()
        ]

    def initialize_system_prompt(self) -> str:
        return """You are a sales workflow orchestrator for a paper supply company. Your role is to:
        1. Coordinate between inventory, quoting, and sales agents
        2. Make intelligent decisions about workflow management
        3. Handle complex scenarios and edge cases
        4. Ensure smooth communication between agents
        Be strategic in your orchestration and maintain a holistic view of the process."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            # Extract content safely
            if isinstance(message, dict):
                content = message
            else:
                content = getattr(message, 'content', {})
            
            # Create a detailed prompt for the LLM about the overall workflow
            workflow_prompt = f"""Analyze the following sales request and determine the best workflow:
            Request: {content}
            
            Please provide:
            1. Analysis of the request
            2. Recommended workflow steps
            3. Potential challenges and solutions
            """
            
            # Get LLM's workflow analysis
            workflow_analysis = await self.model.generate([{"role": "user", "content": workflow_prompt}])
            
            # Execute the workflow with LLM-guided orchestration
            inventory_result = await self.agents[0].process(Message(content=content))
            if inventory_result.get("status") == "error":
                return inventory_result

            # Pass inventory analysis to quoting agent
            quote_message = Message(content={
                **content,
                "inventory_analysis": inventory_result.get("analysis")
            })
            quote_result = await self.agents[1].process(quote_message)
            if quote_result.get("status") == "error":
                return quote_result

            # Pass quote analysis to sales agent
            sale_message = Message(content={
                **content,
                "quote_analysis": quote_result.get("analysis")
            })
            sales_result = await self.agents[2].process(sale_message)
            
            # Get final analysis from LLM
            final_analysis_prompt = f"""Analyze the complete sales workflow results:
            Inventory Analysis: {inventory_result.get('analysis')}
            Quote Analysis: {quote_result.get('analysis')}
            Sales Analysis: {sales_result.get('analysis')}
            
            Please provide:
            1. Overall workflow analysis
            2. Success metrics
            3. Recommendations for improvement
            """
            
            final_analysis = await self.model.generate([{"role": "user", "content": final_analysis_prompt}])
            
            return {
                "status": "success",
                "workflow_analysis": workflow_analysis["content"],
                "inventory_result": inventory_result,
                "quote_result": quote_result,
                "sales_result": sales_result,
                "final_analysis": final_analysis["content"]
            }

        except Exception as e:
            logger.error(f"Orchestrator process failed: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

async def main():
    try:
        logger.info("Initializing orchestrator...")
        orchestrator = SalesOrchestrator()
        
        logger.info("Starting workflow...")
        result = await orchestrator.process(Message(content={}, role="user"))
        
        logger.info("Workflow completed")
        print("Final Result:")
        print(result)
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}", exc_info=True)
        print({
            "status": "error",
            "error": str(e),
            "step": "main"
        })

if __name__ == "__main__":
    asyncio.run(main())