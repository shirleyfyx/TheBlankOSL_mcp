#!/bin/bash

IMAGE_NAME="mcp-server"
CONTAINER_NAME="mcp-shared"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker Desktop."
  exit 1
fi

# Build the image
echo "Building Docker image..."
docker build --no-cache -t $IMAGE_NAME .

# Stop and remove existing container if it exists
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Stopping and removing existing container..."
    docker rm -f $CONTAINER_NAME
fi

# Run the shared container in the background
echo "Starting shared container..."
docker run -d \
  --name $CONTAINER_NAME \
  -v "$(pwd):/app" \
  $IMAGE_NAME \
  tail -f /dev/null

echo "Container '$CONTAINER_NAME' is running."
echo "You can now start Claude Desktop."
