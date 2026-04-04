#!/bin/bash
# Stop vLLM server
docker stop vllm-gomoku 2>/dev/null && echo "vLLM stopped" || echo "vLLM not running"
docker rm vllm-gomoku 2>/dev/null && echo "Container removed" || true
