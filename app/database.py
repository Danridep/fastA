import sqlite3
import json
import os
import traceback
from contextlib import contextmanager
from typing import Generator
from app.config import settings


def get_db_path() -> str:
    """Получить путь к базе данных"""
    db_url = settings.DATABASE_URL

    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "", 1)
    elif db_url.startswith("sqlite://"):
        path = db_url.replace("sqlite://", "", 1)
    else:
        path = db_url

    return os.path.abspath(path)


def init_database():
    """Инициализация базы данных"""
    db_path = get_db_path()

    print(f"=== Инициализация базы данных ===")
    print(f"Путь к БД: {db_path}")

    # Создаем директорию если ее нет
    dir_path = os.path.dirname(db_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        print(f"Создана директория: {dir_path}")

    # Проверяем, существует ли файл и является ли он валидной SQLite базой
    file_exists = os.path.exists(db_path)

    if file_exists:
        print(f"Файл существует ({os.path.getsize(db_path)} байт)")
        # Проверяем, является ли файл валидной SQLite базой
        try:
            test_conn = sqlite3.connect(db_path)
            test_cursor = test_conn.cursor()
            test_cursor.execute("SELECT 1")
            test_conn.close()
            print("Файл является валидной SQLite базой данных")
        except sqlite3.Error as e:
            print(f"Файл поврежден или не является SQLite базой: {e}")
            # Удаляем поврежденный файл
            os.remove(db_path)
            print("Удален поврежденный файл")
            file_exists = False
    else:
        print("Файл не существует, будет создан новый")

    # Создаем или пересоздаем базу данных
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Включаем поддержку внешних ключей
        cursor.execute("PRAGMA foreign_keys = ON")

        print("Подключение к базе данных установлено успешно")

        # Создаем таблицы
        print("Создание таблиц...")
        # Таблица processing_sessions (добавляем)
        cursor.execute("""
                   CREATE TABLE IF NOT EXISTS processing_sessions (
                       session_id TEXT PRIMARY KEY,
                       status TEXT NOT NULL,
                       progress INTEGER DEFAULT 0,
                       message TEXT,
                       stats TEXT,
                       regional_data TEXT,
                       created_at TIMESTAMP,
                       updated_at TIMESTAMP
                   )
               """)

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                full_name TEXT,
                hashed_password TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("- Таблица 'users' создана/проверена")
        # Таблица сессий обработки заявок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_order_sessions
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                message TEXT,
                files_data TEXT,
                stats_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("- Таблица 'work_order_sessions' создана/проверена")
        # Таблица типов работ
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_types
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                normalized_name TEXT,
                has_writeoff_materials INTEGER DEFAULT 0,
                has_writeoff_equipment INTEGER DEFAULT 0,
                demount_lines_count INTEGER DEFAULT 0,
                is_to INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("- Таблица 'work_types' создана/проверена")

        # Создаем индекс для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_work_types_normalized 
            ON work_types(normalized_name)
        ''')
        print("- Индекс 'idx_work_types_normalized' создан/проверен")
        # Таблица номенклатуры
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nomenclature
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK (type IN ('КЦ', 'Расходники')),
                name TEXT NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("- Таблица 'nomenclature' создана/проверена")

        # Таблица адресов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS addresses
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                np_number TEXT,
                address TEXT NOT NULL,
                contact_person TEXT NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(np_number, address)
            )
        ''')
        print("- Таблица 'addresses' создана/проверена")

        # Таблица шаблонов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('КЦ', 'Расходники')),
                headers TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("- Таблица 'templates' создана/проверена")

        # Таблица сессий заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_sessions
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                order_type TEXT NOT NULL CHECK (order_type IN ('КЦ', 'Расходники')),
                data TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        ''')
        print("- Таблица 'order_sessions' создана/проверена")

        # Таблица истории анализов Pandas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                result_filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("- Таблица 'analysis_history' создана/проверена")

        # Таблица для истории сравнений файлов (particle)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS particle_history
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file1_name TEXT NOT NULL,
                file2_name TEXT NOT NULL,
                total1 REAL,
                total2 REAL,
                comparison TEXT NOT NULL,
                minus_count1 INTEGER DEFAULT 0,
                minus_count2 INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        print("- Таблица 'particle_history' создана/проверена")

        conn.commit()
        print("Таблицы успешно созданы/проверены")

        # Добавляем тестовые данные
        print("Добавление тестовых данных...")
        add_sample_data(cursor, conn)

        conn.close()
        print(f"✅ База данных успешно инициализирована: {db_path}")
        print(f"Размер файла: {os.path.getsize(db_path)} байт")

    except Exception as e:
        print(f"❌ Критическая ошибка при инициализации БД: {e}")
        traceback.print_exc()
        raise


@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Контекстный менеджер для получения курсора БД"""
    conn = None
    try:
        # Проверяем и инициализируем БД если нужно
        db_path = get_db_path()
        if not os.path.exists(db_path):
            print("База данных не найдена, инициализация...")
            init_database()

        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = dict_factory

        # Включаем поддержку внешних ключей
        conn.execute("PRAGMA foreign_keys = ON")

        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        print(f"Database error in get_db_cursor: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def dict_factory(cursor, row):
    """Преобразование строки в словарь"""
    if cursor.description is None:
        return row

    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def add_sample_data(cursor, conn):
    """Добавление тестовых данных"""
    # Проверяем есть ли данные в номенклатуре
    cursor.execute("SELECT COUNT(*) FROM nomenclature")
    if cursor.fetchone()[0] == 0:
        add_sample_nomenclature(cursor)

    # Проверяем адреса
    cursor.execute("SELECT COUNT(*) FROM addresses")
    if cursor.fetchone()[0] == 0:
        add_sample_addresses(cursor)

    # Проверяем шаблоны
    cursor.execute("SELECT COUNT(*) FROM templates")
    if cursor.fetchone()[0] == 0:
        add_sample_templates(cursor)

    conn.commit()


def add_sample_nomenclature(cursor):
    """Добавить тестовую номенклатуру"""
    kc_items = [
        ("КЦ", "Кабель UTP 4х2", ""),
        ("КЦ", "Конектор RJ-45 з хвостовиком", ""),
    ]

    cursor.executemany(
        "INSERT INTO nomenclature (type, name, comment) VALUES (?, ?, ?)",
        kc_items
    )

    consumables = [
        ("Расходники", "З'єднувач Scotchlock", ""),
        ("Расходники", "Ізолента", ""),
        ("Расходники", "Кабель 4х2", ""),
        ("Расходники", "Клипса, для круглого кабеля 6 мм", ""),
        ("Расходники", "Клипса 4мм", "Квадратная для GPON"),
        ("Расходники", "Конектор RJ-45", ""),
        ("Расходники", "Стяжка, 3,5х150 мм(черного цвета)", ""),
        ("Расходники", "Термоусаджувальна трубка, 18-20мм", ""),
        ("Расходники", "Муфта соеденительная RJ-45", ""),
        ("Расходники", "Кабель 4х2", "Кабель КВП UTP (4*2*0.5) 4p 24 AWG, Merlion, (CCA), 305м, black"),
    ]

    cursor.executemany(
        "INSERT INTO nomenclature (type, name, comment) VALUES (?, ?, ?)",
        consumables
    )


def add_sample_addresses(cursor):
    """Добавить тестовые адреса"""
    addresses = [
        ("16", "Кропивницкий, Маланюка, 1А", "Чорний Александр Викторович", "(067)5211993"),
        ("15", "Кременчук, просп. Свободы 78А", "Черніков Олександр Олександрович", "(099)9699884"),
        ("5", "Полтава, Нечуя Левицького, 10А", "Доля Александр Алексеевич", "(066)0986851"),
        ("42", "Николаев, ул.Пограничная 165", "Босий Евгений Михайлович", "(098)1144389"),
        ("10", "Одеса, пр. Добровольского, 103, каб.№1", "Савченко Олександр Петрович", "(097)0920788"),
        ("74", "Одеса, ул. Академика Филатова 76", "Косенко Анатолій Юрійович", "(099)5015470"),
        ("8", "Черкассы, ул. Надпільна 248А", "Тюленев Эдуард Геннадьевич", "(066)1897288"),
        ("1", "Вознесенск, Київська, 273Д", "Новохацький Сергій Олексійович", "(096)5633532"),
    ]

    cursor.executemany(
        "INSERT INTO addresses (np_number, address, contact_person, phone) VALUES (?, ?, ?, ?)",
        addresses
    )


def add_sample_templates(cursor):
    """Добавить тестовые шаблоны"""
    kc_headers = ["Наименов ТМЦ", "Кол-во", "Адрес отгрузки", "ФИО получателя", "Телефон"]
    consumables_headers = ["Наименов ТМЦ", "Кол-во", "НП", "Адрес отгрузки", "ФИО получателя", "Телефон", "Комментарий"]

    cursor.execute(
        "INSERT INTO templates (name, type, headers) VALUES (?, ?, ?)",
        ("Шаблон КЦ", "КЦ", json.dumps(kc_headers, ensure_ascii=False))
    )

    cursor.execute(
        "INSERT INTO templates (name, type, headers) VALUES (?, ?, ?)",
        ("Шаблон заказа расходников", "Расходники", json.dumps(consumables_headers, ensure_ascii=False))
    )


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Контекстный менеджер для получения соединения с БД"""
    conn = None
    try:
        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        conn.row_factory = dict_factory
        yield conn
    finally:
        if conn:
            conn.close()


def get_db_connection():
    """Получить соединение с БД"""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = dict_factory
    return conn