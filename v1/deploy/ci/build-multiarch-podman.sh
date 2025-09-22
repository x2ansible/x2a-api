#!/bin/bash
# ============================================================================
# V1 Agents - Multi-Architecture Container Build Script (Podman Native)
# ============================================================================
# Builds for both ARM64 (Apple Silicon) and AMD64 (Intel) using Podman

set -e

echo "🚀 V1 Agents - Multi-Architecture Container Build (Podman)"
echo "=========================================================="

# Configuration
IMAGE_NAME="x2a-v1-agents"
IMAGE_TAG="${1:-latest}"
REGISTRY="${2:-localhost}"
BUILD_TYPE="${3:-quick}"  # quick or full

echo "📋 Build Configuration:"
echo "   Image: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "   Platforms: linux/amd64, linux/arm64"
echo "   Build Type: ${BUILD_TYPE}"

# ============================================================================
# DETERMINE CONTAINERFILE
# ============================================================================

if [ "$BUILD_TYPE" = "full" ]; then
    CONTAINERFILE="Containerfile"
    echo "🏗️ Using full production Containerfile (with comprehensive testing)"
else
    CONTAINERFILE="Containerfile.working"
    echo "⚡ Using working Containerfile (basic validation only)"
fi

# ============================================================================
# BUILD FOR EACH ARCHITECTURE
# ============================================================================

echo "🏗️ Building for multiple architectures..."

# Build for ARM64 (Apple Silicon)
echo "🔨 Building for linux/arm64..."
podman build \
    --platform linux/arm64 \
    --tag ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-arm64 \
    --file ${CONTAINERFILE} \
    .

if [ $? -eq 0 ]; then
    echo " Successfully built for linux/arm64"
else
    echo " Build failed for linux/arm64"
    exit 1
fi

# Build for AMD64 (Intel)
echo "🔨 Building for linux/amd64..."
podman build \
    --platform linux/amd64 \
    --tag ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-amd64 \
    --file ${CONTAINERFILE} \
    .

if [ $? -eq 0 ]; then
    echo " Successfully built for linux/amd64"
else
    echo " Build failed for linux/amd64"
    exit 1
fi

# ============================================================================
# CREATE MULTI-ARCH MANIFEST
# ============================================================================

echo "📋 Creating multi-architecture manifest..."

# Remove existing manifest if it exists
podman manifest rm ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} 2>/dev/null || true

# Create new manifest
podman manifest create ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

# Add both architectures to the manifest
podman manifest add ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-arm64
podman manifest add ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-amd64

echo " Multi-architecture manifest created successfully"

# ============================================================================
# VERIFICATION & TESTING
# ============================================================================

echo "🔍 Verifying multi-arch build..."

# Show manifest details
echo "📋 Manifest details:"
podman manifest inspect ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} | head -20

# Detect current architecture for testing
CURRENT_ARCH=$(uname -m)
if [ "$CURRENT_ARCH" = "arm64" ]; then
    TEST_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-arm64"
    PLATFORM_NAME="ARM64 (Apple Silicon)"
elif [ "$CURRENT_ARCH" = "x86_64" ]; then
    TEST_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-amd64"
    PLATFORM_NAME="AMD64 (Intel)"
else
    echo "⚠️ Unknown architecture: $CURRENT_ARCH, using ARM64 for testing"
    TEST_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-arm64"
    PLATFORM_NAME="Unknown"
fi

echo "🧪 Testing ${PLATFORM_NAME} image..."

# Quick test run
CONTAINER_NAME="x2a-multiarch-test"

# Cleanup existing test container
podman stop ${CONTAINER_NAME} 2>/dev/null || true
podman rm ${CONTAINER_NAME} 2>/dev/null || true

# Run test container for basic validation
echo "🚀 Starting test container..."
podman run -d \
    --name ${CONTAINER_NAME} \
    -p 2024:2024 \
    -e LLM_BASE_URL="https://lss-lss.apps.prod.rhoai.rh-aiservices-bu.com/v1/openai/v1" \
    -e LLM_MODEL="llama-4-scout-17b-16e-w4a16" \
    -e LLM_API_KEY="dummy-key" \
    ${TEST_IMAGE}

echo "⏳ Waiting for container to start..."
sleep 15

# Check if container is running
if podman ps | grep -q ${CONTAINER_NAME}; then
    echo " Container started successfully on ${PLATFORM_NAME}"
    
    # Check if LangGraph server is starting
    echo "📋 Container logs:"
    podman logs ${CONTAINER_NAME} | tail -15
    
    # Basic connectivity test
    sleep 5
    if curl -f -s http://localhost:2024 >/dev/null 2>&1; then
        echo " API responding on port 2024"
    elif curl -f -s http://localhost:2024/docs >/dev/null 2>&1; then
        echo " API docs responding on port 2024"
    else
        echo "⚠️ API not responding yet (may need more time to start)"
    fi
else
    echo " Container failed to start"
    echo "📋 Container logs:"
    podman logs ${CONTAINER_NAME}
fi

# Cleanup test container
echo "🧹 Cleaning up test container..."
podman stop ${CONTAINER_NAME} 2>/dev/null || true
podman rm ${CONTAINER_NAME} 2>/dev/null || true

# ============================================================================
# RESULTS & USAGE
# ============================================================================

echo ""
echo "🎯 Multi-Architecture Build Results"
echo "==================================="
echo " Built for: linux/amd64, linux/arm64"
echo " Manifest created: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo " Native architecture tested: ${PLATFORM_NAME}"
echo ""

echo "📋 Available images:"
podman images | grep ${IMAGE_NAME} | head -5

echo ""
echo "🚀 Usage Examples:"
echo "   # Run on current architecture (auto-select):"
echo "   podman run -p 2024:2024 ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "   # Run specific architecture:"
echo "   podman run --platform linux/amd64 -p 2024:2024 ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "   podman run --platform linux/arm64 -p 2024:2024 ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "   # Test API endpoints:"
echo "   curl http://localhost:2024/docs"
echo "   curl -X POST http://localhost:2024/infrastructure_analysis/invoke -H 'Content-Type: application/json' -d '{\"test\": true}'"
echo ""

echo "📦 Container Management:"
echo "   # Push to registry:"
echo "   podman manifest push ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "   # Remove images:"
echo "   podman rmi ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}*"
echo "   podman manifest rm ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""

echo "🎉 Multi-architecture build complete!"

# Show final status
if podman manifest inspect ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} >/dev/null 2>&1; then
    echo " Multi-arch manifest ready for deployment"
    exit 0
else
    echo " Multi-arch manifest creation failed"
    exit 1
fi
