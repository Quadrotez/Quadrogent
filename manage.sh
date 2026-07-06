#!/bin/bash

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Директории
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"
LOGS_DIR="logs"

# PID-файлы
BACKEND_PID_FILE="$LOGS_DIR/backend.pid"
FRONTEND_PID_FILE="$LOGS_DIR/frontend.pid"

# Определение команды Docker Compose
if docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE=""
fi

# Функция очистки при Ctrl+C
cleanup() {
    echo -e "\n${YELLOW}Останавливаю процессы...${NC}"
    
    # Останавливаем Docker контейнеры
    if [ -n "$DOCKER_COMPOSE" ]; then
        echo -e "${YELLOW}Останавливаю Docker контейнеры...${NC}"
        $DOCKER_COMPOSE stop > /dev/null 2>&1 || true
    fi

    if [ -f "$BACKEND_PID_FILE" ]; then
        kill $(cat "$BACKEND_PID_FILE") > /dev/null 2>&1 || true
        rm -f "$BACKEND_PID_FILE"
    fi
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        kill $(cat "$FRONTEND_PID_FILE") > /dev/null 2>&1 || true
        rm -f "$FRONTEND_PID_FILE"
    fi
    
    echo -e "${GREEN}Остановлено${NC}"
    exit 0
}

# Установка зависимостей
install() {
    echo -e "${GREEN}Начинаю установку зависимостей...${NC}"
    
    # Сборка Docker образов для песочницы
    if command -v docker > /dev/null 2>&1; then
        echo -e "${YELLOW}Сборка Docker образов для песочницы...${NC}"
        if [ -n "$DOCKER_COMPOSE" ] && [ -f "docker-compose.yml" ]; then
            $DOCKER_COMPOSE build
        else
            cd "$BACKEND_DIR"
            docker build -t quadrogent-sandbox -f sandbox.Dockerfile .
            cd ..
        fi
    else
        echo -e "${RED}Docker не найден. Песочница не будет работать без Docker.${NC}"
    fi

    echo -e "${YELLOW}Инициализация виртуального окружения Python...${NC}"
    cd "$BACKEND_DIR"
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    echo -e "${YELLOW}Установка Python-зависимостей...${NC}"
    pip install -r requirements.txt
    deactivate
    cd ..
    
    echo -e "${YELLOW}Установка Node.js зависимостей...${NC}"
    cd "$FRONTEND_DIR"
    npm install
    cd ..
    
    echo -e "${GREEN}Установка успешно завершена!${NC}"
}

# Запуск в foreground с логами
rundev() {
    trap cleanup SIGINT SIGTERM
    
    mkdir -p "$LOGS_DIR"
    
    # Запуск Docker контейнера песочницы
    if [ -n "$DOCKER_COMPOSE" ] && [ -f "docker-compose.yml" ]; then
        echo -e "${GREEN}Запускаю Docker инфраструктуру (песочница)...${NC}"
        $DOCKER_COMPOSE up -d quadrogent-sandbox
    elif command -v docker > /dev/null 2>&1; then
        echo -e "${GREEN}Запускаю Docker контейнер песочницы...${NC}"
        docker run -d --name quadrogent-runtime quadrogent-sandbox tail -f /dev/null || docker start quadrogent-runtime
    fi

    echo -e "${GREEN}Запускаю бэкенд...${NC}"
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    uvicorn main:app --reload --port 8000 &
    BACKEND_PID=$!
    cd ..
    echo $BACKEND_PID > "$BACKEND_PID_FILE"
    
    echo -e "${GREEN}Запускаю фронтенд...${NC}"
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    echo $FRONTEND_PID > "$FRONTEND_PID_FILE"
    
    echo -e "${GREEN}Всё запущено${NC}"
    echo -e "Бэкенд: http://localhost:8000"
    echo -e "Фронтенд: http://localhost:5173"
    echo -e "${YELLOW}Нажми Ctrl+C для остановки${NC}"
    
    # Ждём любого из процессов
    wait
}

