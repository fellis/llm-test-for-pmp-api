#!/usr/bin/env python3
"""
Start vLLM with model and args from config/models.json for the selected MODEL_PROFILE.
Uses HF cache from /root/.cache/huggingface (mount ./models) so models are not re-downloaded.
"""
import json
import os
import sys
from pathlib import Path


def main():
    config_path = os.getenv("CONFIG_PATH", "/config/models.json")
    profile = os.getenv("MODEL_PROFILE", "coding").strip().lower()

    path = Path(config_path)
    if not path.is_file():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    profiles = data.get("profiles") or {}
    if profile not in profiles:
        print(f"Unknown MODEL_PROFILE: {profile}. Known: {list(profiles)}", file=sys.stderr)
        sys.exit(1)

    cfg = profiles[profile]
    model = cfg.get("model")
    if not model:
        print(f"Profile '{profile}' has no 'model' in config", file=sys.stderr)
        sys.exit(1)

    # Build vLLM argv: python -m vllm.entrypoints.openai.api_server [args]
    argv = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        model,
        "--host",
        "0.0.0.0",
        "--port",
        "8002",
        "--tensor-parallel-size",
        "1",
        "--enforce-eager",
    ]

    if cfg.get("quantization"):
        argv += ["--quantization", cfg["quantization"]]
    if cfg.get("dtype"):
        argv += ["--dtype", cfg["dtype"]]
    if cfg.get("max_model_len") is not None:
        argv += ["--max-model-len", str(cfg["max_model_len"])]
    if cfg.get("gpu_memory_utilization") is not None:
        argv += ["--gpu-memory-utilization", str(cfg["gpu_memory_utilization"])]
    if cfg.get("kv_cache_dtype"):
        argv += ["--kv-cache-dtype", cfg["kv_cache_dtype"]]

    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()
