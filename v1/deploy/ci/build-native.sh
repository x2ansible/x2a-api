#!/bin/bash
# ============================================================================
# V1 Agents - Native Architecture Build (ARM64 for Mac)
# ============================================================================
# Quick build for current architecture only

set -e

echo "⚡ V1 Agents - Native Architecture Build"
echo "======================================="

# Configuration
IMAGE_NAME="x2a-v1-agents"
IMAGE_TAG="native-test"
CONTAINER_NAME="x2a-v1-native"
PORT="2024"

# Detect current architecture
CURRENT_ARCH=$(uname -m)
if [ "$CURRENT_ARCH" = "arm64" ]; then
    PLATFORM="linux/arm64"
    ARCH_NAME="ARM64 (Apple Silicon)"
elif [ "$CURRENT_ARCH" = "x86_64" ]; then
    PLATFORM="linux/amd64"
    ARCH_NAME="AMD64 (Intel)"
else
    echo "⚠️ Unknown architecture: $CURRENT_ARCH, defaulting to linux/arm64"
    PLATFORM="linux/arm64"
    ARCH_NAME="Unknown"
fi

echo "📋 Build Configuration:"
echo "   Architecture: ${ARCH_NAME}"
echo "   Platform: ${PLATFORM}"
echo "   Image: ${IMAGE_NAME}:${IMAGE_TAG}"

# ============================================================================
# BUILD PHASE
# ============================================================================

echo "🏗️ Building for native architecture..."

# Build using main Containerfile
podman build \
    --platform ${PLATFORM} \
    --tag ${IMAGE_NAME}:${IMAGE_TAG} \
    --file Containerfile \
    .

if [ $? -eq 0 ]; then
    echo " Native build successful for ${ARCH_NAME}"
else
    echo " Native build failed"
    exit 1
fi

# ============================================================================
# CLEANUP EXISTING CONTAINERS
# ============================================================================

echo "🧹 Cleaning up existing containers..."

if podman ps -a | grep -q ${CONTAINER_NAME}; then
    podman stop ${CONTAINER_NAME} 2>/dev/null || true
    podman rm ${CONTAINER_NAME} 2>/dev/null || true
fi

# ============================================================================
# TEST RUN
# ============================================================================

echo "🚀 Testing container..."

# Run the container
podman run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:${PORT} \
    -e LLM_BASE_URL="https://lss-lss.apps.prod.rhoai.rh-aiservices-bu.com/v1/openai/v1" \
    -e LLM_MODEL="llama-4-scout-17b-16e-w4a16" \
    -e LLM_API_KEY="dummy-key" \
    ${IMAGE_NAME}:${IMAGE_TAG}

echo "⏳ Waiting for container to start..."
sleep 15

# ============================================================================
# VALIDATION
# ============================================================================

echo "🔍 Validating container..."

# Check if container is running
if ! podman ps | grep -q ${CONTAINER_NAME}; then
    echo " Container is not running"
    echo "📋 Container logs:"
    podman logs ${CONTAINER_NAME}
    exit 1
fi

echo " Container is running"

# Check startup logs
echo "📋 Container startup logs:"
podman logs ${CONTAINER_NAME} | tail -15

# Basic connectivity test
echo "🔍 Testing API connectivity..."
sleep 5

if curl -f -s http://localhost:${PORT} >/dev/null 2>&1; then
    echo " API is responding on port ${PORT}"
elif curl -f -s http://localhost:${PORT}/docs >/dev/null 2>&1; then
    echo " API docs endpoint responding"
else
    echo "⚠️ API not responding yet, checking if LangGraph is starting..."
    
    # Check for LangGraph startup messages
    if podman logs ${CONTAINER_NAME} | grep -q "langgraph"; then
        echo " LangGraph server detected in logs"
    else
        echo "⚠️ LangGraph server may not have started"
    fi
fi

# ============================================================================
# RESULTS
# ============================================================================

echo ""
echo "🎯 Native Build Test Results"
echo "============================="
echo " Container built successfully for ${ARCH_NAME}"
echo " Container started and running"
echo "📡 API should be available at: http://localhost:${PORT}"
echo ""
echo "🔧 Next steps:"
echo "   1. Test API endpoints:"
echo "      curl http://localhost:${PORT}/docs"
echo "   2. Test specific agents:"
echo "      curl -X POST http://localhost:${PORT}/infrastructure_analysis/invoke -H 'Content-Type: application/json' -d '{\"test\": true}'"
echo "   3. View logs:"
echo "      podman logs ${CONTAINER_NAME}"
echo "   4. Access container:"
echo "      podman exec -it ${CONTAINER_NAME} /bin/bash"
echo ""
echo "🧹 Cleanup commands:"
echo "   podman stop ${CONTAINER_NAME}"
echo "   podman rm ${CONTAINER_NAME}"
echo "   podman rmi ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "🏗️ For multi-architecture build:"
echo "   ./build-multiarch.sh latest localhost quick"
echo ""
echo "🎉 Native build test complete!"
