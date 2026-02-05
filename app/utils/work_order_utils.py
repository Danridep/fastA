import os
import json
from datetime import datetime
from typing import Dict, Any
from app.config import settings


def create_session_directory(session_id: str) -> Dict[str, str]:
    """
    Создает директории для сессии
    """
    directories = {
        "upload": os.path.join(settings.WORK_ORDERS_UPLOAD_DIR, session_id),
        "export": os.path.join(settings.WORK_ORDERS_EXPORT_DIR, session_id)
    }

    for dir_path in directories.values():
        os.makedirs(dir_path, exist_ok=True)

    return directories

def cleanup_old_sessions(days_old: int = 7):
    """
    Очищает старые сессии и файлы
    """
    try:
        now = datetime.now()

        # Очищаем директории uploads
        for session_dir in os.listdir(settings.WORK_ORDERS_UPLOAD_DIR):
            session_path = os.path.join(settings.WORK_ORDERS_UPLOAD_DIR, session_dir)
            if os.path.isdir(session_path):
                dir_time = datetime.fromtimestamp(os.path.getmtime(session_path))
                if (now - dir_time).days > days_old:
                    import shutil
                    shutil.rmtree(session_path)

        # Очищаем директории exports
        for session_dir in os.listdir(settings.WORK_ORDERS_EXPORT_DIR):
            session_path = os.path.join(settings.WORK_ORDERS_EXPORT_DIR, session_dir)
            if os.path.isdir(session_path):
                dir_time = datetime.fromtimestamp(os.path.getmtime(session_path))
                if (now - dir_time).days > days_old:
                    import shutil
                    shutil.rmtree(session_path)

    except Exception as e:
        print(f"Ошибка очистки старых сессий: {e}")


def format_violation_text(region: str, orders: list) -> str:
    """
    Форматирует текст нарушений для копирования
    """
    lines = [f"{region.upper()}:", "Привет, не списаны материалы за", ""]

    for order in sorted(orders, key=lambda x: x.get('Номер заявки', '')):
        city = order.get('Город', 'Не указан')
        executor = order.get('Исполнитель', 'Не указан')
        lines.append(f"{order['Номер заявки']} - {city} - {executor}")

    lines.append(f"\nВсего: {len(orders)} заявок")

    return "\n".join(lines)


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Получает информацию о файле
    """
    try:
        if not os.path.exists(file_path):
            return {"exists": False}

        stats = os.stat(file_path)

        return {
            "exists": True,
            "size": stats.st_size,
            "created": datetime.fromtimestamp(stats.st_ctime),
            "modified": datetime.fromtimestamp(stats.st_mtime),
            "filename": os.path.basename(file_path),
            "path": file_path
        }

    except Exception as e:
        return {"exists": False, "error": str(e)}