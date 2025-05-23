import json
import logging
import asyncio
from openai import OpenAI
from orchestrator import OrchestratorAgent
from datetime import datetime
from project_starter import init_database, db_engine
from config import AgentConfig, SystemConfig, BusinessRule, BusinessRulesConfig

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_configuration() -> tuple[AgentConfig, SystemConfig]:
    """Load configuration from environment variables."""
    # Default business rules
    business_rules = BusinessRulesConfig(rules=[
        BusinessRule(
            rule_id="large_order",
            condition="item.get('quantity', 0) > 10000",
            action="reject",
            parameters={"reason": "Order quantity too large"},
            enabled=True
        ),
        BusinessRule(
            rule_id="wedding_order",
            condition="'wedding' in request.get('event_type', '').lower() and len(request.get('items', [])) > 5",
            action="reject",
            parameters={"reason": "Complex wedding orders not accepted"},
            enabled=True
        )
    ])
    
    # System configuration
    system_config = SystemConfig(
        log_level="DEBUG",
        environment="development",
        api_timeout=30,
        max_retries=3,
        business_rules=business_rules
    )
    
    # Agent configuration
    agent_config = AgentConfig(
        model="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=1000,
        retry_attempts=3,
        timeout_seconds=30
    )
    
    return agent_config, system_config

def convert_to_dict(obj):
    """Convert an object to a dictionary, handling special cases."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    elif hasattr(obj, 'dict'):
        return obj.dict()
    elif isinstance(obj, dict):
        return {k: convert_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_dict(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return {k: convert_to_dict(v) for k, v in obj.__dict__.items()}
    return obj

async def main():
    try:
        # Initialize database before any agent/orchestrator logic
        init_database(db_engine)
        
        # Load configuration
        agent_config, system_config = load_configuration()

        # Create agent_configs dict for each agent type
        agent_configs = {
            "inventory": agent_config,
            "quoting": agent_config,
            "sales": agent_config,
            "finance": agent_config,
            "customer_service": agent_config
        }

        # Configure OpenAI client with Vocareum
        client = OpenAI(
            base_url="https://openai.vocareum.com/v1",
            api_key="voc-00000000000000000000000000000000abcd.12345678"
        )
        
        logger.debug("Initializing OpenAI client with Vocareum")
        
        # Initialize orchestrator with configuration
        orchestrator = OrchestratorAgent(
            client=client,
            agent_configs=agent_configs,
            system_config=system_config,
            model=agent_config.model,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens
        )
        logger.debug("Initialized OrchestratorAgent with configuration")

        # Example: Quote request workflow
        quote_request = {
            "type": "quote_request",
            "customer_id": "CUST001",
            "items": [
                {"name": "A4 paper", "quantity": 1000}
            ]
        }
        print("\nProcessing quote request through orchestrator...")
        logger.debug("Sending quote request to orchestrator")
        quote_result = await orchestrator.coordinate_workflow(quote_request)
        quote_result_dict = convert_to_dict(quote_result)
        logger.debug(f"Quote request result: {json.dumps(quote_result_dict)}")
        print(json.dumps(quote_result_dict, indent=2))

        # Example: Sale request workflow
        sale_request = {
            "type": "sale_request",
            "customer_id": "CUST002",
            "items": [
                {"name": "A4 paper", "quantity": 1000}
            ],
            "payment_method": "credit_card"
        }
        print("\nProcessing sale request through orchestrator...")
        logger.debug("Sending sale request to orchestrator")
        sale_result = await orchestrator.coordinate_workflow(sale_request)
        sale_result_dict = convert_to_dict(sale_result)
        logger.debug(f"Sale request result: {json.dumps(sale_result_dict)}")
        print(json.dumps(sale_result_dict, indent=2))

        # Example: Customer inquiry workflow
        inquiry_request = {
            "type": "inquiry",
            "customer_id": "CUST003",
            "question": "What is the delivery time for A4 paper?"
        }
        print("\nProcessing customer inquiry through orchestrator...")
        logger.debug("Sending inquiry request to orchestrator")
        inquiry_result = await orchestrator.coordinate_workflow(inquiry_request)
        inquiry_result_dict = convert_to_dict(inquiry_result)
        logger.debug(f"Inquiry request result: {json.dumps(inquiry_result_dict)}")
        print(json.dumps(inquiry_result_dict, indent=2))

    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 