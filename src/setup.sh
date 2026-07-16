#!/bin/bash
set -euo pipefail

MODEL_REPO="Qwen/Qwen3-8B-GGUF"
MODEL_FILE="/workspace/models/Qwen3-8B-Q4_K_M.gguf"
LOG="/workspace/llama.log"

echo "=== 1/5 GPU ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || {
  echo "!! nessuna GPU. Pod avviato in modalità CPU?"; exit 1; }

echo "=== 2/5 dipendenze ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wget git cmake build-essential libcurl4-openssl-dev > /dev/null
pip install -q huggingface-hub

echo "=== 3/5 llama.cpp ==="
cd /workspace
[ -d llama.cpp ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp
cd llama.cpp

if [ ! -f build/bin/llama-server ]; then
  # niente CMAKE_CUDA_ARCHITECTURES: cmake rileva la GPU da solo.
  # Così lo script gira su 3090 (86), 4090 (89), A40 (86)... senza modifiche.
  cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
  cmake --build build --config Release -j"$(nproc)"
else
  echo "già compilato, salto"
fi

echo "--- device rilevati ---"
./build/bin/llama-server --list-devices
./build/bin/llama-server --list-devices | grep -qi cuda || {
  echo "!! build senza CUDA. Cancella build/ e rilancia."; exit 1; }

echo "=== 4/5 modello ==="
if [ ! -f "$MODEL_FILE" ]; then
  hf download "$MODEL_REPO" --include "*Q4_K_M*" --local-dir /workspace/models
else
  echo "già presente ($(du -h "$MODEL_FILE" | cut -f1))"
fi

echo "=== 5/5 avvio ==="
pkill -f llama-server || true
sleep 2

nohup ./build/bin/llama-server \
  -m "$MODEL_FILE" \
  --host 0.0.0.0 --port 8080 \
  -ngl 99 --parallel 8 --cont-batching -c 32768 \
  > "$LOG" 2>&1 &

echo -n "attendo il server"
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    echo ""
    echo "=========================================="
    echo " PRONTO"
    nvidia-smi --query-gpu=memory.used --format=csv,noheader
    echo " URL: https://$RUNPOD_POD_ID-8080.proxy.runpod.net"
    echo " log: tail -f $LOG"
    echo "=========================================="
    exit 0
  fi
  echo -n "."
  sleep 2
done

echo ""
echo "!! timeout. Ultime righe del log:"
tail -30 "$LOG"
exit 1
SCRIPT_EOF

chmod +x /workspace/setup.sh
bash /workspace/setup.sh