#!/bin/bash
# ============================================================================
# V1 Agents - Multi-Architecture Container Build Script
# ============================================================================
# Builds for both ARM64 (Apple Silicon) and AMD64 (Intel) architectures

set -e

echo "🚀 V1 Agents - Multi-Architecture Container Build"
echo "================================================="

# Configuration
IMAGE_NAME="x2a-v1-agents"
IMAGE_TAG="${1:-latest}"
REGISTRY="${2:-localhost}"
BUILD_TYPE="${3:-quick}"  # quick or full

# Target architectures
PLATFORMS="linux/amd64,linux/arm64"

echo "📋 Build Configuration:"
echo "   Image: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "   Platforms: ${PLATFORMS}"
echo "   Build Type: ${BUILD_TYPE}"

# ============================================================================
# DETERMINE CONTAINERFILE
# ============================================================================

if [ "$BUILD_TYPE" = "full" ]; then
    CONTAINERFILE="Containerfile"
    echo "🏗️ Using full production Containerfile (with comprehensive testing)"
else
    CONTAINERFILE="Containerfile.test"
    echo "⚡ Using quick test Containerfile (basic validation only)"
fi

# ============================================================================
# SETUP BUILDX BUILDER (if using docker)
# ============================================================================

if command -v docker &> /dev/null; then
    echo "🐳 Setting up Docker buildx for multi-arch..."
    
    # Create builder if it doesn't exist
    if ! docker buildx ls | grep -q "multiarch-builder"; then
        docker buildx create --name multiarch-builder --platform ${PLATFORMS}
    fi
    
    # Use the builder
    docker buildx use multiarch-builder
    
    # Bootstrap the builder
    docker buildx inspect --bootstrap
    
    BUILD_CMD="docker buildx build"
    BUILD_ARGS="--platform ${PLATFORMS} --push"
    
elif command -v podman &> /dev/null; then
    echo "🐳 Using Podman for multi-arch build..."
    
    # Check if we have buildah
    if ! command -v buildah &> /dev/null; then
        echo " Buildah not found. Installing..."
        brew install buildah || {
            echo " Please install buildah: brew install buildah"
            exit 1
        }
    fi
    
    BUILD_CMD="podman build"
    BUILD_ARGS="--platform ${PLATFORMS}"
    
else
    echo " Neither Docker nor Podman found. Please install one of them."
    exit 1
fi

# ============================================================================
# BUILD PHASE
# ============================================================================

echo "🏗️ Starting multi-architecture build..."

# Clean up any existing manifests
podman manifest rm ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} 2>/dev/null || true

# Build for each architecture
for ARCH in "linux/amd64" "linux/arm64"; do
    ARCH_TAG="${IMAGE_TAG}-$(echo $ARCH | tr '/' '-')"
    
    echo "🔨 Building for ${ARCH}..."
    
    if command -v docker &> /dev/null; then
        # Docker buildx approach
        docker buildx build \
            --platform ${ARCH} \
            --tag ${REGISTRY}/${IMAGE_NAME}:${ARCH_TAG} \
            --file ${CONTAINERFILE} \
            --load \
            .
    else
        # Podman approach
        podman build \
            --platform ${ARCH} \
            --tag ${REGISTRY}/${IMAGE_NAME}:${ARCH_TAG} \
            --file ${CONTAINERFILE} \
            .
    fi
    
    if [ $? -eq 0 ]; then
        echo " Successfully built for ${ARCH}"
    else
        echo " Build failed for ${ARCH}"
        exit 1
    fi
done

# ============================================================================
# CREATE MANIFEST
# ============================================================================

echo "📋 Creating multi-architecture manifest..."

# Create manifest
podman manifest create ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

# Add each architecture to the manifest
podman manifest add ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-linux-amd64
podman manifest add ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}-linux-arm64

echo " Multi-architecture manifest created"

# ============================================================================
# VERIFICATION
# ============================================================================

echo "🔍 Verifying multi-arch build..."

# Inspect the manifest
echo "📋 Manifest details:"
podman manifest inspect ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

# Test current architecture
CURRENT_ARCH=$(uname -m)
if [ "$CURRENT_ARCH" = "arm64" ]; then
    TEST_TAG="${IMAGE_TAG}-linux-arm64"
    PLATFORM_NAME="ARM64 (Apple Silicon)"
elif [ "$CURRENT_ARCH" = "x86_64" ]; then
    TEST_TAG="${IMAGE_TAG}-linux-amd64"
    PLATFORM_NAME="AMD64 (Intel)"
else
    echo "⚠️ Unknown architecture: $CURRENT_ARCH"
    TEST_TAG="${IMAGE_TAG}-linux-arm64"  # Default to ARM64
    PLATFORM_NAME="Unknown"
fi

echo "🧪 Testing ${PLATFORM_NAME} image..."

# Quick test run
CONTAINER_NAME="x2a-multiarch-test"

# Cleanup existing test container
podman stop ${CONTAINER_NAME} 2>/dev/null || true
podman rm ${CONTAINER_NAME} 2>/dev/null || true

# Run test container
podman run -d \
    --name ${CONTAINER_NAME} \
    -p 2024:2024 \
    -e LLM_BASE_URL="https://lss-lss.apps.prod.rhoai.rh-aiservices-bu.com/v1/openai/v1" \
    -e LLM_MODEL="llama-4-scout-17b-16e-w4a16" \
    -e LLM_API_KEY="dummy-key" \
    ${REGISTRY}/${IMAGE_NAME}:${TEST_TAG}

echo "⏳ Waiting for container to start..."
sleep 10

# Check if container is running
if podman ps | grep -q ${CONTAINER_NAME}; then
    echo " Container started successfully on ${PLATFORM_NAME}"
    
    # Basic connectivity test
    sleep 5
    if curl -f -s http://localhost:2024 >/dev/null 2>&1; then
        echo " API responding on port 2024"
    else
        echo "⚠️ API not responding yet (may need more time)"
    fi
    
    echo "📋 Container logs:"
    podman logs ${CONTAINER_NAME} | tail -10
else
    echo " Container failed to start"
    echo "📋 Container logs:"
    podman logs ${CONTAINER_NAME}
fi

# Cleanup test container
podman stop ${CONTAINER_NAME} 2>/dev/null || true
podman rm ${CONTAINER_NAME} 2>/dev/null || true

# ============================================================================
# RESULTS
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
echo "🚀 Usage:"
echo "   Run on current arch: podman run -p 2024:2024 ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "   Run specific arch:   podman run --platform linux/amd64 -p 2024:2024 ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "   Push to registry:    podman manifest push ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "🧹 Cleanup:"
echo "   Remove images: podman rmi ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}*"
echo "   Remove manifest: podman manifest rm ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "🎉 Multi-architecture build complete!"
