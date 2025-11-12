#!/bin/bash
# Production deployment script for AI Agent
# Deploys to remote server using Docker Compose

set -e  # Exit on error

# Configuration
SERVER="166.1.227.64"
SERVER_USER="${SERVER_USER:-root}"  # Default to root, override with SERVER_USER env var
APP_DIR="${APP_DIR:-/opt/ai-agent}"  # Default deployment directory
DOCKER_IMAGE="johnndelembi/ai-agent:latest"
COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AI Agent Production Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Server: $SERVER"
echo "User: $SERVER_USER"
echo "App Directory: $APP_DIR"
echo "Docker Image: $DOCKER_IMAGE"
echo ""

# Check if .env file exists locally
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found locally${NC}"
    echo "Make sure .env file exists on the server at $APP_DIR/.env"
fi

# Step 1: Login to Docker Hub (on server)
echo -e "${GREEN}[1/5] Ensuring Docker Hub login on server...${NC}"
ssh ${SERVER_USER}@${SERVER} "docker login" || {
    echo -e "${RED}Failed to login to Docker Hub on server${NC}"
    exit 1
}

# Step 2: Create app directory on server
echo -e "${GREEN}[2/5] Creating app directory on server...${NC}"
ssh ${SERVER_USER}@${SERVER} "mkdir -p $APP_DIR"

# Step 3: Copy compose file to server
echo -e "${GREEN}[3/5] Copying compose file to server...${NC}"
scp $COMPOSE_FILE ${SERVER_USER}@${SERVER}:$APP_DIR/compose.prod.yml

# Step 4: Copy .env file if it exists locally
if [ -f ".env" ]; then
    echo -e "${GREEN}[4/5] Copying .env file to server...${NC}"
    scp .env ${SERVER_USER}@${SERVER}:$APP_DIR/.env
else
    echo -e "${YELLOW}[4/5] Skipping .env copy (file not found locally)${NC}"
    echo "Make sure .env file exists on server at $APP_DIR/.env"
fi

# Step 5: Deploy on server
echo -e "${GREEN}[5/5] Deploying on server...${NC}"
ssh ${SERVER_USER}@${SERVER} << EOF
    set -e
    cd $APP_DIR
    
    # Pull latest image
    echo "Pulling latest image..."
    docker pull $DOCKER_IMAGE
    
    # Stop existing containers
    echo "Stopping existing containers..."
    docker-compose down || true
    
    # Start services
    echo "Starting services..."
    docker-compose up -d
    
    # Show status
    echo ""
    echo "Deployment complete! Container status:"
    docker-compose ps
    
    echo ""
    echo "Services are starting up. Check logs with:"
    echo "  docker-compose logs -f"
EOF

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "API will be available at: http://${SERVER}:8000"
echo "Flower dashboard: http://${SERVER}:5555"
echo ""
echo "To check logs:"
echo "  ssh ${SERVER_USER}@${SERVER} 'cd $APP_DIR && docker-compose logs -f'"
echo ""
echo "To restart services:"
echo "  ssh ${SERVER_USER}@${SERVER} 'cd $APP_DIR && docker-compose restart'"
echo ""

