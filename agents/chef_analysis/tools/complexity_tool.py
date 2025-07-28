"""
Complexity Analysis Tool for Chef Cookbooks
Calculates complexity scores and migration effort assessment
"""

import logging
import json
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

def chef_complexity_calculator(tree_sitter_facts: Union[Dict[str, Any], str], correlation_id: str = None) -> str:
    """
    Calculate complexity score and migration effort for Chef cookbook based on tree-sitter analysis.
    
    This tool analyzes the structural complexity of Chef cookbooks and provides:
    - Complexity scoring based on resource count and dependencies
    - Migration effort assessment (LOW/MEDIUM/HIGH)
    - Risk factor identification
    - Migration priority recommendations
    - Time estimates for migration
    
    :param tree_sitter_facts: Dictionary or JSON string containing tree-sitter analysis results from the tree-sitter analyzer tool
    :param correlation_id: Optional correlation ID for logging and tracking
    :return: JSON string containing complexity analysis results
    """
    try:
        logger.info(f"[{correlation_id}] Starting complexity analysis")
        
        # Handle string input (convert from JSON string to dict)
        if isinstance(tree_sitter_facts, str):
            try:
                # Clean up the string and parse JSON
                cleaned_facts = tree_sitter_facts.strip()
                if cleaned_facts.startswith('"') and cleaned_facts.endswith('"'):
                    cleaned_facts = cleaned_facts[1:-1]  # Remove outer quotes
                facts = json.loads(cleaned_facts)
            except json.JSONDecodeError as e:
                logger.error(f"[{correlation_id}] JSON parsing failed: {e}")
                facts = {}
        else:
            facts = tree_sitter_facts
        
        if not isinstance(facts, dict):
            logger.error(f"[{correlation_id}] tree_sitter_facts parameter is not a dictionary: {type(facts)}")
            return _create_error_complexity_result()
        
        # Extract base complexity score
        complexity_score = facts.get('summary', {}).get('complexity_score', 0)
        
        # Calculate migration effort
        if complexity_score <= 10:
            migration_effort = "LOW"
            estimated_hours = 4.0
            risk_level = "LOW"
        elif complexity_score <= 25:
            migration_effort = "MEDIUM"
            estimated_hours = 12.0
            risk_level = "MEDIUM"
        else:
            migration_effort = "HIGH"
            estimated_hours = 24.0
            risk_level = "HIGH"
        
        # Analyze risk factors
        risk_factors = []
        resources = facts.get('resources', {})
        dependencies = facts.get('dependencies', {})
        
        if len(dependencies.get('include_recipes', [])) > 2:
            risk_factors.append("Wrapper cookbook with multiple dependencies")
        
        if len(resources.get('templates', [])) > 5:
            risk_factors.append("High template complexity")
            
        if len(resources.get('services', [])) > 3:
            risk_factors.append("Multiple service dependencies")
            
        if complexity_score > 30:
            risk_factors.append("Very high overall complexity")
        
        # Determine migration priority
        if migration_effort == "HIGH" or len(risk_factors) > 2:
            migration_priority = "HIGH"
        elif migration_effort == "MEDIUM" or len(risk_factors) > 0:
            migration_priority = "MEDIUM"
        else:
            migration_priority = "LOW"
        
        result = {
            "complexity_score": complexity_score,
            "migration_effort": migration_effort,
            "estimated_hours": estimated_hours,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "migration_priority": migration_priority,
            "total_resources": facts.get('summary', {}).get('total_resources', 0),
            "is_wrapper": facts.get('summary', {}).get('is_wrapper', False),
            "syntax_success_rate": facts.get('summary', {}).get('syntax_success_rate', 0)
        }
        
        logger.info(f"[{correlation_id}] Complexity analysis completed: score={complexity_score}, effort={migration_effort}")
        return result
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Complexity analysis failed: {e}")
        return _create_error_complexity_result()

def _create_error_complexity_result() -> Dict[str, Any]:
    """Create error result when complexity analysis fails."""
    return {
        "complexity_score": 0,
        "migration_effort": "UNKNOWN",
        "estimated_hours": 0.0,
        "risk_level": "UNKNOWN",
        "risk_factors": ["Analysis failed"],
        "migration_priority": "UNKNOWN",
        "total_resources": 0,
        "is_wrapper": False,
        "syntax_success_rate": 0
    }