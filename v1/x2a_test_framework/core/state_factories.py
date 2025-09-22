"""
x2a State Factories

Enterprise-grade state management for x2a LangGraph agent testing.
Provides centralized, consistent state creation for all agent types in the x2a system.

Key Features:
- Type-safe state creation for all x2a agents
- Consistent state structure across test scenarios
- Platform-specific state variations
- Workflow state management for integration testing
- Validation of state structure and content
- Enterprise logging and debugging support

Supported Agent States:
- Code Gen: Code generation and conversion states
- Context Agent: RAG retrieval and context management states  
- Validation: Ansible-lint and validation states
- Orchestrator: Task planning and coordination states
- Universal Extractor: Platform detection and extraction states
- Structured Analyzer: Analysis and assessment states
- Spec Generator: Specification generation states
- Storage Manager: Neo4j storage operation states
- Synthesizer: Result synthesis and output states
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum

logger = logging.getLogger("x2a_test_framework.state_factories")


class X2AAgentType(Enum):
    """Enumeration of all x2a agent types across the entire v1 system."""
    
    # Primary x2a Agents
    CODE_GEN = "code_gen"
    CONTEXT_AGENT = "context_agent"
    VALIDATION = "validation"
    
    # Infrastructure Analysis Agents
    ORCHESTRATOR = "orchestrator"
    UNIVERSAL_EXTRACTOR = "universal_extractor"
    STRUCTURED_ANALYZER = "structured_analyzer"
    SPEC_GENERATOR = "spec_generator"
    STORAGE_MANAGER = "storage_manager"
    SYNTHESIZER = "synthesizer"


class X2APlatformType(Enum):
    """Enumeration of supported infrastructure platforms."""
    CHEF = "chef"
    TERRAFORM = "terraform"
    PUPPET = "puppet"
    SALT = "salt"
    BLADELOGIC = "bladelogic"
    UNKNOWN = "unknown"


class X2AComplexityLevel(Enum):
    """Enumeration of infrastructure complexity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StateValidationError(Exception):
    """Exception raised when state validation fails."""
    pass


