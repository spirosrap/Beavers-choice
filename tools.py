from pydantic import BaseModel
from pydantic_ai.tools import Tool
from project_starter import (
    get_stock_level,
    create_transaction,
    paper_supplies,
    get_all_inventory,
    get_supplier_delivery_date,
    get_cash_balance,
    generate_financial_report,
    search_quote_history,
    get_price
)
import logging
import asyncio

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('debug.log')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class CheckStockInput(BaseModel):
    item_name: str
    as_of_date: str

async def check_stock_func(item_name: str, as_of_date: str) -> dict:
    print(f"check_stock_func called with item_name={item_name}, as_of_date={as_of_date}")
    logger.debug(f"check_stock_func called with item_name={item_name}, as_of_date={as_of_date}")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _check_stock_sync(item_name, as_of_date))

def _check_stock_sync(item_name: str, as_of_date: str) -> dict:
    print(f"_check_stock_sync called with item_name={item_name}, as_of_date={as_of_date}")
    logger.debug(f"_check_stock_sync called with item_name={item_name}, as_of_date={as_of_date}")
    try:
        result = get_stock_level(item_name, as_of_date)
        print(f"DEBUG: get_stock_level returned DataFrame for {item_name}:\n{result}")
        logger.debug(f"get_stock_level result for {item_name}: {result}")
        
        if result.empty:
            print(f"No stock information found for {item_name}")
            logger.debug(f"No stock information found for {item_name}")
            return {"error": f"Item {item_name} not found in inventory"}
            
        stock_level = int(result["current_stock"].iloc[0])
        print(f"Stock level for {item_name} as of {as_of_date}: {stock_level}")
        logger.debug(f"Stock level for {item_name} as of {as_of_date}: {stock_level}")
        
        if stock_level < 0:
            print(f"Warning: Negative stock level detected for {item_name}: {stock_level}")
            logger.warning(f"Negative stock level detected for {item_name}: {stock_level}")
            return {"error": f"Invalid stock level detected for {item_name}: {stock_level}"}
            
        return {"stock": stock_level}
    except Exception as e:
        print(f"Exception in check_stock for {item_name}: {e}")
        logger.debug(f"Exception in check_stock for {item_name}: {e}")
        return {"error": f"Error checking stock for {item_name}: {str(e)}"}

check_stock_tool = Tool(
    check_stock_func,
    name="check_stock",
    description="Check the stock level for a given item as of a specific date."
)

class GetItemPriceInput(BaseModel):
    item_name: str

async def get_item_price_func(item_name: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _get_item_price_sync(item_name))

def _get_item_price_sync(item_name: str) -> dict:
    logger.debug(f"get_item_price called with item_name={item_name}")
    try:
        result = get_price(item_name)
        logger.debug(f"get_price result for {item_name}: {result}")
        if result.empty:
            logger.debug(f"No price information found for {item_name}")
            return {"error": f"No price information found for {item_name}"}
        unit_price = float(result["unit_price"].iloc[0])
        logger.debug(f"Unit price for {item_name}: {unit_price}")
        return {"unit_price": unit_price}
    except Exception as e:
        logger.debug(f"Exception in get_item_price for {item_name}: {e}")
        return {"error": f"Error getting price for {item_name}: {str(e)}"}

get_item_price_tool = Tool(
    get_item_price_func,
    name="get_item_price",
    description="Get the unit price for a given item."
)

class CreateTransactionInput(BaseModel):
    item_name: str
    transaction_type: str
    quantity: int
    price: float
    date: str

async def create_transaction_tool_func(item_name: str, transaction_type: str, quantity: int, price: float, date: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: {"transaction_id": create_transaction(item_name, transaction_type, quantity, price, date)})

create_transaction_tool = Tool(
    create_transaction_tool_func,
    name="create_transaction",
    description="Create a transaction for an item."
)

class GetAllInventoryInput(BaseModel):
    as_of_date: str

async def get_all_inventory_tool_func(as_of_date: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: {"inventory": get_all_inventory(as_of_date)})

get_all_inventory_tool = Tool(
    get_all_inventory_tool_func,
    name="get_all_inventory",
    description="Get a complete inventory snapshot as of a specific date."
)

class GetSupplierDeliveryDateInput(BaseModel):
    input_date_str: str
    quantity: int

async def get_supplier_delivery_date_tool_func(input_date_str: str, quantity: int) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: {"delivery_date": get_supplier_delivery_date(input_date_str, quantity)})

get_supplier_delivery_date_tool = Tool(
    get_supplier_delivery_date_tool_func,
    name="get_supplier_delivery_date",
    description="Get the estimated delivery date for a supplier order based on quantity."
)

class GetCashBalanceInput(BaseModel):
    as_of_date: str

async def get_cash_balance_tool_func(as_of_date: str) -> dict:
    loop = asyncio.get_event_loop()
    def _get():
        try:
            balance = get_cash_balance(as_of_date)
            return {"balance": balance}
        except Exception as e:
            return {"error": f"Error checking cash balance: {str(e)}"}
    return await loop.run_in_executor(None, _get)

get_cash_balance_tool = Tool(
    get_cash_balance_tool_func,
    name="get_cash_balance",
    description="Get the current cash balance as of a specific date."
)

class GenerateFinancialReportInput(BaseModel):
    as_of_date: str

async def generate_financial_report_tool_func(as_of_date: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: {"financial_report": generate_financial_report(as_of_date)})

generate_financial_report_tool = Tool(
    generate_financial_report_tool_func,
    name="generate_financial_report",
    description="Generate a complete financial report as of a specific date."
)

class SearchQuoteHistoryInput(BaseModel):
    search_terms: list[str]
    limit: int = 5

async def search_quote_history_tool_func(search_terms: list[str], limit: int = 5) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: {"quotes": search_quote_history(search_terms, limit)})

search_quote_history_tool = Tool(
    search_quote_history_tool_func,
    name="search_quote_history",
    description="Search historical quotes based on provided terms."
) 