"""
Code Generation Agent Workflow Nodes

AlphaCodium pattern nodes for infrastructure-to-Ansible conversion.
All nodes organized in a single file for maintainability.
"""

import re
import yaml
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from typing import Any as BaseStore
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from code_gen.state import (
    CodeGenState, 
    get_user_id_from_config, 
    should_reflect, 
    should_continue_iteration,
    log_generation_attempt,
    save_successful_generation
)
from code_gen.utils import get_llm

# ============================================================================
# CONFIG LOADING UTILITIES
# ============================================================================

def _load_config_sync():
    """Load configuration from v1/config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_prompts():
    """Get configured prompts for code_gen agent"""
    config = _load_config_sync()
    return config.get('prompts', {}).get('code_gen', {})

def get_prompt(prompt_name: str, default: str = "") -> str:
    """Get a specific code_gen prompt by name with fallback to default"""
    prompts = get_prompts()
    return prompts.get(prompt_name, default)

# ============================================================================
# DATA MODELS
# ============================================================================

class AnsibleCode(BaseModel):
    """Generated Ansible code with metadata"""
    description: str = Field(description="Description of what the Ansible code does")
    ansible_code: str = Field(description="Complete Ansible playbook or tasks")
    modules_used: list[str] = Field(description="Ansible modules used")
    best_practices_applied: list[str] = Field(description="Best practices incorporated")
    explanation: str = Field(description="Explanation of the conversion choices made")


# ============================================================================
# GLOBAL COMPONENTS
# ============================================================================

# Initialize LLM
llm = get_llm()


# ============================================================================
# EMBEDDED PLATFORM DETECTION (NO HTTP CALLS)
# ============================================================================

def _embedded_platform_detector(files: Dict[str, str]) -> Dict[str, Any]:
    """
    Embedded platform detection using same logic as infrastructure_analysis.
    No HTTP calls - pure function based on file content analysis.
    """
    if not files:
        return {
            "detected_platforms": [],
            "primary_platform": None,
            "confidence_scores": {},
            "evidence": {},
            "mixed_platform": False
        }
    
    # Platform detection scores
    platform_scores = {
        "chef": 0.0,
        "puppet": 0.0,
        "terraform": 0.0,
        "bladelogic": 0.0
    }
    
    evidence = {
        "chef": [],
        "puppet": [],
        "terraform": [],
        "bladelogic": []
    }
    
    # Analyze each file
    for filename, content in files.items():
        chef_score, chef_evidence = _detect_chef_patterns(filename, content)
        puppet_score, puppet_evidence = _detect_puppet_patterns(filename, content)
        terraform_score, terraform_evidence = _detect_terraform_patterns(filename, content)
        bladelogic_score, bladelogic_evidence = _detect_bladelogic_patterns(filename, content)
        
        platform_scores["chef"] += chef_score
        platform_scores["puppet"] += puppet_score
        platform_scores["terraform"] += terraform_score
        platform_scores["bladelogic"] += bladelogic_score
        
        evidence["chef"].extend(chef_evidence)
        evidence["puppet"].extend(puppet_evidence)
        evidence["terraform"].extend(terraform_evidence)
        evidence["bladelogic"].extend(bladelogic_evidence)
    
    # Normalize scores by file count
    file_count = len(files)
    normalized_scores = {k: v/file_count for k, v in platform_scores.items()}
    
    # Determine primary platform
    primary_platform = max(normalized_scores, key=normalized_scores.get)
    primary_confidence = normalized_scores[primary_platform]
    
    # Detect significant platforms (confidence > 0.1)
    significant_platforms = [p for p, score in normalized_scores.items() if score > 0.1]
    mixed_platform = len(significant_platforms) > 1
    
    return {
        "detected_platforms": significant_platforms,
        "primary_platform": primary_platform if primary_confidence > 0.1 else None,
        "confidence_scores": normalized_scores,
        "evidence": evidence,
        "mixed_platform": mixed_platform,
        "file_count": file_count
    }

def _detect_chef_patterns(filename: str, content: str) -> tuple[float, list[str]]:
    """Detect Chef cookbook patterns - embedded version"""
    score = 0.0
    evidence = []
    
    # File name patterns
    if filename == "metadata.rb":
        score += 1.0
        evidence.append("metadata.rb file found")
    elif filename.endswith(".rb") and ("recipes/" in filename or "recipe" in filename.lower()):
        score += 0.7
        evidence.append(f"Recipe file: {filename}")
    elif filename.endswith(".erb"):
        score += 0.5
        evidence.append(f"ERB template: {filename}")
    
    # Content patterns
    if "include_recipe" in content:
        score += 0.3
        evidence.append("include_recipe calls found")
    if re.search(r'\b(?:package|service|template|file|directory)\s+[\'"]', content):
        score += 0.4
        evidence.append("Chef resource declarations found")
    if "node[" in content:
        score += 0.3
        evidence.append("Node attribute access found")
    if "action :" in content:
        score += 0.3
        evidence.append("Chef action syntax found")
        
    return score, evidence

def _detect_puppet_patterns(filename: str, content: str) -> tuple[float, list[str]]:
    """Detect Puppet manifest patterns - embedded version"""
    score = 0.0
    evidence = []
    
    # File patterns
    if filename.endswith(".pp"):
        score += 0.8
        evidence.append(f"Puppet manifest: {filename}")
    elif filename == "metadata.json":
        score += 0.3
        evidence.append("metadata.json found")
        
    # Content patterns
    if re.search(r'class\s+\w+', content):
        score += 0.4
        evidence.append("Puppet class definitions found")
    if "ensure =>" in content:
        score += 0.4
        evidence.append("Puppet ensure syntax found")
    if re.search(r'\b(?:package|service|file|exec)\s*\{', content):
        score += 0.3
        evidence.append("Puppet resource declarations found")
        
    return score, evidence

def _detect_terraform_patterns(filename: str, content: str) -> tuple[float, list[str]]:
    """Detect Terraform configuration patterns - embedded version"""  
    score = 0.0
    evidence = []
    
    # File patterns
    if filename.endswith(".tf"):
        score += 0.9
        evidence.append(f"Terraform file: {filename}")
    elif filename.endswith(".hcl"):
        score += 0.5
        evidence.append(f"HCL file: {filename}")
        
    # Content patterns
    if "resource \"" in content:
        score += 0.5
        evidence.append("Terraform resource blocks found")
    if "provider \"" in content:
        score += 0.4
        evidence.append("Terraform provider configuration found")
    if "variable \"" in content or "locals {" in content:
        score += 0.3
        evidence.append("Terraform variables/locals found")
        
    return score, evidence

def _detect_bladelogic_patterns(filename: str, content: str) -> tuple[float, list[str]]:
    """Detect BladeLogic script patterns - embedded version"""
    score = 0.0
    evidence = []
    
    # File patterns
    if filename.endswith(".nsh"):
        score += 0.7
        evidence.append(f"NSH script: {filename}")
    elif filename.endswith(".blcli"):
        score += 0.8
        evidence.append(f"BladeLogic CLI script: {filename}")
        
    # Content patterns
    if "blcli" in content.lower():
        score += 0.5
        evidence.append("BladeLogic CLI commands found")
    if "nexec" in content or "ncp" in content:
        score += 0.3
        evidence.append("NSH commands found")
        
    return score, evidence


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

# Create generation prompt templates
ansible_generation_prompt = ChatPromptTemplate.from_messages([
    ("system", get_prompt('ansible_generation_system')),
    ("user", "Convert this {source_platform} infrastructure code to Ansible:\n\n{source_code}")
])

reflection_prompt = ChatPromptTemplate.from_messages([
    ("system", get_prompt('reflection_system')),
    ("user", "Analyze the errors and provide reflections to improve the next code generation attempt.")
])

# Create structured chains
ansible_generator = ansible_generation_prompt | llm.with_structured_output(AnsibleCode)
reflector = reflection_prompt | llm


# ============================================================================
# VALIDATION TOOLS FOR REACT AGENT
# ============================================================================

@tool
def validate_yaml_syntax(ansible_code: str) -> str:
    """Validate YAML syntax of Ansible code"""
    try:
        # Try parsing as YAML
        yaml.safe_load(ansible_code)
        return "YAML syntax is valid"
    except yaml.YAMLError as e:
        return f"YAML syntax error: {str(e)}"


@tool  
def validate_ansible_modules(ansible_code: str) -> str:
    """Check if Ansible modules used are valid and properly formatted"""
    common_modules = {
        'package', 'service', 'copy', 'template', 'file', 'lineinfile',
        'user', 'group', 'command', 'shell', 'script', 'cron', 'mount',
        'systemd', 'firewalld', 'iptables', 'yum', 'apt', 'pip', 'git'
    }
    
    found_modules = []
    potential_issues = []
    
    # Extract module names from tasks
    import re
    lines = ansible_code.split('\n')
    for line in lines:
        # Look for module usage patterns
        for module in common_modules:
            if re.search(rf'\b{module}:', line.strip()):
                found_modules.append(module)
        
        # Check for potential issues
        if ':' in line and 'name:' not in line and '---' not in line:
            module_name = line.split(':')[0].strip().split()[-1]
            if module_name and module_name not in common_modules and len(module_name) > 2:
                potential_issues.append(f"Unknown or potentially invalid module: {module_name}")
    
    result = f"Found modules: {', '.join(set(found_modules))}"
    if potential_issues:
        result += f"\nModule validation issues: {'; '.join(potential_issues)}"
    
    return result


@tool
def validate_ansible_structure(ansible_code: str) -> str:
    """Validate Ansible playbook structure and syntax"""
    issues = []
    
    if not ansible_code.strip().startswith('---'):
        issues.append("Missing YAML document separator (---)")
    
    required_playbook_keys = ['name', 'hosts']
    for key in required_playbook_keys:
        if f'{key}:' not in ansible_code:
            issues.append(f"Missing required playbook key: {key}")
    
    if 'tasks:' not in ansible_code:
        issues.append("No tasks section found")
    
    if not issues:
        return "Ansible structure appears valid"
    else:
        return f"Structure issues: {'; '.join(issues)}"


def create_validation_react_agent():
    """Create validation ReAct agent with Ansible validation tools"""
    tools = [validate_yaml_syntax, validate_ansible_modules, validate_ansible_structure]
    
    # Create ReAct agent with simple tools - no custom prompt for now
    return create_react_agent(llm, tools)


# ============================================================================
# WORKFLOW NODES
# ============================================================================

def extract_source_code_from_messages(state: CodeGenState, config: RunnableConfig = None, *, store: BaseStore = None) -> CodeGenState:
    """Extract infrastructure code from chat messages and load user context"""
    print("📝 Extracting infrastructure code from messages...")
    
    messages = state.get("messages", [])
    source_code = ""
    
    # Get user_id from config for memory namespacing
    user_id = get_user_id_from_config(config)
    
    # Find the most recent human message with code
    for message in reversed(messages):
        if hasattr(message, 'content') and message.content:
            content = message.content
            
            # Look for code blocks or code-like content
            if any(keyword in content.lower() for keyword in ["cookbook", "recipe", "chef", "puppet", "terraform", "bladelogic"]):
                source_code = content
                break
            
            # Look for code blocks (markdown format)
            code_match = re.search(r'```[\w]*\n(.*?)\n```', content, re.DOTALL)
            if code_match:
                source_code = code_match.group(1)
                break
    
    if not source_code and messages:
        # Fallback: use the last human message
        source_code = messages[-1].content if messages[-1].content else ""
    
    print(f"📄 Extracted source code: {len(source_code)} characters")
    
    # Log extraction to memory if available
    if store:
        try:
            extraction_namespace = (user_id, "code_extractions")
            extraction_log = {
                "source_code_length": len(source_code),
                "timestamp": datetime.now().isoformat(),
                "has_code": bool(source_code)
            }
            store.put(extraction_namespace, str(uuid.uuid4()), extraction_log)
        except Exception as e:
            print(f"⚠️ Memory logging error: {e}")
    
    return {
        **state,
        "source_code": source_code,
        "source_platform": "unknown",  # Will be detected in analysis
        "iterations": 0,
        "error": "",
        "ansible_code": "",
        "best_practices": "",
        "infrastructure_specification": "",
        "infrastructure_analysis": "",
        "validation_results": {},
        "reflections": ""
    }


async def analyze_infrastructure_code(state: CodeGenState, config: RunnableConfig = None, *, store: BaseStore = None) -> CodeGenState:
    """HYBRID: Call infrastructure analysis agent directly (no HTTP)"""
    print("🔍 Analyzing infrastructure code via direct graph call...")
    
    # Handle both dict and CodeGenState objects
    source_code = state.get('source_code', '') if isinstance(state, dict) else state.source_code
    if not source_code:
        return {**state, "error": "No source code provided for analysis"}
    
    try:
        # Import and call infrastructure analysis orchestrator-worker system
        from infrastructure_analysis.graph import create_infrastructure_analysis_graph
        import os
        
        # Set config path environment variable for infrastructure analysis agent
        config_path = str(Path(__file__).parent.parent / "config.yaml")
        os.environ['CONFIG_PATH'] = config_path
        
        # Create the infrastructure analysis graph
        infra_graph = create_infrastructure_analysis_graph()
        
        # Prepare input in the correct format (messages + input_code)
        from langchain_core.messages import HumanMessage
        infra_input = {
            'messages': [HumanMessage(content=source_code)],
            'input_code': source_code
        }
        
        print(f"📤 Calling infrastructure analysis with {len(source_code)} chars of code...")
        
        # Call the infrastructure analysis agent directly (no HTTP!)
        result = await infra_graph.ainvoke(infra_input)
        
        print(f" Infrastructure analysis completed successfully!")
        
        # Extract platform detection from Universal Extractor worker results (most accurate)
        detected_platforms = []
        platform = "unknown"
        confidence = 0.0
        
        worker_results = result.get("worker_results", [])
        for worker_result in worker_results:
            # Look for Universal Extractor results
            if hasattr(worker_result, 'worker_type') and worker_result.worker_type == "universal_extractor":
                if hasattr(worker_result, 'extracted_facts') and worker_result.extracted_facts:
                    facts = worker_result.extracted_facts
                    if 'detected_platforms' in facts:
                        detected_platforms = facts['detected_platforms']
                        # Filter out generic platforms and prioritize specific ones
                        priority_platforms = ['chef', 'terraform', 'puppet', 'salt', 'bladelogic']
                        for priority_platform in priority_platforms:
                            if priority_platform in detected_platforms:
                                platform = priority_platform
                                break
                        if platform == "unknown" and detected_platforms:
                            platform = detected_platforms[0]  # Use first detected if no priority match
                    
                    confidence = getattr(worker_result, 'confidence', 0.8)  # Universal extractor typically has high confidence
                    break
        
        # Fallback to orchestrator decision if no universal extractor results
        if platform == "unknown":
            orchestrator_decision = result.get("orchestrator_decision", {})
            if hasattr(orchestrator_decision, 'detected_platforms'):
                detected_platforms = orchestrator_decision.detected_platforms
                platform = detected_platforms[0] if detected_platforms else "unknown"
                confidence = getattr(orchestrator_decision, 'confidence', 0.0)
        
        # Extract comprehensive analysis from final_analysis
        final_analysis = result.get("final_analysis", "")
        if not final_analysis:
            final_analysis = f"Platform: {platform}\nConfidence: {confidence:.2f}\nSource Code Size: {len(source_code)} characters"
        
        # Extract specification from synthesized results or worker results
        specification = ""
        synthesized_results = result.get("synthesized_results", {})
        
        if synthesized_results:
            # Try to get specification from synthesis
            specification = synthesized_results.get("natural_specification", "")
            if not specification:
                specification = synthesized_results.get("unified_analysis", "")
        
        # Fallback to worker results if no synthesized specification
        if not specification:
            worker_results = result.get("worker_results", [])
            for worker_result in worker_results:
                if hasattr(worker_result, 'natural_spec') and worker_result.natural_spec:
                    specification = worker_result.natural_spec
                    break
        
        # Final fallback specification
        if not specification:
            specification = f'''Infrastructure Specification for {platform} to Ansible Migration:

Platform: {platform}
Source Code Size: {len(source_code)} characters
Detected Platforms: {', '.join(detected_platforms)}
Confidence: {confidence:.2f}

Migration Requirements:
- Convert {platform} syntax to Ansible YAML format
- Ensure idempotency and proper error handling  
- Maintain all functionality from source code
- Follow Ansible best practices and conventions

Acceptance Criteria:
- Valid YAML syntax with proper structure
- Executable Ansible playbook/tasks
- Equivalent functionality to source {platform} code
- Passes ansible-lint validation checks'''

        print(f"🎯 Detected platform: {platform} (confidence: {confidence:.2f})")
        print(f"📊 Analysis length: {len(final_analysis)} chars")
        print(f"📋 Specification length: {len(specification)} chars")
        
        return {
            **state,
            "source_platform": platform,
            "infrastructure_analysis": final_analysis,
            "infrastructure_specification": specification
        }
        
    except Exception as e:
        print(f"⚠️ Direct infrastructure analysis failed: {e}")
        # Fallback to simple pattern matching
        platform = "chef" if "package" in source_code and "action" in source_code else "unknown"
        return {
            **state,
            "source_platform": platform,
            "infrastructure_analysis": f"Fallback analysis: Detected {platform} code ({len(source_code)} chars)",
            "infrastructure_specification": f"Basic infrastructure specification for {platform} to Ansible conversion"
        }


def get_best_practices(state: CodeGenState, config: RunnableConfig = None, *, store: BaseStore = None) -> CodeGenState:
    """HYBRID: Call context agent directly for real best practices (no HTTP)"""
    print("📚 Getting best practices via direct graph call...")
    
    # Handle both dict and CodeGenState objects
    platform = state.get('source_platform', 'unknown') if isinstance(state, dict) else state.source_platform
    analysis = state.get('infrastructure_analysis', '') if isinstance(state, dict) else state.infrastructure_analysis
    
    try:
        # Import and call context agent directly
        from context_agent.graph import create_context_agent_graph
        
        # Create the graph
        context_graph = create_context_agent_graph()
        
        # Prepare targeted question for context agent
        if platform == "unknown":
            question = "What are general Ansible automation best practices for infrastructure migration and code conversion?"
        else:
            question = f"What are the best practices for migrating from {platform} to Ansible? I need specific guidance for converting {platform} infrastructure code to Ansible playbooks, including module choices, syntax conversion, and common pitfalls to avoid."
        
        # Prepare input in MessagesState format
        context_input = {
            "messages": [{"role": "human", "content": question}]
        }
        
        print(f"📤 Asking context agent about {platform} to Ansible best practices...")
        
        # Call the context agent directly (no HTTP!)
        result = context_graph.invoke(context_input)
        
        # Extract best practices from response
        practices = ""
        if result and isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            for message in messages:
                if isinstance(message, dict):
                    role = message.get("role", "")
                    content = message.get("content", "")
                else:
                    # LangChain message object
                    role = getattr(message, 'type', '')
                    content = getattr(message, 'content', str(message))
                
                if 'assistant' in str(role).lower() or 'ai' in str(role).lower():
                    practices = str(content)
                    break
        
        if not practices:
            practices = "Context Agent returned no best practices - using fallback"
            
        print(f" Retrieved best practices from context agent: {len(practices)} characters")
        
        return {**state, "best_practices": practices}
        
    except Exception as e:
        print(f"⚠️ Direct context agent call failed: {e}")
        # Fallback to curated best practices by platform
        if platform == "chef":
            practices = """Best practices for Chef to Ansible conversion:
