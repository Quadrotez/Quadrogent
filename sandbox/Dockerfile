FROM alpine:latest

RUN apk add --no-cache \
    bash \
    curl \
    wget \
    git \
    python3 \
    py3-pip \
    zip \
    unzip \
    sudo

RUN echo '#!/bin/bash' > /usr/local/bin/apt-get && \
    echo 'if [[ "$1" == "install" ]]; then shift; sudo apk add --no-cache "$@"; else echo "Only install command is wrapped"; fi' >> /usr/local/bin/apt-get && \
    chmod +x /usr/local/bin/apt-get

RUN adduser -D -s /bin/bash quadrogent && \
    echo "quadrogent ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

WORKDIR /home/quadrogent
RUN mkdir -p /home/quadrogent/uploads /home/quadrogent/output && \
    chown -R quadrogent:quadrogent /home/quadrogent

ENV HOME=/home/quadrogent

WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir -r requirements.txt && chown -R quadrogent:quadrogent /app

COPY sandbox_server.py .

USER quadrogent

EXPOSE 5000

CMD ["/app/venv/bin/python3", "-m", "uvicorn", "sandbox_server:app", "--host", "0.0.0.0", "--port", "5000"]
