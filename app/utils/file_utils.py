import os
import shutil
from datetime import datetime
from typing import Optional
from fastapi import UploadFile


def save_uploaded_file(file: UploadFile, upload_dir: str) -> str:
    """
    Сохранить загруженный файл
    """
    os.makedirs(upload_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def delete_file(file_path: str) -> bool:
    """
    Удалить файл
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except:
        return False


def get_file_size(file_path: str) -> Optional[int]:
    """
    Получить размер файла
    """
    try:
        return os.path.getsize(file_path)
    except:
        return None


def clean_old_files(directory: str, days_old: int = 7):
    """
    Удалить старые файлы
    """
    try:
        now = datetime.now()
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (now - file_time).days > days_old:
                    delete_file(file_path)
    except:
        pass