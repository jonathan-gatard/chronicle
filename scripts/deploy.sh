#!/bin/bash
# Deploy Scribe to Home Assistant and Restart

SOURCE_DIR="$(cd "$(dirname "$0")/../custom_components/scribe" && pwd)"
TARGET_DIR="$1"
CONTAINER_NAME=${2:-homeassistant}

if [ -z "$TARGET_DIR" ]; then
    echo "Usage: $0 <target_directory> [container_name]"
    exit 1
fi

echo "🚀 Deploying Scribe..."

# 1. Sync Files
echo "📂 Syncing files..."
# Ensure target exists
mkdir -p "$TARGET_DIR"
# Clean target
rm -rf "$TARGET_DIR"/*

# Copy all files from source to target
cp -r "$SOURCE_DIR"/* "$TARGET_DIR"/

echo "✅ Files copied."

# 2. Restart Home Assistant
echo "🔄 Restarting Home Assistant..."
docker restart "$CONTAINER_NAME"

echo "✅ Deployment Complete!"
