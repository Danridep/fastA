import re
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode


def validate_email(email: str) -> bool:
    """Проверка валидности email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Проверка валидности телефона"""
    pattern = r'^[\d\s\-\+\(\)]{10,20}$'
    return bool(re.match(pattern, phone))


def generate_hash(text: str) -> str:
    """Генерация хеша для текста"""
    return hashlib.md5(text.encode()).hexdigest()


def format_datetime(dt: datetime, format_str: str = "%d.%m.%Y %H:%M") -> str:
    """Форматирование даты и времени"""
    return dt.strftime(format_str)


def parse_datetime(dt_str: str, format_str: str = "%d.%m.%Y %H:%M") -> Optional[datetime]:
    """Парсинг даты и времени"""
    try:
        return datetime.strptime(dt_str, format_str)
    except:
        return None


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
    """Преобразование вложенного словаря в плоский"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, ', '.join(map(str, v))))
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Разделение списка на части"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_get(obj: Any, keys: List[str], default: Any = None) -> Any:
    """Безопасное получение значения из вложенного объекта"""
    try:
        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key, default)
            elif isinstance(obj, list) and key.isdigit():
                obj = obj[int(key)] if int(key) < len(obj) else default
            else:
                obj = getattr(obj, key, default)
            if obj is default:
                break
        return obj
    except:
        return default


def build_url(base_url: str, params: Dict) -> str:
    """Построение URL с параметрами"""
    if params:
        return f"{base_url}?{urlencode(params)}"
    return base_url


def human_readable_size(size_bytes: int) -> str:
    """Преобразование размера в читаемый вид"""
    if size_bytes == 0:
        return "0 Б"

    size_names = ("Б", "КБ", "МБ", "ГБ", "ТБ")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.2f} {size_names[i]}"


def sanitize_filename(filename: str) -> str:
    """Очистка имени файла от небезопасных символов"""
    # Заменяем небезопасные символы
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Убираем начальные и конечные точки/пробелы
    filename = filename.strip('. ')
    # Ограничиваем длину
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    return filename


def get_month_name(month_number: int) -> str:
    """Получить название месяца по номеру"""
    months = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ]
    return months[month_number - 1] if 1 <= month_number <= 12 else 'Неизвестно'


def calculate_percentage(part: float, total: float) -> float:
    """Рассчитать процент"""
    if total == 0:
        return 0
    return round((part / total) * 100, 2)


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Объединение словарей с глубоким копированием"""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def time_ago(dt: datetime) -> str:
    """Время в формате "сколько времени назад" """
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "только что"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} мин. назад"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} ч. назад"
    elif seconds < 2592000:
        days = int(seconds // 86400)
        return f"{days} дн. назад"
    else:
        months = int(seconds // 2592000)
        return f"{months} мес. назад"


def validate_russian_text(text: str) -> bool:
    """Проверка, что текст содержит только русские буквы и разрешенные символы"""
    pattern = r'^[а-яА-ЯёЁ0-9\s\-\.,!?;:()"]+$'
    return bool(re.match(pattern, text))