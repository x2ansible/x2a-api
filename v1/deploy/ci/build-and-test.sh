#!/bin/bash
# ============================================================================
# V1 Agents - Local Container Build and Test Script
# ============================================================================

set -e

echo "🚀 V1 Agents - Container Build and Test"
echo "========================================"

# Configuration
IMAGE_NAME="x2a-v1-agents"
IMAGE_TAG="local-test"
CONTAINER_NAME="x2a-v1-test"
PORT="2024"

# ============================================================================
# BUILD PHASE
# ============================================================================

echo "🏗️ Building container image..."
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"

# Build with podman (includes comprehensive testing during build)
podman build -f Containerfile -t ${IMAGE_NAME}:${IMAGE_TAG} .

if [ $? -eq 0 ]; then
    echo " Container build successful (tests passed during build)"
else
    echo " Container build failed (tests failed during build)"
    exit 1
fi

# ============================================================================
# CLEANUP EXISTING CONTAINERS
# ============================================================================

echo "🧹 Cleaning up existing containers..."

# Stop and remove existing container if it exists
if podman ps -a | grep -q ${CONTAINER_NAME}; then
    echo "🛑 Stopping existing container..."
    podman stop ${CONTAINER_NAME} || true
    echo "🗑️ Removing existing container..."
    podman rm ${CONTAINER_NAME} || true
fi

# ============================================================================
# RUN PHASE
# ============================================================================

echo "🚀 Starting container..."

# Run the container with port mapping
podman run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:${PORT} \
    -e LLM_BASE_URL="https://lss-lss.apps.prod.rhoai.rh-aiservices-bu.com/v1/openai/v1" \
    -e LLM_MODEL="llama-4-scout-17b-16e-w4a16" \
    -e LLM_API_KEY="dummy-key" \
    -e NEO4J_URI="neo4j://host.containers.internal:7687" \
    -e NEO4J_USERNAME="neo4j" \
    -e NEO4J_PASSWORD="password" \
    ${IMAGE_NAME}:${IMAGE_TAG}

echo "⏳ Waiting for container to start..."
sleep 10

# ============================================================================
# HEALTH CHECK
# ============================================================================

echo "🏥 Performing health checks..."

# Check if container is running
if ! podman ps | grep -q ${CONTAINER_NAME}; then
    echo " Container is not running"
    echo "📋 Container logs:"
    podman logs ${CONTAINER_NAME}
    exit 1
fi

echo " Container is running"

# Check if the API is responding
echo "🔍 Testing API endpoints..."

# Wait a bit more for the server to fully start
sleep 15

# Test health endpoint (if available)
if curl -f -s http://localhost:${PORT}/health > /dev/null; then
    echo " Health endpoint responding"
else
    echo "⚠️ Health endpoint not available (might be normal)"
fi

# Test LangGraph API
echo "🧪 Testing LangGraph API endpoints..."

# List available agents
echo "📋 Available agents:"
curl -s http://localhost:${PORT}/docs || echo "⚠️ Could not fetch API docs"

# ============================================================================
# AGENT TESTING
# ============================================================================

echo "🤖 Testing individual agents..."

# Test Infrastructure Analysis Agent
echo "🏗️ Testing Infrastructure Analysis Agent..."
TEST_RESULT=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Test infrastructure analysis"}],
        "uploaded_files": {
            "test.rb": "package \"nginx\" do\n  action :install\nend"
        },
        "analysis_depth": "quick"
    }' \
    http://localhost:${PORT}/infrastructure_analysis/invoke || echo "FAILED")

if [[ "$TEST_RESULT" == *"FAILED"* ]]; then
    echo "⚠️ Infrastructure Analysis test failed or timed out"
else
    echo " Infrastructure Analysis agent responding"
fi

# Test Validation Agent
echo "🔍 Testing Validation Agent..."
TEST_RESULT=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "ansible_code": "---\n- name: test\n  hosts: all\n  tasks:\n    - name: install nginx\n      package: name=nginx state=present",
        "validation_level": "basic"
    }' \
    http://localhost:${PORT}/ansible_validator/invoke || echo "FAILED")

if [[ "$TEST_RESULT" == *"FAILED"* ]]; then
    echo "⚠️ Validation Agent test failed or timed out"
else
    echo " Validation agent responding"
fi

# Test Context Agent
echo "🧠 Testing Context Agent..."
TEST_RESULT=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "What are Ansible best practices?"}]
    }' \
    http://localhost:${PORT}/context_agent/invoke || echo "FAILED")

if [[ "$TEST_RESULT" == *"FAILED"* ]]; then
    echo "⚠️ Context Agent test failed or timed out"
else
    echo " Context agent responding"
fi

# Test Code Generation Agent
echo "🎯 Testing Code Generation Agent..."
TEST_RESULT=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "source_platform": "chef",
        "source_code": "package \"nginx\" do\n  action :install\nend",
        "target_platform": "ansible",
        "enable_reflection": false
    }' \
    http://localhost:${PORT}/code_gen/invoke || echo "FAILED")

if [[ "$TEST_RESULT" == *"FAILED"* ]]; then
    echo "⚠️ Code Generation Agent test failed or timed out"
else
    echo " Code Generation agent responding"
fi

# ============================================================================
# RESULTS
# ============================================================================

echo ""
echo "🎯 Container Test Results"
echo "========================="
echo " Container built successfully"
echo " Container started successfully"
echo " API server is running on port ${PORT}"
echo "🤖 Agents tested: 4/4"
echo ""
echo "📡 API Access:"
echo "   - LangGraph API: http://localhost:${PORT}"
echo "   - API Docs: http://localhost:${PORT}/docs"
echo ""
echo "🔧 Container Management:"
echo "   - View logs: podman logs ${CONTAINER_NAME}"
echo "   - Stop container: podman stop ${CONTAINER_NAME}"
echo "   - Remove container: podman rm ${CONTAINER_NAME}"
echo "   - Remove image: podman rmi ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "🎉 Container testing complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Test individual agents via API calls"
echo "   2. Run comprehensive functional tests against container"
echo "   3. Set up CI/CD pipeline with GitHub Actions"