- Use package module instead of package resource  
- Use service module for service management
- Convert Chef attributes to Ansible variables
- Use Ansible templates instead of ERB templates
- Convert Chef notifications to Ansible handlers
- Ensure idempotency in all tasks
- Structure playbooks with descriptive task names"""
        elif platform == "puppet":
            practices = """Best practices for Puppet to Ansible conversion:
- Convert ensure => present/absent to state: present/absent
- Use package and service modules for resource management
- Convert Puppet facts to Ansible variables
- Use Ansible templates instead of file resources with content
- Convert Puppet notify/subscribe to Ansible handlers"""
        else:
            practices = """General Ansible best practices:
- Use descriptive task names
- Ensure idempotency with appropriate modules
- Use variables and templates for configuration
- Follow standard directory structure conventions
- Add proper error handling and validation
- Use handlers for restart operations
- Include documentation and comments"""
        
        return {**state, "best_practices": practices}


def generate_ansible_code(state: CodeGenState, config: RunnableConfig = None, *, store: BaseStore = None) -> CodeGenState:
    """Generate Ansible code using LLM with all available context"""
    print("⚙️ Generating Ansible code...")
    
    # Handle both dict and CodeGenState objects
    current_iterations = state.get('iterations', 0) if isinstance(state, dict) else state.iterations
    iterations = current_iterations + 1
    
    # Log generation attempt
    user_id = get_user_id_from_config(config)
    if store:
        log_generation_attempt(store, user_id, state)
    
    try:
        # Get state values for generation
        best_practices = state.get('best_practices', '') if isinstance(state, dict) else state.best_practices
        reflections = state.get('reflections', '') if isinstance(state, dict) else state.reflections
        source_platform = state.get('source_platform', 'unknown') if isinstance(state, dict) else state.source_platform
        source_code = state.get('source_code', '') if isinstance(state, dict) else state.source_code
        infrastructure_analysis = state.get('infrastructure_analysis', '') if isinstance(state, dict) else state.infrastructure_analysis
        infrastructure_specification = state.get('infrastructure_specification', '') if isinstance(state, dict) else state.infrastructure_specification
        
        # Use reflections if available (AlphaCodium pattern)
        enhanced_practices = best_practices
        if reflections:
            enhanced_practices += f"\n\nReflections from previous attempt:\n{reflections}"
        
        result = ansible_generator.invoke({
            "source_platform": source_platform,
            "source_code": source_code,
            "infrastructure_analysis": infrastructure_analysis,
            "best_practices": enhanced_practices,
            "infrastructure_specification": infrastructure_specification
        })
        
        print(f" Generated Ansible code: {len(result.ansible_code)} characters")
        
        return {
            **state,
            "ansible_code": result.ansible_code,
            "iterations": iterations
        }
    
    except Exception as e:
        error_msg = f"Code generation failed: {str(e)}"
        print(f" {error_msg}")
        return {
            **state,
            "error": error_msg,
            "iterations": iterations
        }


def validate_code(state: CodeGenState, config: RunnableConfig = None, *, store: BaseStore = None) -> CodeGenState:
    """Validate generated Ansible code using ReAct agent"""
    print("🔍 Validating Ansible code...")
    
    # Handle both dict and CodeGenState objects
    ansible_code = state.get('ansible_code', '') if isinstance(state, dict) else state.ansible_code
    if not ansible_code:
        return {**state, "error": "No Ansible code to validate"}
    
    try:
        # Create validation ReAct agent
        validation_agent = create_validation_react_agent()
        
        # Get additional state values
        source_platform = state.get('source_platform', 'unknown') if isinstance(state, dict) else state.source_platform
        iterations = state.get('iterations', 0) if isinstance(state, dict) else state.iterations
        
        # Prepare validation request
        validation_request = f"""Please validate this generated Ansible code thoroughly:

