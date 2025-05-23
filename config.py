from pydantic_settings import BaseSettings
from pydantic import validator
from typing import Optional, Dict, Any, List
from datetime import datetime

class BusinessRule(BaseSettings):
    rule_id: str
    condition: str
    action: str
    parameters: Dict[str, Any]
    enabled: bool = True

class AgentConfig(BaseSettings):
    model: str
    temperature: float
    max_tokens: int
    retry_attempts: int = 3
    timeout_seconds: int = 30
    
    @validator('temperature')
    def validate_temperature(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('Temperature must be between 0 and 1')
        return v
    
    class Config:
        env_prefix = 'AGENT_'

class BusinessRulesConfig(BaseSettings):
    rules: List[BusinessRule]
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        for rule in self.rules:
            if not rule.enabled:
                continue
            if self._evaluate_condition(rule.condition, context):
                return self._execute_action(rule.action, rule.parameters, context)
        return True
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        # Simple condition evaluation - can be extended for more complex rules
        try:
            return eval(condition, {"__builtins__": {}}, context)
        except Exception:
            return False
    
    def _execute_action(self, action: str, parameters: Dict[str, Any], context: Dict[str, Any]) -> bool:
        # Simple action execution - can be extended for more complex actions
        try:
            if action == "reject":
                return False
            elif action == "accept":
                return True
            return True
        except Exception:
            return False

class SystemConfig(BaseSettings):
    log_level: str = "INFO"
    environment: str = "development"
    api_timeout: int = 30
    max_retries: int = 3
    business_rules: BusinessRulesConfig
    
    class Config:
        env_prefix = 'SYSTEM_' 