#!/bin/bash
set -e

echo "🚀 Building X2A V1 Agents Container"
echo "===================================="

IMAGE_NAME="x2a-agents"
TAG="${1:-latest}"

echo "📋 Building: ${IMAGE_NAME}:${TAG}"

podman build -t ${IMAGE_NAME}:${TAG} .

echo " Build complete: ${IMAGE_NAME}:${TAG}"
echo "🚀 To run: podman run -p 2024:2024 ${IMAGE_NAME}:${TAG}"
