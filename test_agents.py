from orchestrator import OrchestratorAgent
import json

def test_quote_request():
    print("\n=== Testing Quote Request ===")
    orchestrator = OrchestratorAgent()
    
    # Test a quote request
    quote_request = {
        "type": "quote_request",
        "customer_id": "CUST001",
        "items": [
            {"name": "Premium Paper", "quantity": 10},
            {"name": "Executive Pens", "quantity": 5}
        ]
    }
    
    result = orchestrator.coordinate_workflow(quote_request)
    print("\nQuote Request Result:")
    print(json.dumps(result, indent=2))

def test_sale_request():
    print("\n=== Testing Sale Request ===")
    orchestrator = OrchestratorAgent()
    
    # Test a sale request
    sale_request = {
        "type": "sale_request",
        "customer_id": "CUST002",
        "items": [
            {"name": "Standard Paper", "quantity": 5},
            {"name": "Basic Pens", "quantity": 3}
        ],
        "payment_method": "credit_card"
    }
    
    result = orchestrator.coordinate_workflow(sale_request)
    print("\nSale Request Result:")
    print(json.dumps(result, indent=2))

def test_customer_inquiry():
    print("\n=== Testing Customer Inquiry ===")
    orchestrator = OrchestratorAgent()
    
    # Test a customer inquiry
    inquiry_request = {
        "type": "inquiry",
        "customer_id": "CUST003",
        "question": "What is the delivery time for Premium Paper?",
        "priority": "high"
    }
    
    result = orchestrator.coordinate_workflow(inquiry_request)
    print("\nCustomer Inquiry Result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    print("Starting Multi-Agent System Tests...")
    test_quote_request()
    test_sale_request()
    test_customer_inquiry()
    print("\nAll tests completed!") 