# Запуск в фоне
rundevbg() {
    mkdir -p "$LOGS_DIR"
    
    # Запуск Docker контейнера песочницы
    if [ -n "$DOCKER_COMPOSE" ] && [ -f "docker-compose.yml" ]; then
        echo -e "${GREEN}Запускаю Docker инфраструктуру (песочница) в фоне...${NC}"
        $DOCKER_COMPOSE up -d quadrogent-sandbox
    elif command -v docker > /dev/null 2>&1; then
        echo -e "${GREEN}Запускаю Docker контейнер песочницы в фоне...${NC}"
        docker run -d --name quadrogent-runtime quadrogent-sandbox tail -f /dev/null || docker start quadrogent-runtime
    fi

    echo -e "${GREEN}Запускаю бэкенд в фоне...${NC}"
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    nohup uvicorn main:app --reload --port 8000 > ../"$LOGS_DIR"/backend.log 2>&1 &
    echo $! > ../"$BACKEND_PID_FILE"
    cd ..
    
    echo -e "${GREEN}Запускаю фронтенд в фоне...${NC}"
    cd "$FRONTEND_DIR"
    nohup npm run dev > ../"$LOGS_DIR"/frontend.log 2>&1 &
    echo $! > ../"$FRONTEND_PID_FILE"
    cd ..
    
    echo -e "${GREEN}Всё запущено в фоне${NC}"
    echo -e "Логи: ${YELLOW}./manage.sh logs${NC}"
    echo -e "Стоп: ${YELLOW}./manage.sh stopbg${NC}"
}

# Остановка фоновых процессов
stopbg() {
    echo -e "${YELLOW}Останавливаю процессы...${NC}"
    
    # Останавливаем Docker
    if [ -n "$DOCKER_COMPOSE" ]; then
        echo -e "${YELLOW}Останавливаю Docker контейнеры...${NC}"
        $DOCKER_COMPOSE stop > /dev/null 2>&1 || true
    fi

    if [ -f "$BACKEND_PID_FILE" ]; then
        kill $(cat "$BACKEND_PID_FILE") > /dev/null 2>&1 || true
        rm -f "$BACKEND_PID_FILE"
        echo -e "${GREEN}Бэкенд остановлен${NC}"
    else
        echo -e "${YELLOW}Бэкенд не запущен${NC}"
    fi
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        kill $(cat "$FRONTEND_PID_FILE") > /dev/null 2>&1 || true
        rm -f "$FRONTEND_PID_FILE"
        echo -e "${GREEN}Фронтенд остановлен${NC}"
    else
        echo -e "${YELLOW}Фронтенд не запущен${NC}"
    fi
}

# Просмотр логов
logs() {
    if [ ! -d "$LOGS_DIR" ] || [ -z "$(ls -A $LOGS_DIR/*.log 2>/dev/null)" ]; then
        echo -e "${RED}Логи не найдены${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Просмотр логов (Ctrl+C для выхода)${NC}"
    tail -f "$LOGS_DIR"/*.log
}

# Показать помощь
help() {
    echo "Использование: ./manage.sh <команда>"
    echo ""
    echo "Команды:"
    echo "  install    - Установить зависимости (Docker build, Python venv и npm)"
    echo "  rundev     - Запустить всё в foreground с логами (включая песочницу)"
    echo "  rundevbg   - Запустить всё в фоне (включая песочницу)"
    echo "  stopbg     - Остановить фоновые процессы и Docker"
    echo "  logs       - Просмотр логов"
    echo "  help       - Показать эту справку"
}

# Обработка команд
case "$1" in
    install)
        install
        ;;
    rundev)
        rundev
        ;;
    rundevbg)
        rundevbg
        ;;
    stopbg)
        stopbg
        ;;
    logs)
        logs
        ;;
    help|--help|-h)
        help
        ;;
    *)
        echo -e "${RED}Неизвестная команда: $1${NC}"
        help
        exit 1
        ;;
esac
