FROM alpine:latest

# Установка необходимых пакетов
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

# Создание скрипта-обертки для имитации apt-get (так как в Alpine используется apk)
# Это позволит модели использовать привычные команды установки
RUN echo '#!/bin/bash' > /usr/local/bin/apt-get && \
    echo 'if [[ "$1" == "install" ]]; then shift; sudo apk add --no-cache "$@"; else echo "Only install command is wrapped"; fi' >> /usr/local/bin/apt-get && \
    chmod +x /usr/local/bin/apt-get

# Создание пользователя quadrogent
RUN adduser -D -s /bin/bash quadrogent && \
    echo "quadrogent ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Настройка рабочих директорий
WORKDIR /home/quadrogent
RUN mkdir -p /home/quadrogent/uploads /home/quadrogent/output && \
    chown -R quadrogent:quadrogent /home/quadrogent

# Переключение на пользователя quadrogent
USER quadrogent

# Начальная директория
ENV HOME=/home/quadrogent
WORKDIR /home/quadrogent
