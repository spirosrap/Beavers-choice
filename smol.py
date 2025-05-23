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
    generate_sample_inventory
)

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
    async def generate(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        # In a real implementation, this would call an actual LLM API
        # For now, we'll simulate a more realistic response
        last_message = messages[-1]["content"]
        if "inventory" in last_message.lower():
            return {"role": "assistant", "content": "Inventory levels checked. Paper: 500, Ink: 200"}
        elif "quote" in last_message.lower():
            return {"role": "assistant", "content": "Quote generated with appropriate discounts"}
        elif "sale" in last_message.lower():
            return {"role": "assistant", "content": "Sale processed successfully"}
        return {"role": "assistant", "content": "Task completed"}

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
            
            # First check if item exists in paper_supplies
            item_exists = any(supply["item_name"].lower() == item.lower() for supply in paper_supplies)
            if not item_exists:
                logger.error(f"Item '{item}' not found in paper supplies")
                return {
                    "stock_level": 0,
                    "needs_restock": True,
                    "status": "error",
                    "error": f"Item '{item}' not found in paper supplies",
                    "item": item
                }
            
            # Get stock level from database
            try:
                # First check if item exists in inventory table
                inventory_check = pd.read_sql(
                    "SELECT item_name FROM inventory WHERE item_name = :item",
                    self.db_engine,
                    params={"item": item}
                )
                
                if inventory_check.empty:
                    logger.error(f"Item '{item}' not found in inventory table")
                    return {
                        "stock_level": 0,
                        "needs_restock": True,
                        "status": "error",
                        "error": f"Item '{item}' not found in inventory table",
                        "item": item
                    }
                
                # Get stock level from transactions
                stock_query = """
                    SELECT COALESCE(SUM(CASE
                        WHEN transaction_type = 'stock_orders' THEN units
                        WHEN transaction_type = 'sales' THEN -units
                        ELSE 0
                    END), 0) AS current_stock
                    FROM transactions
                    WHERE item_name = :item
                """
                
                stock_info = pd.read_sql(
                    stock_query,
                    self.db_engine,
                    params={"item": item}
                )
                
                if stock_info.empty:
                    logger.error(f"No stock information found for item '{item}'")
                    return {
                        "stock_level": 0,
                        "needs_restock": True,
                        "status": "error",
                        "error": f"No stock information found for item '{item}'",
                        "item": item
                    }
                
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
                    
                    # Create transaction directly using SQL
                    transaction_query = """
                        INSERT INTO transactions (item_name, transaction_type, units, price, transaction_date)
                        VALUES (:item_name, :transaction_type, :quantity, :price, :date)
                    """
                    with self.db_engine.connect() as conn:
                        conn.execute(
                            transaction_query,
                            {
                                "item_name": item,
                                "transaction_type": "stock_orders",
                                "quantity": quantity,
                                "price": quantity * unit_price,
                                "date": datetime.now().isoformat()
                            }
                        )
                    
                    # Update stock level after transaction
                    stock_info = pd.read_sql(
                        stock_query,
                        self.db_engine,
                        params={"item": item}
                    )
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
            
            return {
                "stock_level": stock_level,
                "needs_restock": needs_restock,
                "status": "success",
                "item": item
            }
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
            
            return {
                "base_price": base_price,
                "quantity": quantity,
                "discount": discount,
                "final_price": final_price,
                "status": "success"
            }
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
                    # Create transaction using SQLAlchemy text()
                    transaction_query = text("""
                        INSERT INTO transactions (item_name, transaction_type, units, price, transaction_date)
                        VALUES (:item_name, :transaction_type, :quantity, :price, :date)
                    """)
                    
                    with self.db_engine.connect() as conn:
                        conn.execute(
                            transaction_query,
                            {
                                "item_name": item_name,
                                "transaction_type": "sales",
                                "quantity": quantity,
                                "price": item_total,
                                "date": datetime.now().isoformat()
                            }
                        )
                        conn.commit()  # Explicitly commit the transaction
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
            
            return {
                "order_id": order_id,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "total_price": total_price,
                "order_details": order_details
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
        # Create the inventory tool first
        self.inventory_tool = InventoryTool()
        
        # Initialize the parent class with the tool
        super().__init__(
            model=SimpleModel(),
            name="inventory_agent",
            description="Manages inventory levels and reordering",
            tools=[self.inventory_tool]  # Pass the tool instance in a list
        )
        self.db_engine = db_engine  # Use the global db_engine

    def initialize_system_prompt(self) -> str:
        return """You are an inventory management agent. Your role is to check inventory levels and determine if reordering is needed."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            # Extract content safely, handling nested dictionaries
            if isinstance(message, dict) and 'content' in message:
                content = message['content']
            else:
                content = getattr(message, 'content', message)
            
            logger.info(f"Processing inventory check with content: {content}")
            
            # Get a valid item from paper_supplies if not specified
            if not content or not isinstance(content, dict) or 'item' not in content:
                # Use the first item from paper_supplies as default
                default_item = paper_supplies[0]["item_name"]
                logger.info(f"No item specified, using default item: {default_item}")
                item = default_item
            else:
                item = content.get("item")
                # Verify item exists in paper_supplies
                if not any(supply["item_name"].lower() == item.lower() for supply in paper_supplies):
                    logger.error(f"Invalid item '{item}' specified")
                    return {
                        "status": "error",
                        "error": f"Invalid item '{item}'. Please specify a valid item from the inventory.",
                        "item": item
                    }
            
            logger.info(f"Checking inventory for item: {item}")
            
            # Verify item exists in inventory table
            try:
                inventory_check = pd.read_sql(
                    "SELECT item_name FROM inventory WHERE item_name = :item",
                    self.db_engine,
                    params={"item": item}
                )
                
                if inventory_check.empty:
                    logger.error(f"Item '{item}' not found in inventory table")
                    return {
                        "status": "error",
                        "error": f"Item '{item}' not found in inventory table",
                        "item": item
                    }
            except Exception as e:
                logger.error(f"Error checking inventory table: {str(e)}", exc_info=True)
                return {
                    "status": "error",
                    "error": f"Error checking inventory table: {str(e)}",
                    "item": item
                }
            
            # Call the tool with explicit keyword arguments
            try:
                # Use the instance variable directly
                result = await self.inventory_tool.forward(item=item)
                logger.info(f"Inventory check result: {result}")
                
                # Ensure we have a valid result
                if not isinstance(result, dict):
                    logger.error(f"Tool returned invalid result type: {type(result)}")
                    return {
                        "status": "error",
                        "error": f"Invalid result type: {type(result)}",
                        "item": item
                    }
                
                # If the tool returned an error, propagate it
                if result.get("status") == "error":
                    return result
                
                # Ensure we have the required fields
                if "stock_level" not in result:
                    logger.error("Tool result missing 'stock_level' field")
                    return {
                        "status": "error",
                        "error": "Missing required field: stock_level",
                        "item": item
                    }
                
                return result
            except Exception as e:
                logger.error(f"Error calling inventory tool: {str(e)}", exc_info=True)
                return {
                    "status": "error",
                    "error": f"Tool error: {str(e)}",
                    "item": item
                }
            
        except Exception as e:
            logger.error(f"Error in inventory agent: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": f"Agent error: {str(e)}",
                "item": item if 'item' in locals() else "unknown"
            }

class QuotingAgent(MultiStepAgent):
    """Agent for price quoting"""
    def __init__(self):
        # Create the quoting tool first
        self.quoting_tool = QuotingTool()
        
        # Initialize the parent class with the tool
        super().__init__(
            model=SimpleModel(),
            name="quoting_agent",
            description="Generates quotes based on inventory status",
            tools=[self.quoting_tool]  # Pass the tool instance in a list
        )

    def initialize_system_prompt(self) -> str:
        return """You are a quoting agent. Your role is to generate quotes based on inventory status and apply appropriate discounts."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            # Extract content safely, handling nested dictionaries
            if isinstance(message, dict) and 'content' in message:
                content = message['content']
            else:
                content = getattr(message, 'content', message)
            
            logger.info(f"Processing quote with content: {content}")
            
            # Extract item and quantity from content if available, otherwise use defaults
            item = content.get("item", "A4 paper")  # Use A4 paper as default
            quantity = content.get("quantity", 100)
            logger.info(f"Generating quote for {quantity} units of {item}")
            
            # Use the instance variable directly
            result = await self.quoting_tool.forward(item=item, quantity=quantity)
            logger.info(f"Quote generation result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error in quoting agent: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

class SalesAgent(MultiStepAgent):
    """Agent for sales processing"""
    def __init__(self):
        # Create the sales tool first
        self.sales_tool = SalesTool()
        
        # Initialize the parent class with the tool
        super().__init__(
            model=SimpleModel(),
            name="sales_agent",
            description="Processes sales and calculates totals",
            tools=[self.sales_tool]  # Pass the tool instance in a list
        )

    def initialize_system_prompt(self) -> str:
        return """You are a sales agent. Your role is to process sales orders and calculate the total price."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            # Extract content safely, handling nested dictionaries
            if isinstance(message, dict) and 'content' in message:
                content = message['content']
            else:
                content = getattr(message, 'content', message)
            
            logger.info(f"Processing sale with content: {content}")
            
            # Extract order from content if available, otherwise use default
            # Use the item and quantity from the quote
            item = content.get("item", "A4 paper")
            quantity = content.get("quantity", 100)
            order = {item: quantity}  # Create order with the quoted item and quantity
            
            logger.info(f"Processing order: {order}")
            
            # Use the instance variable directly
            result = await self.sales_tool.forward(order=order)
            logger.info(f"Sale processing result: {result}")
            return result
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
            tools=[]  # No tools needed for orchestrator
        )
        self.agents = [
            InventoryAgent(),
            QuotingAgent(),
            SalesAgent()
        ]

    def initialize_system_prompt(self) -> str:
        return """You are a sales workflow orchestrator. Your role is to coordinate the inventory check, quote generation, and sales processing steps."""

    async def process(self, message: Message) -> Dict[str, Any]:
        try:
            logger.info("Starting inventory check...")
            # Step 1: Check inventory
            inventory_result = await self.agents[0].process(message)
            logger.info(f"Inventory check result: {inventory_result}")
            if inventory_result.get("status") == "error":
                logger.error(f"Inventory check failed: {inventory_result.get('error')}")
                return inventory_result

            logger.info("Generating quote...")
            # Step 2: Generate quote
            quote_result = await self.agents[1].process(Message(content=inventory_result, role="user"))
            logger.info(f"Quote generation result: {quote_result}")
            if quote_result.get("status") == "error":
                logger.error(f"Quote generation failed: {quote_result.get('error')}")
                return quote_result

            logger.info("Processing sale...")
            # Step 3: Process sale
            sales_result = await self.agents[2].process(Message(content=quote_result, role="user"))
            logger.info(f"Sale processing result: {sales_result}")
            return sales_result

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