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

def check_stock(item_name: str, as_of_date: str) -> dict:
    logger.debug(f"check_stock called with item_name={item_name}, as_of_date={as_of_date}")
    try:
        result = get_stock_level(item_name, as_of_date)
        logger.debug(f"get_stock_level result for {item_name}: {result}")
        if result.empty:
            logger.debug(f"No stock information found for {item_name}")
            return {"error": f"No stock information found for {item_name}"}
        stock_level = int(result["current_stock"].iloc[0])
        logger.debug(f"Stock level for {item_name} as of {as_of_date}: {stock_level}")
        return {"stock": stock_level}
    except Exception as e:
        logger.debug(f"Exception in check_stock for {item_name}: {e}")
        return {"error": f"Error checking stock for {item_name}: {str(e)}"}

check_stock_tool = Tool(
    check_stock,
    name="check_stock",
    description="Check the stock level for a given item as of a specific date."
)

class GetItemPriceInput(BaseModel):
    item_name: str

def get_item_price(item_name: str) -> dict:
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
    get_item_price,
    name="get_item_price",
    description="Get the unit price for a given item."
)

class CreateTransactionInput(BaseModel):
    item_name: str
    transaction_type: str
    quantity: int
    price: float
    date: str

def create_transaction_tool(item_name: str, transaction_type: str, quantity: int, price: float, date: str) -> dict:
    transaction_id = create_transaction(
        item_name, transaction_type, quantity, price, date
    )
    return {"transaction_id": transaction_id}

create_transaction_tool = Tool(
    create_transaction_tool,
    name="create_transaction",
    description="Create a transaction for an item."
)

class GetAllInventoryInput(BaseModel):
    as_of_date: str

def get_all_inventory_tool(as_of_date: str) -> dict:
    inventory = get_all_inventory(as_of_date)
    return {"inventory": inventory}

get_all_inventory_tool = Tool(
    get_all_inventory_tool,
    name="get_all_inventory",
    description="Get a complete inventory snapshot as of a specific date."
)

class GetSupplierDeliveryDateInput(BaseModel):
    input_date_str: str
    quantity: int

def get_supplier_delivery_date_tool(input_date_str: str, quantity: int) -> dict:
    delivery_date = get_supplier_delivery_date(input_date_str, quantity)
    return {"delivery_date": delivery_date}

get_supplier_delivery_date_tool = Tool(
    get_supplier_delivery_date_tool,
    name="get_supplier_delivery_date",
    description="Get the estimated delivery date for a supplier order based on quantity."
)

class GetCashBalanceInput(BaseModel):
    as_of_date: str

def get_cash_balance_tool(as_of_date: str) -> dict:
    try:
        balance = get_cash_balance(as_of_date)
        return {"balance": balance}
    except Exception as e:
        return {"error": f"Error checking cash balance: {str(e)}"}

get_cash_balance_tool = Tool(
    get_cash_balance_tool,
    name="get_cash_balance",
    description="Get the current cash balance as of a specific date."
)

class GenerateFinancialReportInput(BaseModel):
    as_of_date: str

def generate_financial_report_tool(as_of_date: str) -> dict:
    report = generate_financial_report(as_of_date)
    return {"financial_report": report}

generate_financial_report_tool = Tool(
    generate_financial_report_tool,
    name="generate_financial_report",
    description="Generate a complete financial report as of a specific date."
)

class SearchQuoteHistoryInput(BaseModel):
    search_terms: list[str]
    limit: int = 5

def search_quote_history_tool(search_terms: list[str], limit: int = 5) -> dict:
    quotes = search_quote_history(search_terms, limit)
    return {"quotes": quotes}

search_quote_history_tool = Tool(
    search_quote_history_tool,
    name="search_quote_history",
    description="Search historical quotes based on provided terms."
) 