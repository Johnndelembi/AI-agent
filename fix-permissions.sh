#!/bin/bash
# Quick fix script for Docker volume permissions
# Run this on the host machine to fix permissions for mounted volumes

echo "🔧 Fixing permissions for Docker volumes..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Fix permissions for audio_output
if [ -d "$SCRIPT_DIR/audio_output" ]; then
    echo "Fixing audio_output permissions..."
    chmod -R 777 "$SCRIPT_DIR/audio_output" 2>/dev/null || sudo chmod -R 777 "$SCRIPT_DIR/audio_output"
else
    echo "Creating audio_output directory..."
    mkdir -p "$SCRIPT_DIR/audio_output"
    chmod -R 777 "$SCRIPT_DIR/audio_output" 2>/dev/null || sudo chmod -R 777 "$SCRIPT_DIR/audio_output"
fi

# Fix permissions for logs
if [ -d "$SCRIPT_DIR/logs" ]; then
    echo "Fixing logs permissions..."
    chmod -R 777 "$SCRIPT_DIR/logs" 2>/dev/null || sudo chmod -R 777 "$SCRIPT_DIR/logs"
else
    echo "Creating logs directory..."
    mkdir -p "$SCRIPT_DIR/logs"
    chmod -R 777 "$SCRIPT_DIR/logs" 2>/dev/null || sudo chmod -R 777 "$SCRIPT_DIR/logs"
fi

# Fix permissions for data
if [ -d "$SCRIPT_DIR/data" ]; then
    echo "Fixing data permissions..."
    chmod -R 777 "$SCRIPT_DIR/data" 2>/dev/null || sudo chmod -R 777 "$SCRIPT_DIR/data"
else
    echo "Creating data directory..."
    mkdir -p "$SCRIPT_DIR/data"
    chmod -R 777 "$SCRIPT_DIR/data" 2>/dev/null || sudo chmod -R 777 "$SCRIPT_DIR/data"
fi

echo "✅ Permissions fixed! You can now restart your Docker containers."
