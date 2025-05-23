# main.py
from smolagents.core import Agent, Orchestrator, Task
from typing import Any, Dict

# Worker 1: Inventory Management
class InventoryAgent(Agent):
    def run(self, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        stock = {"paper": 500, "ink": 200}
        reorder_threshold = 100
        needs_restock = {item: qty < reorder_threshold for item, qty in stock.items()}
        return {"stock": stock, "needs_restock": needs_restock}

# Worker 2: Quoting
class QuotingAgent(Agent):
    def run(self, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        base_prices = {"paper": 1.50, "ink": 2.00}
        discounts = {"paper": 0.10} if context["needs_restock"]["paper"] else {}
        final_prices = {item: base_prices[item] * (1 - discounts.get(item, 0)) for item in base_prices}
        return {"quotes": final_prices}

# Worker 3: Sales Finalization
class SalesAgent(Agent):
    def run(self, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate order processing
        order = {"paper": 100, "ink": 50}
        total = sum(context["quotes"][item] * qty for item, qty in order.items())
        return {"order": order, "total_price": total, "status": "processed"}

# Orchestrator
class MunderDifflinOrchestrator(Orchestrator):
    def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        context = initial_context

        context.update(self.call_agent("inventory", Task("Check inventory", {}), context))
        context.update(self.call_agent("quote", Task("Generate quote", {}), context))
        context.update(self.call_agent("sales", Task("Process sale", {}), context))

        return context

# Instantiate and wire up the system
if __name__ == "__main__":
    orchestrator = MunderDifflinOrchestrator(agents={
        "inventory": InventoryAgent(),
        "quote": QuotingAgent(),
        "sales": SalesAgent(),
    })

    result = orchestrator.run({})
    print("Final Result:")
    print(result)