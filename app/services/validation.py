from typing import Dict, Any, List, Optional, Tuple
import re
from app.models import NomenclatureCreate, AddressCreate, TemplateCreate


class ValidationError(Exception):
    """Ошибка валидации"""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class Validator:
    """Класс для валидации данных"""

    @staticmethod
    def validate_nomenclature(data: Dict[str, Any]) -> List[ValidationError]:
        """Валидация данных номенклатуры"""
        errors = []

        # Тип
        if not data.get('type'):
            errors.append(ValidationError('type', 'Тип обязателен'))
        elif data['type'] not in ['КЦ', 'Расходники']:
            errors.append(ValidationError('type', 'Тип должен быть "КЦ" или "Расходники"'))

        # Название
        if not data.get('name'):
            errors.append(ValidationError('name', 'Название обязательно'))
        elif len(data['name']) > 200:
            errors.append(ValidationError('name', 'Название не должно превышать 200 символов'))

        # Комментарий
        if data.get('comment') and len(data['comment']) > 500:
            errors.append(ValidationError('comment', 'Комментарий не должен превышать 500 символов'))

        return errors

    @staticmethod
    def validate_address(data: Dict[str, Any]) -> List[ValidationError]:
        """Валидация данных адреса"""
        errors = []

        # Адрес
        if not data.get('address'):
            errors.append(ValidationError('address', 'Адрес обязателен'))
        elif len(data['address']) > 300:
            errors.append(ValidationError('address', 'Адрес не должен превышать 300 символов'))

        # ФИО получателя
        if not data.get('contact_person'):
            errors.append(ValidationError('contact_person', 'ФИО получателя обязательно'))
        elif len(data['contact_person']) > 100:
            errors.append(ValidationError('contact_person', 'ФИО не должно превышать 100 символов'))

        # Номер НП
        if data.get('np_number') and len(data['np_number']) > 20:
            errors.append(ValidationError('np_number', 'Номер НП не должен превышать 20 символов'))

        # Телефон
        if data.get('phone'):
            phone = data['phone']
            # Убираем все нецифровые символы для проверки
            digits = re.sub(r'\D', '', phone)
            if len(digits) < 10:
                errors.append(ValidationError('phone', 'Некорректный номер телефона'))

        return errors

    @staticmethod
    def validate_template(data: Dict[str, Any]) -> List[ValidationError]:
        """Валидация данных шаблона"""
        errors = []

        # Название
        if not data.get('name'):
            errors.append(ValidationError('name', 'Название шаблона обязательно'))
        elif len(data['name']) > 100:
            errors.append(ValidationError('name', 'Название не должно превышать 100 символов'))

        # Тип
        if not data.get('type'):
            errors.append(ValidationError('type', 'Тип шаблона обязателен'))
        elif data['type'] not in ['КЦ', 'Расходники']:
            errors.append(ValidationError('type', 'Тип должен быть "КЦ" или "Расходники"'))

        # Заголовки
        if not data.get('headers'):
            errors.append(ValidationError('headers', 'Заголовки обязательны'))
        elif not isinstance(data['headers'], list):
            errors.append(ValidationError('headers', 'Заголовки должны быть списком'))
        elif len(data['headers']) == 0:
            errors.append(ValidationError('headers', 'Добавьте хотя бы один заголовок'))
        else:
            for i, header in enumerate(data['headers']):
                if not header or not isinstance(header, str):
                    errors.append(ValidationError(f'headers[{i}]', 'Заголовок должен быть строкой'))
                elif len(header) > 100:
                    errors.append(ValidationError(f'headers[{i}]', 'Заголовок не должен превышать 100 символов'))

        return errors

    @staticmethod
    def validate_order_data(data: Dict[str, Any]) -> List[ValidationError]:
        """Валидация данных заказа"""
        errors = []

        if not isinstance(data, dict):
            errors.append(ValidationError('data', 'Данные должны быть словарем'))
            return errors

        # Проверяем обязательные поля
        required_fields = ['headers', 'addresses', 'addresses_data']
        for field in required_fields:
            if field not in data:
                errors.append(ValidationError(field, 'Обязательное поле отсутствует'))

        if errors:
            return errors

        # Проверяем заголовки
        if not isinstance(data['headers'], list):
            errors.append(ValidationError('headers', 'Заголовки должны быть списком'))

        # Проверяем адреса
        if not isinstance(data['addresses'], list):
            errors.append(ValidationError('addresses', 'Адреса должны быть списком'))

        # Проверяем данные адресов
        if not isinstance(data['addresses_data'], dict):
            errors.append(ValidationError('addresses_data', 'Данные адресов должны быть словарем'))
        else:
            for address, items in data['addresses_data'].items():
                if not isinstance(items, list):
                    errors.append(ValidationError(f'addresses_data[{address}]', 'Данные должны быть списком'))
                    continue

                for i, item in enumerate(items):
                    if not isinstance(item, dict):
                        errors.append(
                            ValidationError(f'addresses_data[{address}][{i}]', 'Элемент должен быть словарем'))
                        continue

                    # Проверяем наличие всех заголовков
                    for header in data['headers']:
                        if header not in item:
                            errors.append(ValidationError(
                                f'addresses_data[{address}][{i}][{header}]',
                                'Отсутствует обязательное поле'
                            ))

        return errors

    @staticmethod
    def validate_excel_file(file_content: bytes, filename: str) -> List[ValidationError]:
        """Валидация Excel файла"""
        errors = []

        # Проверяем расширение
        if not filename.lower().endswith(('.xlsx', '.xls')):
            errors.append(ValidationError('file', 'Файл должен быть в формате Excel (.xlsx, .xls)'))

        # Проверяем размер (максимум 50MB)
        max_size = 50 * 1024 * 1024
        if len(file_content) > max_size:
            errors.append(ValidationError('file', f'Размер файла не должен превышать {max_size // (1024 * 1024)}MB'))

        # Проверяем что файл не пустой
        if len(file_content) == 0:
            errors.append(ValidationError('file', 'Файл пустой'))

        return errors

    @staticmethod
    def validate_month(month: int) -> List[ValidationError]:
        """Валидация месяца"""
        errors = []

        if not isinstance(month, int):
            errors.append(ValidationError('month', 'Месяц должен быть числом'))
        elif not 1 <= month <= 12:
            errors.append(ValidationError('month', 'Месяц должен быть в диапазоне от 1 до 12'))

        return errors

    @staticmethod
    def sanitize_input(text: str, max_length: int = 500) -> str:
        """Очистка пользовательского ввода"""
        if not text:
            return ""

        # Убираем лишние пробелы
        text = ' '.join(text.split())

        # Обрезаем до максимальной длины
        if len(text) > max_length:
            text = text[:max_length]

        # Заменяем опасные символы
        replacements = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
            '&': '&amp;'
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    @staticmethod
    def validate_quantity(quantity: str) -> Tuple[bool, Optional[str]]:
        """Валидация количества"""
        if not quantity:
            return True, None

        # Проверяем что это целое число
        if not quantity.isdigit():
            return False, "Количество должно быть целым числом"

        # Проверяем диапазон
        qty = int(quantity)
        if qty < 0:
            return False, "Количество не может быть отрицательным"
        if qty > 1000000:
            return False, "Количество слишком большое"

        return True, None