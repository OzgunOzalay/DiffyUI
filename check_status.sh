#!/bin/bash
# Quick status check script for DiffyUI

echo "=== DiffyUI Status Check ==="
echo ""

echo "1. Checking Docker containers..."
docker ps -a | grep -E "diffyui|NAME" || echo "No DiffyUI containers found"
echo ""

echo "2. Checking ComfyUI container logs (last 20 lines)..."
docker logs --tail 20 diffyui-comfyui 2>&1 || echo "Could not get logs"
echo ""

echo "3. Checking if port 8188 is accessible..."
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8188 || echo "Port 8188 not accessible"
echo ""

echo "4. Checking custom_nodes directory..."
docker exec diffyui-comfyui ls -la /app/ComfyUI/custom_nodes 2>&1 | head -10 || echo "Could not check custom_nodes"
echo ""

echo "5. Checking if ComfyUI process is running..."
docker exec diffyui-comfyui ps aux | grep -E "python.*main.py|ComfyUI" || echo "ComfyUI process not found"
echo ""

echo "=== Status Check Complete ==="
echo ""
echo "If containers are not running, try: docker-compose up -d"
echo "If you see errors, check: docker-compose logs comfyui"
