# Lab 3 Assignment

## Task 1: Complete the `docker-compose.yml`

A skeleton `docker-compose.yml` is provided in the `Lab3` directory. Complete it so that all 4 services (vLLM, Open WebUI, ASR, TTS) can be started with a single `docker compose up -d` command.

Key points to consider:
- **GPU access:** Services that need GPU must have `runtime: nvidia`.
- **Volume mounts:** vLLM needs the model directory; Open WebUI needs a persistent data volume.
- **Dependencies:** Use `depends_on` so Open WebUI starts after the backend services.
- **Shared memory:** vLLM requires `shm_size: "8g"`.

> **Note:** Jetson Orin NX has 16 GiB shared CPU/GPU memory. The vLLM server is configured with `--gpu-memory-utilization 0.50` to leave room for ASR and TTS. If you encounter out-of-memory errors, try reducing `--max-model-len` or adjusting this value.

## Task 2: Configure Open WebUI

After all services are running, open your browser and go to `http://localhost:3000` (or `http://<jetson-ip>:3000` if accessing remotely).

First-time users will be asked to create an admin account( If no such page, it may because of your groupmate have already created it using the 3000 port, you may **change to another port** when making docker-compose.yml)

After logging in:

### 2.1 Connect LLM (vLLM)

1. Click the **avatar** (bottom-left) → **Admin Panel**
2. Go to **Settings** → **Connections**
3. Under **OpenAI API**, set:
   - API URL: `http://vllm:8000/v1`
   - API Key: `not-needed`
4. Click the **refresh icon** next to the URL — you should see the Qwen3 model appear

### 2.2 Configure Speech-to-Text (ASR)

1. In Admin Panel, go to **Settings** → **Audio**
2. Under **STT Settings**, set:
   - STT Engine: `OpenAI`
   - API Base URL: `http://asr:5092/v1`
   - API Key: `not-needed`
   - STT Model: `faster-whisper`

### 2.3 Configure Text-to-Speech (TTS)

1. Still in **Settings** → **Audio**
2. Under **TTS Settings**, set:
   - TTS Engine: `OpenAI`
   - API Base URL: `http://tts:8880/v1`
   - API Key: `not-needed`
   - TTS Voice: `af_bella`
   - TTS Model: `kokoro`
3. Click **Save** at the bottom

## Task 3: Voice Call Recording

### Browser Microphone Permission

Chrome blocks microphone access on non-HTTPS pages (except `localhost`). If you are accessing the Jetson remotely via its IP address, you need to make the browser see `localhost`. Here are three options:

**Option A — VS Code / Cursor Port Forwarding (easiest):**

If you are connected to the Jetson via VS Code or Cursor Remote-SSH:

1. Open the **Ports** panel (bottom bar → **Ports**, or `Ctrl+Shift+P` → "Ports: Focus on Ports View")
2. Click **Forward a Port**, enter `3000`
3. Open `http://localhost:3000` in your browser — the connection is automatically tunneled to the Jetson

**Option B — SSH Port Forwarding:**

Forward the Jetson's port 3000 to your local machine manually:

```bash
ssh -L 3000:localhost:3000 <user>@<jetson-ip>
```

Then open `http://localhost:3000` in your browser.

**Option C — Chrome Insecure Origins Flag:**

1. Open `chrome://flags/#unsafely-treat-insecure-origin-as-secure` in Chrome
2. Add `http://<jetson-ip>:3000` to the list
3. Click **Relaunch**

### Start the Voice Call

1. Select the Qwen3-4B model in the chat page
2. Click the **phone icon** (top-right of the chat area) to start a voice call
3. Allow microphone access when prompted by the browser
4. Conduct at least **2 complete rounds** of voice dialogue
5. Record your screen and save as `screen-record.mp4`

## Submission

Please submit your work to Blackboard by uploading the following files:
```
docker-compose.yml
screen-record.mp4
```
