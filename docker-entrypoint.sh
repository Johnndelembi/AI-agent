#!/bin/bash
set -e

# Fix permissions for mounted volumes
# This ensures the app user can write to mounted directories
# We run as root initially to fix permissions, then switch to app user

if [ -d "/app/audio_output" ]; then
    echo "🔧 Fixing permissions for /app/audio_output..."
    # Try to change ownership to app user, fallback to making it world-writable
    chown -R app:app /app/audio_output 2>/dev/null || chmod -R 777 /app/audio_output || true
    # Ensure directory is writable
    chmod -R u+w /app/audio_output 2>/dev/null || chmod -R 777 /app/audio_output || true
fi

if [ -d "/app/logs" ]; then
    echo "🔧 Fixing permissions for /app/logs..."
    chown -R app:app /app/logs 2>/dev/null || chmod -R 777 /app/logs || true
    chmod -R u+w /app/logs 2>/dev/null || chmod -R 777 /app/logs || true
fi

if [ -d "/app/data" ]; then
    echo "🔧 Fixing permissions for /app/data..."
    chown -R app:app /app/data 2>/dev/null || chmod -R 777 /app/data || true
    chmod -R u+w /app/data 2>/dev/null || chmod -R 777 /app/data || true
fi

# Switch to app user and execute the main command
# If running as root, switch to app user; otherwise just execute
if [ "$(id -u)" = "0" ]; then
    # We're root, switch to app user using su
    if [ $# -eq 0 ]; then
        exec su app
    else
        # Build command by properly quoting each argument
        QUOTED_ARGS=()
        for arg in "$@"; do
            QUOTED_ARGS+=("$(printf '%q' "$arg")")
        done
        # Join with spaces and execute
        CMD="${QUOTED_ARGS[*]}"
        exec su app -c "cd /app && $CMD"
    fi
else
    # Already running as app user, just execute
    exec "$@"
fi



