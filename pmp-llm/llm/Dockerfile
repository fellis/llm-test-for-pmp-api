# Model runner: loads config by MODEL_PROFILE and starts vLLM from cache.
FROM vllm/vllm-openai:latest

WORKDIR /app

COPY entrypoint.py .
COPY templates/ /app/templates/

ENV CONFIG_PATH=/config/models.json
ENV MODEL_PROFILE=coding

ENTRYPOINT ["python3", "/app/entrypoint.py"]
