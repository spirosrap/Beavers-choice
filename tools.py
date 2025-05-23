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
    search_quote_history
)

class CheckStockInput(BaseModel):
    item_name: str
    as_of_date: str

def check_stock(item_name: str, as_of_date: str) -> dict:
    result = get_stock_level(item_name, as_of_date)
    return {"stock": int(result["current_stock"].iloc[0])}

check_stock_tool = Tool(
    check_stock,
    name="check_stock",
    description="Check the stock level for a given item as of a specific date."
)

class GetItemPriceInput(BaseModel):
    item_name: str

def get_item_price(item_name: str) -> dict:
    for item in paper_supplies:
        if item["item_name"].lower() == item_name.lower():
            return {"unit_price": item["unit_price"]}
    return {"error": "Item not found"}

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
    balance = get_cash_balance(as_of_date)
    return {"cash_balance": balance}

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