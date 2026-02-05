import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    # Основные настройки приложения
    APP_TITLE: str = "Excel Web App"
    APP_DESCRIPTION: str = "Веб-версия приложения для работы с Excel"
    APP_VERSION: str = "1.0.0"

    # Настройки базы данных
    DATABASE_URL: str = f"sqlite:///{Path(__file__).parent.parent / 'excel_app.db'}"

    # Настройки безопасности
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Настройки CORS
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Директории для обработки заявок
    WORK_ORDERS_UPLOAD_DIR: str = Field(default="uploads/work_orders")
    WORK_ORDERS_EXPORT_DIR: str = Field(default="exports/work_orders")

    # Настройки файлов
    MAX_UPLOAD_SIZE: int = Field(default=50 * 1024 * 1024, description="50MB")
    ALLOWED_EXTENSIONS: List[str] = [".xlsx", ".xls", ".csv"]

    # Настройки пути
    UPLOAD_DIR: str = "uploads"
    EXPORT_DIR: str = "exports"
    STATIC_DIR: str = "static"
    TEMPLATE_DIR: str = "templates"

    # Настройки приложения
    AUTO_SAVE_INTERVAL: int = 30000
    SESSION_TIMEOUT: int = 3600

    # Конфигурация модели
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Создаем экземпляр настроек
settings = Settings()


# Создаем директории после инициализации настроек
def create_directories():
    directories = [
        settings.WORK_ORDERS_UPLOAD_DIR,
        settings.WORK_ORDERS_EXPORT_DIR,
        settings.UPLOAD_DIR,
        settings.EXPORT_DIR,
        settings.STATIC_DIR,
        settings.TEMPLATE_DIR
    ]

    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"Директория создана/проверена: {directory}")
        except Exception as e:
            print(f"Ошибка создания директории {directory}: {e}")


create_directories()

print(f"База данных будет создана по пути: {settings.DATABASE_URL}")
print(f"Директория для загрузки work orders: {settings.WORK_ORDERS_UPLOAD_DIR}")
print(f"Директория для экспорта work orders: {settings.WORK_ORDERS_EXPORT_DIR}")