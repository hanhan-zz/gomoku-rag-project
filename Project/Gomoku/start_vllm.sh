#!/bin/bash
# Start vLLM server for Gomoku AI (Qwen3-4B)
# Based on Lab3 configuration

MODEL_PATH="/opt/models/Qwen3-4B-quantized.w4a16"
PORT=8000

if [ ! -d "$MODEL_PATH" ]; then
    echo "Error: Model not found at $MODEL_PATH"
    exit 1
fi

echo "Starting vLLM server with Qwen3-4B..."
echo "Model: $MODEL_PATH"
echo "Port: $PORT"
echo ""

docker run \
    -d -it \
    --network host \
    --shm-size=8g \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    --runtime=nvidia \
    --name=vllm-gomoku \
    -v "$MODEL_PATH:/root/.cache/huggingface/Qwen3-4B-quantized.w4a16" \
    ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin \
    vllm serve /root/.cache/huggingface/Qwen3-4B-quantized.w4a16 \
        --host 0.0.0.0 \
        --port $PORT \
        --gpu-memory-utilization 0.50 \
        --max-model-len 4096 \
        --max-num-batched-tokens 2048

echo "vLLM server started. Wait ~30s for model loading."
echo "Health check: curl -s http://localhost:$PORT/v1/models"
