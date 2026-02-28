import sqlite3
import json
import os
import traceback
from contextlib import contextmanager
from typing import Generator
from app.config import settings


def get_db_path() -> str:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "", 1)
    elif db_url.startswith("sqlite://"):
        path = db_url.replace("sqlite://", "", 1)
    else:
        path = db_url
    return os.path.abspath(path)


def init_database():
    db_path = get_db_path()
    print(f"=== Инициализация базы данных ===")
    print(f"Путь к БД: {db_path}")

    dir_path = os.path.dirname(db_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    if os.path.exists(db_path):
        try:
            test_conn = sqlite3.connect(db_path)
            test_conn.cursor().execute("SELECT 1")
            test_conn.close()
        except sqlite3.Error as e:
            print(f"Файл поврежден: {e}")
            os.remove(db_path)

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_sessions (
                session_id TEXT PRIMARY KEY, status TEXT NOT NULL,
                progress INTEGER DEFAULT 0, message TEXT, stats TEXT,
                regional_data TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
            )""")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE, full_name TEXT, hashed_password TEXT,
                is_active BOOLEAN DEFAULT 1, is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_order_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL, progress INTEGER DEFAULT 0, message TEXT,
                files_data TEXT, stats_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                normalized_name TEXT, has_writeoff_materials INTEGER DEFAULT 0,
                has_writeoff_equipment INTEGER DEFAULT 0, demount_lines_count INTEGER DEFAULT 0,
                is_to INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_work_types_normalized ON work_types(normalized_name)''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nomenclature (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK (type IN ('КЦ', 'Расходники')),
                name TEXT NOT NULL, comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT, np_number TEXT,
                address TEXT NOT NULL, contact_person TEXT NOT NULL, phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(np_number, address)
            )''')

        # address_mapping: JSON {"addr_id": [nom_id, ...], ...}
        # Маппинг хранится внутри шаблона
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('КЦ', 'Расходники')),
                headers TEXT,
                address_mapping TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

        # Миграция для существующих БД
        try:
            cursor.execute("ALTER TABLE templates ADD COLUMN address_mapping TEXT DEFAULT '{}'")
            print("- Колонка address_mapping добавлена в templates (миграция)")
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL UNIQUE,
                order_type TEXT NOT NULL CHECK (order_type IN ('КЦ', 'Расходники')),
                data TEXT, user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, month INTEGER NOT NULL,
                original_filename TEXT NOT NULL, result_filename TEXT NOT NULL,
                file_size INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS particle_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file1_name TEXT NOT NULL, file2_name TEXT NOT NULL,
                total1 REAL, total2 REAL, comparison TEXT NOT NULL,
                minus_count1 INTEGER DEFAULT 0, minus_count2 INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )''')

        conn.commit()
        add_sample_data(cursor, conn)
        conn.close()
        print(f"✅ База данных успешно инициализирована: {db_path}")

    except Exception as e:
        print(f"❌ Критическая ошибка при инициализации БД: {e}")
        traceback.print_exc()
        raise


@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    conn = None
    try:
        db_path = get_db_path()
        if not os.path.exists(db_path):
            init_database()
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = dict_factory
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def dict_factory(cursor, row):
    if cursor.description is None:
        return row
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def add_sample_data(cursor, conn):
    cursor.execute("SELECT COUNT(*) as c FROM nomenclature")
    if cursor.fetchone()["c"] == 0:
        add_sample_nomenclature(cursor)
    cursor.execute("SELECT COUNT(*) as c FROM addresses")
    if cursor.fetchone()["c"] == 0:
        add_sample_addresses(cursor)
    cursor.execute("SELECT COUNT(*) as c FROM templates")
    if cursor.fetchone()["c"] == 0:
        add_sample_templates(cursor)
    conn.commit()


def add_sample_nomenclature(cursor):
    cursor.executemany("INSERT INTO nomenclature (type, name, comment) VALUES (?, ?, ?)", [
        ("КЦ", "Кабель UTP 4х2", ""),
        ("КЦ", "Конектор RJ-45 з хвостовиком", ""),
        ("Расходники", "З'єднувач Scotchlock", ""),
        ("Расходники", "Ізолента", ""),
        ("Расходники", "Кабель 4х2", ""),
        ("Расходники", "Клипса, для круглого кабеля 6 мм", ""),
        ("Расходники", "Клипса 4мм", "Квадратная для GPON"),
        ("Расходники", "Конектор RJ-45", ""),
        ("Расходники", "Стяжка, 3,5х150 мм(черного цвета)", ""),
        ("Расходники", "Термоусаджувальна трубка, 18-20мм", ""),
        ("Расходники", "Муфта соеденительная RJ-45", ""),
    ])


def add_sample_addresses(cursor):
    cursor.executemany("INSERT INTO addresses (np_number, address, contact_person, phone) VALUES (?, ?, ?, ?)", [
        ("16", "Кропивницкий, Маланюка, 1А",            "Чорний Александр Викторович",          "(067)5211993"),
        ("15", "Кременчук, просп. Свободы 78А",          "Черніков Олександр Олександрович",      "(099)9699884"),
        ("5",  "Полтава, Нечуя Левицького, 10А",         "Доля Александр Алексеевич",             "(066)0986851"),
        ("42", "Николаев, ул.Пограничная 165",           "Босий Евгений Михайлович",              "(098)1144389"),
        ("10", "Одеса, пр. Добровольского, 103, каб.№1", "Савченко Олександр Петрович",           "(097)0920788"),
        ("74", "Одеса, ул. Академика Филатова 76",       "Косенко Анатолій Юрійович",             "(099)5015470"),
        ("8",  "Черкассы, ул. Надпільна 248А",           "Тюленев Эдуард Геннадьевич",            "(066)1897288"),
        ("1",  "Вознесенск, Київська, 273Д",             "Новохацький Сергій Олексійович",        "(096)5633532"),
    ])


def add_sample_templates(cursor):
    cursor.execute(
        "INSERT INTO templates (name, type, headers, address_mapping) VALUES (?, ?, ?, ?)",
        ("Шаблон КЦ", "КЦ",
         json.dumps(["Наименов ТМЦ","Кол-во","Адрес отгрузки","ФИО получателя","Телефон"], ensure_ascii=False),
         "{}"))
    cursor.execute(
        "INSERT INTO templates (name, type, headers, address_mapping) VALUES (?, ?, ?, ?)",
        ("Шаблон заказа расходников", "Расходники",
         json.dumps(["Наименов ТМЦ","Кол-во","НП","Адрес отгрузки","ФИО получателя","Телефон","Комментарий"], ensure_ascii=False),
         "{}"))


@contextmanager
def get_db_connection() -> Generator[sqlite3.Cursor, None, None]:
    conn = None
    try:
        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        conn.row_factory = dict_factory
        yield conn
    finally:
        if conn:
            conn.close()