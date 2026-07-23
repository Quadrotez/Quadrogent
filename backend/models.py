from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Setting(Base):
    """Хранилище настроек в формате key-value"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ApiKey(Base):
    """API-ключи для разных провайдеров (Ollama, OpenRouter, Groq и т.д.)"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    provider = Column(String, unique=True, nullable=False, index=True)
    api_key = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    proxy_url = Column(String, nullable=True)
    enabled = Column(Integer, nullable=False, default=1)  # 1=вкл, 0=выкл
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Chat(Base):
    """Модель чата (диалога)"""
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, default="Новый чат")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Message(Base):
    """Модель сообщения в чате"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, nullable=False, index=True)
    role = Column(String, nullable=False)  # "user", "assistant", "system", "tool"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ToolCall(Base):
    """Запись вызова инструмента моделью"""
    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, nullable=False, index=True)
    tool = Column(String, nullable=False)
    input = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, success, error
    created_at = Column(DateTime, server_default=func.now())


class PresentedFile(Base):
    """Файлы, которые модель презентовала пользователю"""
    __tablename__ = "presented_files"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, nullable=False, index=True)
    filename = Column(String, nullable=False)
    local_path = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())