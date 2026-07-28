FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force

RUN userdel -r node && \
    useradd -m -d /home/agent -u 1000 agent && \
    chown -R agent:agent /app

COPY --chown=agent:agent server.js /app/server.js

ENV CODEX_HOME=/mnt/efs/.codex \
    WORKSPACE_DIR=/mnt/efs/workspace \
    NODE_ENV=production \
    PORT=8080

EXPOSE 8080
USER agent
CMD ["node", "/app/server.js"]
