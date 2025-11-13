#!/bin/bash
# Production deployment script for AI Agent
# Deploys to remote server using Docker Compose

set -e  # Exit on error

# Configuration
SERVER="166.1.227.64"
SERVER_USER="${SERVER_USER:-root}"  # Default to root, override with SERVER_USER env var
APP_DIR="${APP_DIR:-/var/www/mipango-ai-engine}"  # Default deployment directory
DOCKER_IMAGE="registry.mipangoapp.com/mipango-ai-engine:latest"


#SIMPLIFIED VERSION
#!/bin/bash

set -euo pipefail

# Build docker image
docker build --platform=linux/amd64 --target production -t ${DOCKER_IMAGE} .

# Push image to registry
docker push ${DOCKER_IMAGE}

# SSH into the server and deploy
ssh ${SERVER_USER}@${SERVER} << 'EOF'
  set -e
  cd $APP_DIR && docker compose pull ${DOCKER_IMAGE}
  docker compose restart ${DOCKER_IMAGE} && docker image prune -f && exit
EOF