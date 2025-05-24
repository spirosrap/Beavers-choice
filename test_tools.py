from project_starter import (
    paper_supplies,
    get_stock_level,
    create_transaction,
    get_all_inventory,
    get_supplier_delivery_date,
    get_cash_balance,
    generate_financial_report,
    search_quote_history,
    init_database,
    db_engine
)
from datetime import datetime
import pandas as pd

def test_tools():
    # Initialize database first
    init_database(db_engine)
    
    # Use the correct date (2025-01-01T00:00:00) for all checks
    test_date = "2025-01-01T00:00:00"

    print("\nTesting get_stock_level:")
    stock_result = get_stock_level("A4 paper", test_date)
    print(f"Stock result: {stock_result}")

    print("\nTesting price lookup for 'A4 paper':")
    price_result = next((item["unit_price"] for item in paper_supplies if item["item_name"] == "A4 paper"), None)
    print(f"Unit price for A4 paper: {price_result}")

    print("\nTesting get_cash_balance:")
    balance_result = get_cash_balance(test_date)
    print(f"Balance result: {balance_result}")

    print("\nTesting get_all_inventory:")
    inventory_result = get_all_inventory(test_date)
    print(f"Inventory result: {inventory_result}")

    print("\nTesting get_supplier_delivery_date:")
    delivery_result = get_supplier_delivery_date(test_date, 100)
    print(f"Delivery result: {delivery_result}")

    print("\nTesting create_transaction:")
    transaction_result = create_transaction("A4 paper", "sales", 10, price_result * 10 if price_result else 0, test_date)
    print(f"Transaction result: {transaction_result}")

    print("\nTesting generate_financial_report:")
    report_result = generate_financial_report(test_date)
    print(f"Financial report result: {report_result}")

    print("\nTesting search_quote_history:")
    quote_result = search_quote_history(["paper", "bulk"], 5)
    print(f"Quote history result: {quote_result}")

