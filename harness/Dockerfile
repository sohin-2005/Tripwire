# Sandbox for running Claude Code on benchmark tasks.
# The container sees only the mounted task folder; it never sees the host's files.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force

# Claude Code refuses to skip permission prompts as root.
RUN useradd --create-home --uid 1000 agent \
    && mkdir -p /work /home/agent/.claude/projects \
    && chown -R agent:agent /work /home/agent
USER agent
WORKDIR /work
