FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# gcc + make for test compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc make && \
    rm -rf /var/lib/apt/lists/*

# Node.js 22.x
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

RUN useradd -m -s /bin/bash agent