class X2AStateBuilder:
    """
    Advanced state builder for creating validated x2a agent states.
    
    Provides fluent interface for building complex states with validation.
    """
    
    def __init__(self, agent_type: X2AAgentType):
        self.agent_type = agent_type
        self.state = {}
        self._validation_rules = []
        
    def with_input_code(self, code: str) -> 'X2AStateBuilder':
        """Add input code to the state."""
        self.state["input_code"] = code
        return self
    
    def with_platform(self, platform: X2APlatformType) -> 'X2AStateBuilder':
        """Add platform information to the state."""
        self.state["platform"] = platform.value
        return self
    
    def with_complexity(self, complexity: X2AComplexityLevel) -> 'X2AStateBuilder':
        """Add complexity level to the state."""
        self.state["complexity_level"] = complexity.value
        return self
    
    def with_messages(self, messages: List[Dict[str, Any]] = None) -> 'X2AStateBuilder':
        """Add messages to the state."""
        self.state["messages"] = messages or []
        return self
    
    def with_custom_field(self, key: str, value: Any) -> 'X2AStateBuilder':
        """Add custom field to the state."""
        self.state[key] = value
        return self
    
    def with_timestamp(self) -> 'X2AStateBuilder':
        """Add timestamp to the state."""
        self.state["x2a_test_timestamp"] = datetime.now().isoformat()
        return self
    
    def add_validation_rule(self, rule: callable) -> 'X2AStateBuilder':
        """Add validation rule for the state."""
        self._validation_rules.append(rule)
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build and validate the final state."""
        # Add agent-specific default fields
        self._add_agent_defaults()
        
        # Run validation rules
        self._validate_state()
        
        logger.debug(f"Built {self.agent_type.value} state with {len(self.state)} fields")
        return self.state.copy()
    
    def _add_agent_defaults(self):
        """Add default fields based on agent type."""
        base_defaults = {
            "error_messages": [],
            "x2a_agent_type": self.agent_type.value,
            "x2a_framework_version": "1.0.0"
        }
        
        # Add base defaults if not already present
        for key, value in base_defaults.items():
            if key not in self.state:
                self.state[key] = value
        
        # Add agent-specific defaults
        agent_defaults = {
            # Primary x2a Agents
            X2AAgentType.CODE_GEN: {
                "generated_code": "",
                "generation_status": "pending",
                "conversion_type": "chef_to_ansible",
                "generation_confidence": 0.0,
                "generation_errors": []
            },
            X2AAgentType.CONTEXT_AGENT: {
                "retrieved_context": [],
                "search_query": "",
                "context_relevance": 0.0,
                "retrieval_results": {},
                "knowledge_base": "default"
            },
            X2AAgentType.VALIDATION: {
                "validation_results": {},
                "validation_status": "pending",
                "validation_profile": "basic",
                "ansible_lint_results": [],
                "validation_errors": []
            },
            
            # Infrastructure Analysis Agents
            X2AAgentType.ORCHESTRATOR: {
                "orchestrator_decision": {},
                "worker_assignments": [],
                "orchestrator_confidence": 0.0,
                "orchestrator_reasoning": ""
            },
            X2AAgentType.UNIVERSAL_EXTRACTOR: {
                "extraction_results": {},
                "detected_platforms": [],
                "extraction_confidence": 0.0
            },
            X2AAgentType.STRUCTURED_ANALYZER: {
                "analysis_results": {},
                "analysis_confidence": 0.0,
                "analysis_depth": "standard"
            },
            X2AAgentType.SPEC_GENERATOR: {
                "specifications": {},
                "generation_status": "pending"
            },
            X2AAgentType.STORAGE_MANAGER: {
                "storage_results": {},
                "storage_status": "pending"
            },
            X2AAgentType.SYNTHESIZER: {
                "synthesis_results": {},
                "final_output": {},
                "synthesis_confidence": 0.0
            }
        }
        
        if self.agent_type in agent_defaults:
            for key, value in agent_defaults[self.agent_type].items():
                if key not in self.state:
                    self.state[key] = value
    
    def _validate_state(self):
        """Validate the built state."""
        # Run custom validation rules
        for rule in self._validation_rules:
            try:
                rule(self.state)
            except Exception as e:
                raise StateValidationError(f"State validation failed: {str(e)}")
        
        # Basic validation
        if "input_code" in self.state and self.state["input_code"] is not None:
            if not isinstance(self.state["input_code"], str):
                raise StateValidationError("input_code must be a string")


class StateFactory:
    """
    Enterprise-grade factory for creating test states for all x2a agents.
    
    Provides consistent, validated state creation with enterprise-level
    configuration management and validation.
    """
    
    @staticmethod
    def create_base_state(
        input_code: str = None,
        include_messages: bool = True,
        include_errors: bool = True,
        custom_fields: Dict[str, Any] = None,
        agent_type: X2AAgentType = None
    ) -> Dict[str, Any]:
        """
        Create a base state that works for most x2a agents.
        
        Args:
            input_code: The infrastructure code to analyze
            include_messages: Whether to include messages field
            include_errors: Whether to include error_messages field
            custom_fields: Additional fields to include
            agent_type: Specific agent type for enhanced defaults
            
        Returns:
            Dict representing a validated test state
        """
        default_code = '''
# x2a Test Infrastructure Code
# Default Chef cookbook for testing
cookbook_name = "x2a_test"

package "nginx" do
  action :install
end

service "nginx" do
  action [:enable, :start]
end
'''
        
        builder = X2AStateBuilder(agent_type or X2AAgentType.ORCHESTRATOR)
        builder.with_input_code(input_code or default_code)
        
        if include_messages:
            builder.with_messages([])
            
        if include_errors:
            builder.with_custom_field("error_messages", [])
        
        builder.with_timestamp()
        
        # Add custom fields
        if custom_fields:
            for key, value in custom_fields.items():
                builder.with_custom_field(key, value)
        
        return builder.build()
    
    @staticmethod
    def create_orchestrator_state(
        input_code: str = None,
        complexity: X2AComplexityLevel = X2AComplexityLevel.MEDIUM,
        include_workflow_context: bool = False
    ) -> Dict[str, Any]:
        """Create state specific to orchestrator agent testing."""
        builder = X2AStateBuilder(X2AAgentType.ORCHESTRATOR)
        builder.with_input_code(input_code)
        builder.with_complexity(complexity)
        builder.with_messages([])
        builder.with_timestamp()
        
        if include_workflow_context:
            builder.with_custom_field("workflow_id", f"x2a_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            builder.with_custom_field("workflow_stage", "orchestration")
        
        # Add validation for orchestrator-specific requirements
        def validate_orchestrator_state(state):
            required_fields = ["orchestrator_decision", "worker_assignments"]
            for field in required_fields:
                if field not in state:
                    raise StateValidationError(f"Orchestrator state missing required field: {field}")
        
        builder.add_validation_rule(validate_orchestrator_state)
        
        return builder.build()
    
    @staticmethod
    def create_code_gen_state(
        input_code: str = None,
        conversion_type: str = "chef_to_ansible",
        output_format: str = "yaml",
        include_context: bool = True
    ) -> Dict[str, Any]:
        """Create state for code generation agent testing."""
        builder = X2AStateBuilder(X2AAgentType.CODE_GEN)
        builder.with_input_code(input_code)
        builder.with_custom_field("conversion_type", conversion_type)
        builder.with_custom_field("output_format", output_format)
        builder.with_custom_field("include_context", include_context)
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add generation context if needed
        if include_context:
            builder.with_custom_field("generation_context", {
                "source_platform": "chef",
                "target_platform": "ansible",
                "migration_strategy": "direct_conversion"
            })
        
        return builder.build()
    
    @staticmethod
    def create_context_agent_state(
        search_query: str = None,
        knowledge_base: str = "default",
        max_results: int = 5,
        context_type: str = "migration_guidance"
    ) -> Dict[str, Any]:
        """Create state for context agent testing."""
        builder = X2AStateBuilder(X2AAgentType.CONTEXT_AGENT)
        builder.with_custom_field("search_query", search_query or "ansible best practices")
        builder.with_custom_field("knowledge_base", knowledge_base)
        builder.with_custom_field("max_results", max_results)
        builder.with_custom_field("context_type", context_type)
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add search parameters
        builder.with_custom_field("search_parameters", {
            "vector_search": True,
            "semantic_search": True,
            "similarity_threshold": 0.7
        })
        
        return builder.build()
    
    @staticmethod
    def create_validation_state(
        generated_code: str = None,
        validation_profile: str = "basic",
        include_ansible_lint: bool = True,
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        """Create state for validation agent testing."""
        builder = X2AStateBuilder(X2AAgentType.VALIDATION)
        builder.with_custom_field("generated_code", generated_code or "")
        builder.with_custom_field("validation_profile", validation_profile)
        builder.with_custom_field("include_ansible_lint", include_ansible_lint)
        builder.with_custom_field("timeout_seconds", timeout_seconds)
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add validation configuration
        builder.with_custom_field("validation_config", {
            "check_syntax": True,
            "check_best_practices": True,
            "check_security": validation_profile in ["moderate", "safety", "production"],
            "fail_on_warning": validation_profile == "production"
        })
        
        # Add validation for validation-specific requirements
        def validate_validation_state(state):
            if "validation_profile" not in state:
                raise StateValidationError("Validation state must include validation_profile")
            valid_profiles = ["basic", "moderate", "safety", "shared", "production"]
            if state["validation_profile"] not in valid_profiles:
                raise StateValidationError(f"Invalid validation profile: {state['validation_profile']}")
        
        builder.add_validation_rule(validate_validation_state)
        
        return builder.build()
    
    @staticmethod
    def create_universal_extractor_state(
        input_code: str = None,
        platform: X2APlatformType = X2APlatformType.CHEF,
        extraction_depth: str = "standard"
    ) -> Dict[str, Any]:
        """Create state for universal extractor agent testing."""
        builder = X2AStateBuilder(X2AAgentType.UNIVERSAL_EXTRACTOR)
        builder.with_input_code(input_code)
        builder.with_platform(platform)
        builder.with_custom_field("extraction_depth", extraction_depth)
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add validation for extractor-specific requirements
        def validate_extractor_state(state):
            if "platform" not in state:
                raise StateValidationError("Universal extractor state must include platform")
        
        builder.add_validation_rule(validate_extractor_state)
        
        return builder.build()
    
    @staticmethod
    def create_structured_analyzer_state(
        input_code: str = None,
        platform: X2APlatformType = X2APlatformType.CHEF,
        analysis_depth: str = "comprehensive",
        include_security_analysis: bool = True
    ) -> Dict[str, Any]:
        """Create state for structured analyzer agent testing."""
        builder = X2AStateBuilder(X2AAgentType.STRUCTURED_ANALYZER)
        builder.with_input_code(input_code)
        builder.with_platform(platform)
        builder.with_custom_field("analysis_depth", analysis_depth)
        builder.with_custom_field("include_security_analysis", include_security_analysis)
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add extracted facts if needed for realistic testing
        builder.with_custom_field("extracted_facts", {
            "platform": platform.value,
            "resources": [],
            "dependencies": [],
            "configurations": {}
        })
        
        return builder.build()
    
    @staticmethod
    def create_spec_generator_state(
        input_code: str = None,
        platform: X2APlatformType = X2APlatformType.CHEF,
        spec_format: str = "markdown",
        include_diagrams: bool = True
    ) -> Dict[str, Any]:
        """Create state for spec generator agent testing."""
        builder = X2AStateBuilder(X2AAgentType.SPEC_GENERATOR)
        builder.with_input_code(input_code)
        builder.with_platform(platform)
        builder.with_custom_field("spec_format", spec_format)
        builder.with_custom_field("include_diagrams", include_diagrams)
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add analysis results that spec generator would receive
        builder.with_custom_field("analysis_results", {
            "complexity_score": 7.5,
            "security_considerations": [],
            "migration_recommendations": []
        })
        
        return builder.build()
    
    @staticmethod
    def create_storage_manager_state(
        input_code: str = None,
        platform: X2APlatformType = X2APlatformType.CHEF,
        storage_operation: str = "store",
        neo4j_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create state for storage manager agent testing."""
        builder = X2AStateBuilder(X2AAgentType.STORAGE_MANAGER)
        builder.with_input_code(input_code)
        builder.with_platform(platform)
        builder.with_custom_field("storage_operation", storage_operation)
        builder.with_custom_field("neo4j_config", neo4j_config or {"test_mode": True})
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add data to store
        builder.with_custom_field("storage_data", {
            "analysis_id": f"x2a_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "facts": {},
            "analysis": {},
            "specifications": {}
        })
        
        return builder.build()
    
    @staticmethod
    def create_synthesizer_state(
        input_code: str = None,
        platform: X2APlatformType = X2APlatformType.CHEF,
        output_format: str = "comprehensive",
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """Create state for synthesizer agent testing."""
        builder = X2AStateBuilder(X2AAgentType.SYNTHESIZER)
        builder.with_input_code(input_code)
        builder.with_platform(platform)
        builder.with_custom_field("output_format", output_format)
        builder.with_custom_field("include_recommendations", include_recommendations)
        builder.with_messages([])
        builder.with_timestamp()
        
        # Add all the results that synthesizer would receive
        builder.with_custom_field("worker_results", [
            {
                "worker_type": "universal_extractor",
                "platform": platform.value,
                "results": {"extracted_facts": {}},
                "confidence": 0.9
            },
            {
                "worker_type": "structured_analyzer", 
                "platform": platform.value,
                "results": {"analysis": {}},
                "confidence": 0.85
            }
        ])
        
        return builder.build()


class WorkflowStateFactory:
    """
    Factory for creating workflow states for integration testing.
    
    Manages state transitions between agents in complete x2a workflows.
    """
    
    @staticmethod
    def create_workflow_initial_state(
        input_code: str,
        platform: X2APlatformType = X2APlatformType.CHEF,
        workflow_id: str = None
    ) -> Dict[str, Any]:
        """Create initial state for a complete x2a workflow."""
        workflow_id = workflow_id or f"x2a_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        builder = X2AStateBuilder(X2AAgentType.ORCHESTRATOR)
        builder.with_input_code(input_code)
        builder.with_platform(platform)
        builder.with_custom_field("workflow_id", workflow_id)
        builder.with_custom_field("workflow_stage", "initialization")
        builder.with_custom_field("workflow_history", [])
        builder.with_timestamp()
        
        return builder.build()
    
    @staticmethod
    def create_workflow_intermediate_state(
        previous_state: Dict[str, Any],
        current_agent: X2AAgentType,
        agent_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create intermediate state during workflow execution."""
        builder = X2AStateBuilder(current_agent)
        
        # Preserve workflow context
        for key, value in previous_state.items():
            builder.with_custom_field(key, value)
        
        # Update workflow stage and history
        builder.with_custom_field("workflow_stage", current_agent.value)
        
        workflow_history = previous_state.get("workflow_history", [])
        workflow_history.append({
            "agent": current_agent.value,
            "timestamp": datetime.now().isoformat(),
            "results_summary": len(str(agent_results))  # Simple summary
        })
        builder.with_custom_field("workflow_history", workflow_history)
        
        # Add agent results
        builder.with_custom_field(f"{current_agent.value}_results", agent_results)
        
        return builder.build()
    
    @staticmethod
    def validate_workflow_state_transition(
        from_state: Dict[str, Any],
        to_state: Dict[str, Any],
        expected_agent: X2AAgentType
    ) -> bool:
        """Validate that workflow state transition is valid."""
        try:
            # Check that workflow ID is preserved
            if from_state.get("workflow_id") != to_state.get("workflow_id"):
                logger.error("Workflow ID not preserved in state transition")
                return False
            
            # Check that agent type is correct
            if to_state.get("x2a_agent_type") != expected_agent.value:
                logger.error(f"Expected agent {expected_agent.value}, got {to_state.get('x2a_agent_type')}")
                return False
            
            # Check that workflow history is updated
            from_history = from_state.get("workflow_history", [])
            to_history = to_state.get("workflow_history", [])
            
            if len(to_history) <= len(from_history):
                logger.error("Workflow history not properly updated")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Workflow state validation failed: {str(e)}")
            return False
