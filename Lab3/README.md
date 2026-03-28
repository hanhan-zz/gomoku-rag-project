# Lab 3: Multi-Service AI Deployment with Docker Compose

In Lab 2, you containerized the ASR and TTS services individually. In this lab, you will use **Docker Compose** to orchestrate multiple AI services and integrate them through **Open WebUI** for a complete voice interaction experience on the Jetson Orin NX.

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| LLM (vLLM) | `ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin` | 8000 | Qwen3-4B language model |
| ASR | `faster-whisper:fastapi` | 5092 | Speech-to-Text (from Lab 2) |
| TTS | `dustynv/kokoro-tts:fastapi-r36.4.0-cu128-24.04` | 8880 | Text-to-Speech |
| Open WebUI | `ghcr.io/open-webui/open-webui:main` | 8080 | Web interface |

## Docker Compose Basics

### From `docker run` to `docker-compose.yml`

In Lab 1, we launched the vLLM server with a long `docker run` command:

```bash
docker run \
  -d -it \
  --network host \
  --shm-size=8g \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --runtime=nvidia \
  --name=vllm \
  -v $PWD/Qwen3-4B-quantized.w4a16:/root/.cache/huggingface/Qwen3-4B-quantized.w4a16 \
  ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin \
  vllm serve /root/.cache/huggingface/Qwen3-4B-quantized.w4a16 \
    --gpu-memory-utilization 0.5 \
    --max-model-len 4096 \
    --max-num-batched-tokens 2048
```

This works, but it is hard to manage when you need to run multiple services together. Docker Compose lets you define all services in a single YAML file.

The **equivalent** `docker-compose.yml`:

```yaml
services:
  vllm:
    image: ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin
    network_mode: host
    shm_size: "8g"
    ulimits:
      memlock: -1
      stack: 67108864
    runtime: nvidia
    volumes:
      - /opt/models/Qwen3-4B-quantized.w4a16:/root/.cache/huggingface/Qwen3-4B-quantized.w4a16
    command: >
      vllm serve /root/.cache/huggingface/Qwen3-4B-quantized.w4a16
        --gpu-memory-utilization 0.5
        --max-model-len 4096
        --max-num-batched-tokens 2048
```

Here is how each `docker run` flag maps to a `docker-compose.yml` key:

| `docker run` flag | `docker-compose.yml` key |
|-------------------|--------------------------|
| `--network host` | `network_mode: host` |
| `--shm-size=8g` | `shm_size: "8g"` |
| `--ulimit memlock=-1` | `ulimits: memlock: -1` |
| `--runtime=nvidia` | `runtime: nvidia` |
| `-v host:container` | `volumes: - host:container` |
| (trailing args) | `command: >` |

Now you can start the service with:

```bash
docker compose up -d
```

And stop it with:

```bash
docker compose down
```

### Demo 1: Single-Service App (`demo/hello-server/`)

A minimal example showing how Docker Compose can build and run a single service from a `Dockerfile`.

```
demo/hello-server/
├── app.py              # Simple JSON API server
├── Dockerfile          # Image definition
└── docker-compose.yml  # Compose file with build context
```

**docker-compose.yml:**

```yaml
services:
  web:
    build: .
    ports:
      - "5000:5000"
```

The `build: .` key tells Compose to build the image from the local `Dockerfile`, replacing `docker build` + `docker run` with a single command:

```bash
cd Lab3/demo/hello-server
docker compose up --build
```

Visit `http://localhost:5000` to see the JSON response.

### Demo 2: Multi-Service App (`demo/calculator/`)

A frontend + backend example showing how Compose orchestrates multiple services with `depends_on`.

```
demo/calculator/
├── backend.py            # FastAPI calculator API
├── frontend.html         # Browser UI (Tailwind CSS)
├── Dockerfile.backend    # Backend image
├── Dockerfile.frontend   # Frontend static server
└── docker-compose.yaml   # Two-service Compose file
```

**docker-compose.yaml:**

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: calc-backend
    ports:
      - "6060:6060"

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    container_name: calc-frontend
    ports:
      - "5959:5959"
    depends_on:
      - backend
```

Key differences from Demo 1:
- **Multiple Dockerfiles:** Use `build.dockerfile` to specify which Dockerfile each service uses.
- **`depends_on`:** Ensures the backend starts before the frontend.
- **`container_name`:** Assigns a fixed name to each container.

```bash
cd Lab3/demo/calculator
docker compose up --build
```

Visit `http://localhost:5959` to use the calculator UI.

### Useful Commands

| Command | Description |
|---------|-------------|
| `docker compose up` | Start all services |
| `docker compose up -d` | Start all services in background (detached) |
| `docker compose up --build` | Rebuild images and start |
| `docker compose down` | Stop and remove all containers |
| `docker compose logs` | View logs from all services |
| `docker compose logs -f <service>` | Follow logs for a specific service |
| `docker compose ps` | List running services |

## Multi-Service Architecture

In this lab, all 4 services run in the same Docker Compose network. Open WebUI connects to other services by **service name** (e.g., `http://vllm:8000/v1`). Only Open WebUI's port is exposed to the host for browser access.

```
┌─────────────────────────────────────────────────────┐
│  docker-compose                                     │
│                                                     │
│  ┌───────────┐    /v1/chat/completions              │
│  │  vllm     │◄──────────────────────┐              │
│  │  :8000    │                       │              │
│  └───────────┘                       │              │
│                                ┌─────┴───────┐      │
│  ┌───────────┐  /v1/audio/     │  open-webui │      │
│  │  asr      │◄─transcriptions─│  :8080      │◄─────┼──── Browser :3000
│  │  :5092    │                 │             │      │
│  └───────────┘                 └─────┬───────┘      │
│                                      │              │
│  ┌───────────┐    /v1/audio/speech   │              │
│  │  tts      │◄──────────────────────┘              │
│  │  :8880    │                                      │
│  └───────────┘                                      │
└─────────────────────────────────────────────────────┘
```

## References

- [Open WebUI — Connect to vLLM](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-vllm)
- [Open WebUI — OpenAI STT Integration](https://docs.openwebui.com/features/media-generation/audio/speech-to-text/openai-stt-integration)
- [Open WebUI — Kokoro-FastAPI TTS Integration](https://docs.openwebui.com/features/media-generation/audio/text-to-speech/Kokoro-FastAPI-integration)
- [Kokoro-FastAPI (GitHub)](https://github.com/remsky/Kokoro-FastAPI)
- [Jetson AI Lab — LLMs on Jetson](https://www.jetson-ai-lab.com/tutorials/genai-on-jetson-llms-vlms/)

# Submit Your Work

Read the [Assignment](Assignment.md) file for the submission instructions.
