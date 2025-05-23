import csv
import asyncio
import logging
from datetime import datetime
from openai import OpenAI
from orchestrator import OrchestratorAgent
from main import convert_to_dict
from project_starter import get_cash_balance
import re

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def process_quote_request(orchestrator: OrchestratorAgent, request_data: dict, initial_cash_balance: float) -> dict:
    """Process a single quote request through the orchestrator."""
    try:
        # Convert the request into the format expected by the orchestrator
        orchestrator_request = {
            "type": "quote_request",
            "customer_id": f"CUST_{request_data['job'].replace(' ', '_')}",
            "items": parse_items_from_request(request_data['request']),
            "delivery_date": request_data['request_date'],
            "event_type": request_data['event'],
            "need_size": request_data['need_size']
        }
        
        # Process the request through the orchestrator
        result = await orchestrator.coordinate_workflow(orchestrator_request)
        result_dict = convert_to_dict(result)
        
        # Get final cash balance after request processing
        final_cash_balance = get_cash_balance(request_data['request_date'])
        cash_balance_change = final_cash_balance - initial_cash_balance
        
        # Add cash balance tracking to result
        result_dict.update({
            'initial_cash_balance': initial_cash_balance,
            'final_cash_balance': final_cash_balance,
            'cash_balance_change': cash_balance_change,
            'cash_balance_changed': abs(cash_balance_change) > 0.01  # Consider changed if difference > 1 cent
        })
        
        return result_dict
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {"error": str(e)}

def parse_items_from_request(request_text: str) -> list:
    """Parse items from the request text into a structured format."""
    items = []
    # Use regex to find patterns like '1000 sheets of A4 paper' or '500 sheets of A3 paper'
    pattern = re.compile(r"(\d+)\s+([a-zA-Z0-9\s]+?)(?:,| for| and|\.|$)")
    matches = pattern.findall(request_text)
    for match in matches:
        quantity = int(match[0])
        item_name = match[1].strip()
        # Remove leading descriptors like 'sheets of'
        item_name = re.sub(r"^sheets of\s+", "", item_name, flags=re.IGNORECASE)
        # Remove trailing words that are not part of the item name
        for stop_word in ["for", "needed", "required", "needed.", "required."]:
            if item_name.endswith(stop_word):
                item_name = item_name[: -len(stop_word)].strip()
        if quantity > 0 and item_name:
            items.append({
                "name": item_name,
                "quantity": quantity
            })
    # Fallback to old logic for bullet-pointed/multi-line requests
    if not items:
        lines = request_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith(('I would like', 'Dear', 'Thank')):
                continue
            line = line.replace('-', '').replace('•', '').strip()
            parts = line.split(' of ')
            if len(parts) == 2:
                quantity_part = parts[0].strip()
                item_desc = parts[1].strip()
                quantity = 0
                for word in quantity_part.split():
                    try:
                        quantity = int(word.replace(',', ''))
                        break
                    except ValueError:
                        continue
                if quantity > 0:
                    items.append({
                        "name": item_desc,
                        "quantity": quantity
                    })
    return items

async def evaluate_system():
    """Main evaluation function that processes all quote requests and generates results."""
    try:
        # Initialize OpenAI client
        client = OpenAI(
            base_url="https://openai.vocareum.com/v1",
            api_key="voc-00000000000000000000000000000000abcd.12345678"
        )
        
        # Initialize orchestrator
        orchestrator = OrchestratorAgent(
            client=client,
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=1000
        )
        
        # Read quote requests
        results = []
        with open('quote_requests_sample.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                logger.info(f"Processing request from {row['job']} for {row['event']}")
                
                # Get initial cash balance before processing request
                initial_cash_balance = get_cash_balance(row['request_date'])
                
                result = await process_quote_request(orchestrator, row, initial_cash_balance)
                
                # Add original request data to results
                result.update({
                    'job': row['job'],
                    'need_size': row['need_size'],
                    'event': row['event'],
                    'request': row['request'],
                    'request_date': row['request_date']
                })
                results.append(result)
        
        # Write results to CSV
        with open('test_results.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'job', 'need_size', 'event', 'request', 'request_date',
                'status', 'steps', 'error', 'initial_cash_balance',
                'final_cash_balance', 'cash_balance_change', 'cash_balance_changed'
            ])
            writer.writeheader()
            for result in results:
                writer.writerow({
                    'job': result['job'],
                    'need_size': result['need_size'],
                    'event': result['event'],
                    'request': result['request'],
                    'request_date': result['request_date'],
                    'status': result.get('status', 'unknown'),
                    'steps': str(result.get('steps', [])),
                    'error': result.get('error', ''),
                    'initial_cash_balance': result.get('initial_cash_balance', 0),
                    'final_cash_balance': result.get('final_cash_balance', 0),
                    'cash_balance_change': result.get('cash_balance_change', 0),
                    'cash_balance_changed': result.get('cash_balance_changed', False)
                })
        
        # Print summary statistics
        total_requests = len(results)
        successful_quotes = sum(1 for r in results if r.get('status') == 'completed')
        cash_balance_changes = sum(1 for r in results if r.get('cash_balance_changed', False))
        
        print("\n===== EVALUATION SUMMARY =====")
        print(f"Total Requests Processed: {total_requests}")
        print(f"Successfully Fulfilled Quotes: {successful_quotes}")
        print(f"Requests with Cash Balance Changes: {cash_balance_changes}")
        print(f"Unfulfilled Requests: {total_requests - successful_quotes}")
        
        logger.info("Evaluation completed successfully")
        
    except Exception as e:
        logger.error(f"Error in evaluation: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(evaluate_system()) 