```yaml
{ansible_code}
```

Run all validation tools and provide a comprehensive validation report including:
- YAML syntax validation
- Ansible module verification
- Structure and safety checks
- Overall assessment and recommendations

Source platform: {source_platform}
Generation iteration: {iterations}"""
        
        # Run validation through ReAct agent
        validation_messages = [{"role": "user", "content": validation_request}]
        result = validation_agent.invoke({"messages": validation_messages})
        
        # Extract validation results
        validation_output = ""
        if result.get("messages"):
            for message in result["messages"]:
                if hasattr(message, 'content'):
                    validation_output += message.content + "\n"
        
        # Determine if validation passed - look for critical failures, not minor suggestions
        critical_failures = any(keyword in validation_output.lower() for keyword in 
                               ["syntax error", "invalid yaml", "critical error", "fatal", "cannot execute", 
                                "failed to parse", "major issue", "critical issue"])
        
        # Look for positive validation indicators
        positive_indicators = any(phrase in validation_output.lower() for phrase in
                                ["syntax is valid", "well-structured", "follows best practices", 
                                 "correctly used", "properly formatted", "structure is correct"])
        
        # Only fail if there are critical issues and no positive indicators
        has_errors = critical_failures and not positive_indicators
        
        validation_results = {
            "validation_output": validation_output,
            "has_errors": has_errors,
            "passed": not has_errors
        }
        
        if has_errors:
            print(" Validation failed: Found issues in generated code")
            return {
                **state,
                "validation_results": validation_results,
                "error": validation_request + "\n\n" + validation_output
            }
        else:
            print(" Validation passed: Code appears correct")
            return {
                **state,
                "validation_results": validation_results,
                "error": ""  # Clear any previous errors
            }
            
    except Exception as e:
        error_msg = f"Validation failed: {str(e)}"
        print(f" {error_msg}")
        return {**state, "error": error_msg}


def reflect_on_errors(state: CodeGenState, config: RunnableConfig = None, *, store: BaseStore = None) -> CodeGenState:
    """Reflect on errors using LLM analysis (AlphaCodium pattern)"""
    print("🤔 Reflecting on errors for next iteration...")
    
    # Handle both dict and CodeGenState objects
    error = state.get('error', '') if isinstance(state, dict) else getattr(state, 'error', '')
    if not error:
        return state  # No errors to reflect on
    
    # Get all state values safely
    source_platform = state.get('source_platform', 'unknown') if isinstance(state, dict) else getattr(state, 'source_platform', 'unknown')
    source_code = state.get('source_code', '') if isinstance(state, dict) else getattr(state, 'source_code', '')
    infrastructure_analysis = state.get('infrastructure_analysis', '') if isinstance(state, dict) else getattr(state, 'infrastructure_analysis', '')
    infrastructure_specification = state.get('infrastructure_specification', '') if isinstance(state, dict) else getattr(state, 'infrastructure_specification', '')
    ansible_code = state.get('ansible_code', '') if isinstance(state, dict) else getattr(state, 'ansible_code', '')
    
    try:
        reflection_result = reflector.invoke({
            "source_platform": source_platform,
            "source_code": source_code,
            "infrastructure_analysis": infrastructure_analysis,
            "infrastructure_specification": infrastructure_specification,
            "ansible_code": ansible_code,
            "validation_errors": error
        })
        
        reflections = reflection_result.content if hasattr(reflection_result, 'content') else str(reflection_result)
        
        print(f"💡 Generated reflections: {len(reflections)} characters")
        
        return {**state, "reflections": reflections}
        
    except Exception as e:
        error_msg = f"Reflection failed: {str(e)}"
        print(f" {error_msg}")
        # Continue without reflections
        return state


# ============================================================================
# ROUTING FUNCTIONS  
# ============================================================================

def should_reflect_on_errors(state: CodeGenState) -> str:
    """Determine if we should reflect on errors or retry directly"""
    # Handle both dict and CodeGenState objects
    use_reflection = state.get('use_reflection', True) if isinstance(state, dict) else getattr(state, 'use_reflection', True)
    error = state.get('error', '') if isinstance(state, dict) else getattr(state, 'error', '')
    iterations = state.get('iterations', 0) if isinstance(state, dict) else getattr(state, 'iterations', 0)
    max_iterations = state.get('max_iterations', 3) if isinstance(state, dict) else getattr(state, 'max_iterations', 3)
    
    if error and use_reflection and iterations < max_iterations:
        return "reflect"
    elif error and iterations < max_iterations:
        return "generate_ansible"  # Retry without reflection
    else:
        return "end"  # Max iterations reached or no error


def should_continue_generation(state: CodeGenState) -> str:
    """Determine if generation should continue or end"""
    # Handle both dict and CodeGenState objects
    error = state.get('error', '') if isinstance(state, dict) else getattr(state, 'error', '')
    iterations = state.get('iterations', 0) if isinstance(state, dict) else getattr(state, 'iterations', 0)
    max_iterations = state.get('max_iterations', 3) if isinstance(state, dict) else getattr(state, 'max_iterations', 3)
    
    if error and iterations < max_iterations:
        return "continue"  # Keep trying
    else:
        return "end"  # Success or max iterations reached