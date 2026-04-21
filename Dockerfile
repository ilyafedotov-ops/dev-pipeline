FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.opencode/bin:/root/.local/bin:${PATH}"

WORKDIR /app

# System deps used by DevGodzilla integrations (git, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Git safe.directory — repos cloned from host/Windmill may have different UID.
RUN git config --global --add safe.directory '*'

# Optional: install CLI agents (opencode/codex/claude/gemini) inside the container.
# Enabled by compose via build-arg INSTALL_AGENT_CLIS=1.
ARG INSTALL_AGENT_CLIS=0
RUN if [ "${INSTALL_AGENT_CLIS}" = "1" ]; then \
      set -eux; \
      apt-get update; \
      apt-get install -y --no-install-recommends nodejs npm; \
      rm -rf /var/lib/apt/lists/*; \
      curl -fsSL https://opencode.ai/install | bash; \
      npm install -g @openai/codex @anthropic-ai/claude-code @google/gemini-cli; \
      opencode --version; \
      codex --version; \
      claude --version; \
      gemini --version; \
    fi

# Install DevGodzilla dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "devgodzilla.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
