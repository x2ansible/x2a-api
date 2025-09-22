#!/bin/bash
# ============================================================================
# V1 AI Agents - Container Entrypoint Script
# ============================================================================

set -e

echo "🚀 Starting X2A V1 AI Agents Container"
echo "========================================"

# Verify test success marker (either full tests or quick validation)
if [ -f "/app/TEST_SUCCESS_MARKER" ]; then
    echo " Full build-time tests passed successfully"
elif [ -f "/app/QUICK_TEST_SUCCESS" ]; then
    echo " Quick validation passed (test build)"
else
    echo " ERROR: No test validation markers found. Container will not start."
    exit 1
fi

# ============================================================================
# ENVIRONMENT VALIDATION
# ============================================================================

echo "🔍 Validating environment..."

# Check required directories
required_dirs=(
    "infrastructure_analysis"
    "validation" 
    "context_agent"
    "code_gen"
    "testing"
)

for dir in "${required_dirs[@]}"; do
    if [ ! -d "/app/$dir" ]; then
        echo " ERROR: Required directory missing: $dir"
        exit 1
    fi
done

echo " All required directories present"

# ============================================================================
# CONFIGURATION SETUP
# ============================================================================

echo "🔧 Setting up configuration..."

# Create default config if none exists
if [ ! -f "/app/config.yaml" ]; then
    echo "📝 Creating default configuration..."
    cat > /app/config.yaml << EOF
llm:
  base_url: "${LLM_BASE_URL:-https://lss-lss.apps.prod.rhoai.rh-aiservices-bu.com/v1/openai/v1}"
  model: "${LLM_MODEL:-llama-4-scout-17b-16e-w4a16}"
  api_key: "${LLM_API_KEY:-dummy-key}"
  temperature: ${LLM_TEMPERATURE:-0.1}
  max_tokens: ${LLM_MAX_TOKENS:-4000}

neo4j:
  uri: "${NEO4J_URI:-neo4j://localhost:7687}"
  username: "${NEO4J_USERNAME:-neo4j}"
  password: "${NEO4J_PASSWORD:-password}"
  database: "${NEO4J_DATABASE:-neo4j}"

agents:
  infrastructure_analysis:
    enabled: ${INFRASTRUCTURE_ANALYSIS_ENABLED:-true}
  validation:
    enabled: ${VALIDATION_AGENT_ENABLED:-true}
  context_agent:
    enabled: ${CONTEXT_AGENT_ENABLED:-true}
  code_generation:
    enabled: ${CODE_GENERATION_AGENT_ENABLED:-true}

server:
  host: "${LANGGRAPH_HOST:-0.0.0.0}"
  port: ${LANGGRAPH_PORT:-2024}
  debug: ${DEBUG:-false}
EOF
else
    echo " Using existing configuration"
fi

# ============================================================================
# HEALTH CHECK SETUP
# ============================================================================

echo "🏥 Setting up health check endpoint..."

# Create a simple health check script
cat > /app/health_check.py << 'EOF'
#!/usr/bin/env python3
import sys
import asyncio
from pathlib import Path

sys.path.append('/app')

async def health_check():
    """Simple health check for the agents"""
    try:
        # Import key agent components to verify they load
        from infrastructure_analysis.graph import app as infra_app
        from validation.graph import app as validation_app
        from context_agent.graph import app as context_app
        from code_gen.graph import app as codegen_app
        
        print(" All agents loaded successfully")
        return True
    except Exception as e:
        print(f" Health check failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(health_check())
    sys.exit(0 if result else 1)
EOF

chmod +x /app/health_check.py

# ============================================================================
# RUNTIME VALIDATION (Quick smoke test)
# ============================================================================

echo "🧪 Running runtime validation..."

# Quick import test
python3 -c "
import sys
sys.path.append('/app')

try:
    from infrastructure_analysis.graph import app as infra_app
    from validation.graph import app as validation_app  
    from context_agent.graph import app as context_app
    from code_gen.graph import app as codegen_app
    print(' All agents imported successfully')
except Exception as e:
    print(f' Agent import failed: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo " Runtime validation failed"
    exit 1
fi

echo " Runtime validation passed"

# ============================================================================
# LANGGRAPH SERVER SETUP
# ============================================================================

echo "🔧 Preparing LangGraph server..."

# Create LangGraph configuration if needed
if [ ! -f "/app/langgraph.json" ]; then
    echo "📝 Creating LangGraph configuration..."
    cat > /app/langgraph.json << EOF
{
  "graphs": {
    "infrastructure_analysis": {
      "path": "infrastructure_analysis.graph:app",
      "description": "Infrastructure analysis agent for Chef, Puppet, Terraform, etc."
    },
    "validation": {
      "path": "validation.graph:app", 
      "description": "Ansible validation agent with ansible-lint integration"
    },
    "context_agent": {
      "path": "context_agent.graph:app",
      "description": "Context agent with Neo4j RAG capabilities"
    },
    "code_generation": {
      "path": "code_gen.graph:app",
      "description": "Code generation agent for Chef-to-Ansible conversion"
    }
  },
  "server": {
    "host": "${LANGGRAPH_HOST:-0.0.0.0}",
    "port": ${LANGGRAPH_PORT:-2024}
  }
}
EOF
fi

# ============================================================================
# START AGENTS
# ============================================================================

echo "🚀 Starting LangGraph API server..."
echo "📡 Server will be available at: http://${LANGGRAPH_HOST:-0.0.0.0}:${LANGGRAPH_PORT:-2024}"
echo "🤖 Available agents:"
echo "   - Infrastructure Analysis: /infrastructure_analysis"
echo "   - Validation: /validation" 
echo "   - Context Agent: /context_agent"
echo "   - Code Generation: /code_generation"
echo ""
echo "🔄 Starting server..."

# Execute the command passed to the container
exec "$@"