def test_quote_requests():
    """Test quote requests with different scenarios."""
    # Initialize database
    init_database(db_engine)
    test_date = "2025-01-01T00:00:00"
    
    # Test cases based on quote_requests_sample.csv
    test_cases = [
        {
            "name": "Office use - A4 paper",
            "items": [{"name": "A4 paper", "quantity": 1000}],
            "expected_status": "completed",
            "should_change_balance": False,  # Quotes shouldn't change balance
            "job": "office manager",
            "event": "office use"
        },
        {
            "name": "Presentation - A3 paper",
            "items": [{"name": "A3 paper", "quantity": 500}],
            "expected_status": "completed",
            "should_change_balance": False,
            "job": "presentation manager",
            "event": "presentation"
        },
        {
            "name": "Conference - Cardstock",
            "items": [{"name": "Cardstock", "quantity": 1000}],
            "expected_status": "completed",
            "should_change_balance": False,
            "job": "conference organizer",
            "event": "conference"
        },
        {
            "name": "Glossy paper order",
            "items": [{"name": "Glossy paper", "quantity": 100}],
            "expected_status": "completed",
            "should_change_balance": False,
            "job": "designer",
            "event": "marketing"
        },
        {
            "name": "Large order - A4 paper (should fail)",
            "items": [{"name": "A4 paper", "quantity": 4000}],
            "expected_status": "rejected",
            "should_change_balance": False,
            "job": "bulk buyer",
            "event": "bulk purchase"
        },
        {
            "name": "Crepe paper - too large (should fail)",
            "items": [{"name": "Crepe paper", "quantity": 10000}],
            "expected_status": "rejected",
            "should_change_balance": False,
            "job": "party planner",
            "event": "party"
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print(f"Context: {test_case['job']} organizing {test_case['event']}")
        
        # Get initial cash balance
        initial_balance = get_cash_balance(test_date)
        
        # Check stock for all items first
        all_in_stock = True
        quote_details = []
        total_amount = 0
        
        for item in test_case["items"]:
            stock_result = get_stock_level(item["name"], test_date)
            if stock_result.empty or stock_result["current_stock"].iloc[0] < item["quantity"]:
                all_in_stock = False
                print(f"Insufficient stock for {item['name']}. Available: {stock_result['current_stock'].iloc[0] if not stock_result.empty else 0}, Requested: {item['quantity']}")
                break
            
            # Get price for the item
            price = next((p["unit_price"] for p in paper_supplies if p["item_name"] == item["name"]), 0)
            item_total = price * item["quantity"]
            total_amount += item_total
            
            quote_details.append({
                "item_name": item["name"],
                "quantity": item["quantity"],
                "unit_price": price,
                "item_total": item_total,
                "stock_available": stock_result["current_stock"].iloc[0] if not stock_result.empty else 0
            })
        
        status = "completed" if all_in_stock else "rejected"
        
        # Get final cash balance
        final_balance = get_cash_balance(test_date)
        cash_balance_changed = initial_balance != final_balance
        
        # Record results
        results.append({
            "test_case": test_case["name"],
            "job": test_case["job"],
            "event": test_case["event"],
            "items": test_case["items"],
            "expected_status": test_case["expected_status"],
            "actual_status": status,
            "quote_details": quote_details,
            "total_amount": total_amount,
            "initial_balance": initial_balance,
            "final_balance": final_balance,
            "cash_balance_changed": cash_balance_changed,
            "expected_balance_change": test_case["should_change_balance"]
        })
    
    # Save results to CSV
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results

def test_sales_requests():
    """Test sales requests with different scenarios."""
    # Initialize database
    init_database(db_engine)
    test_date = "2025-01-01T00:00:00"
    
    # Sales test cases (ensure sufficient stock for these)
    test_cases = [
        {
            "name": "Sale - A4 paper",
            "items": [{"name": "A4 paper", "quantity": 100}],
            "should_change_balance": True
        },
        {
            "name": "Sale - Cardstock",
            "items": [{"name": "Cardstock", "quantity": 200}],
            "should_change_balance": True
        },
        {
            "name": "Sale - A3 paper",
            "items": [{"name": "A3 paper", "quantity": 150}],
            "should_change_balance": True
        },
        {
            "name": "Sale - Glossy paper (insufficient stock)",
            "items": [{"name": "Glossy paper", "quantity": 10000}],
            "should_change_balance": False  # Should fail
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        initial_balance = get_cash_balance(test_date)
        all_in_stock = True
        for item in test_case["items"]:
            stock_result = get_stock_level(item["name"], test_date)
            if stock_result.empty or stock_result["current_stock"].iloc[0] < item["quantity"]:
                all_in_stock = False
                print(f"Insufficient stock for {item['name']}. Available: {stock_result['current_stock'].iloc[0] if not stock_result.empty else 0}, Requested: {item['quantity']}")
                break
        transaction_ids = []
        status = "rejected"
        try:
            if all_in_stock:
                for item in test_case["items"]:
                    price = next((p["unit_price"] for p in paper_supplies if p["item_name"] == item["name"]), 0)
                    print(f"DEBUG: Creating sales transaction for {item['name']} with unit price {price} and quantity {item['quantity']}")
                    transaction_id = create_transaction(
                        item["name"],
                        "sales",
                        item["quantity"],
                        price * item["quantity"],
                        test_date
                    )
                    print(f"DEBUG: Transaction ID for {item['name']}: {transaction_id}")
                    transaction_ids.append(transaction_id)
                status = "completed"
        except ValueError as e:
            print(f"Sales transaction failed as expected: {str(e)}")
            transaction_ids = []
            status = "rejected"
        final_balance = get_cash_balance(test_date)
        cash_balance_changed = initial_balance != final_balance
        results.append({
            "test_case": test_case["name"],
            "items": test_case["items"],
            "expected_status": "completed" if test_case["should_change_balance"] else "rejected",
            "actual_status": status,
            "transaction_ids": transaction_ids if status == "completed" else None,
            "initial_balance": initial_balance,
            "final_balance": final_balance,
            "cash_balance_changed": cash_balance_changed,
            "expected_balance_change": test_case["should_change_balance"]
        })
    pd.DataFrame(results).to_csv("test_sales_results.csv", index=False)
    return results

if __name__ == "__main__":
    # Initialize database once for all tests
    init_database(db_engine)
    
    print("Running basic tool tests...")
    test_tools()
    
    print("\nRunning quote request tests...")
    test_quote_requests()
    
    print("\nRunning sales request tests...")
    test_sales_requests() 