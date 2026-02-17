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

    # Tokenizer mode: "hf" uses HuggingFace tokenizer (avoids mistral_common restrictions)
    if cfg.get("tokenizer_mode"):
        argv += ["--tokenizer-mode", cfg["tokenizer_mode"]]
    if cfg.get("config_format"):
        argv += ["--config-format", cfg["config_format"]]
    if cfg.get("load_format"):
        argv += ["--load-format", cfg["load_format"]]

    # Function calling / tools support (set tool_call_parser in models.json per profile)
    # Plugin must be loaded before parser name validation
    tool_parser_plugin = cfg.get("tool_parser_plugin")
    if tool_parser_plugin:
        argv += ["--tool-parser-plugin", tool_parser_plugin]
    tool_parser = cfg.get("tool_call_parser")
    if tool_parser:
        argv += ["--enable-auto-tool-choice", "--tool-call-parser", tool_parser]
    chat_template = cfg.get("chat_template")
    if chat_template:
        argv += ["--chat-template", chat_template]

    print(f"[entrypoint] profile={profile} model={model} tool_parser={tool_parser}", flush=True)
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()
