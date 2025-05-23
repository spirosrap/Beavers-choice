from project_starter import init_database, db_engine, create_transaction
from datetime import datetime

if __name__ == "__main__":
    # Initialize the database
    init_database(db_engine)
    # Add initial stock for 'A4 paper'
    item_name = "A4 paper"
    quantity = 5000  # Set an initial stock quantity
    price = 0  # Price is not relevant for stock_orders
    date = datetime.now().isoformat()
    try:
        transaction_id = create_transaction(item_name, "stock_orders", quantity, price, date)
        print(f"Initialized stock for {item_name}: {quantity} units (transaction ID: {transaction_id})")
    except Exception as e:
        print(f"Error initializing stock: {e}") 