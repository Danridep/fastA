from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import FileResponse
import os
import uuid
import sqlite3
from datetime import datetime
import json
from typing import Dict, List, Optional
import pandas as pd

from app.database import get_db_cursor
from app.routers.models.work_order import (
    WorkOrderResult, SessionStatus, ViolationStats
)
from app.services.work_order_processor import WorkOrderProcessor
from app.utils.file_utils import save_uploaded_file, delete_file
from app.config import settings

router = APIRouter()

# Хранилище сессий
sessions = {}


@router.post("/process", response_model=WorkOrderResult)
async def process_work_orders(
        background_tasks: BackgroundTasks,
        work_types_file: UploadFile = File(None),  # Сделаем необязательным
        orders_file: UploadFile = File(...)
):
    """
    Обработка заявок на нарушения
    """
    try:
        # Генерируем ID сессии
        session_id = str(uuid.uuid4())

        # Создаем директории для файлов
        upload_dir = os.path.join(settings.WORK_ORDERS_UPLOAD_DIR, session_id)
        export_dir = os.path.join(settings.WORK_ORDERS_EXPORT_DIR, session_id)
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(export_dir, exist_ok=True)

        # Сохраняем сессию
        sessions[session_id] = {
            "session_id": session_id,
            "status": "processing",
            "progress": 0,
            "message": "Загрузка файлов...",
            "files": {},
            "stats": None,
            "regional_data": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        work_types_path = None
        orders_path = save_uploaded_file(orders_file, upload_dir)

        if work_types_file:
            work_types_path = save_uploaded_file(work_types_file, upload_dir)
            sessions[session_id]["files"]["work_types"] = work_types_path

        sessions[session_id]["files"]["orders"] = orders_path
        sessions[session_id]["progress"] = 20
        sessions[session_id]["message"] = "Файлы загружены, начинается проверка..."

        # Запускаем обработку в фоне
        background_tasks.add_task(
            process_work_orders_background,
            session_id,
            work_types_path,
            orders_path,
            export_dir
        )

        return WorkOrderResult(
            session_id=session_id,
            message="Обработка начата. Используйте /status для отслеживания прогресса.",
            created_at=datetime.now()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске обработки: {str(e)}")


def process_work_orders_background(session_id: str, work_types_path: str,
                                   orders_path: str, export_dir: str):
    """Фоновая обработка заявок"""
    try:
        sessions[session_id]["progress"] = 30
        sessions[session_id]["message"] = "Загрузка данных..."

        # Создаем процессор
        processor = WorkOrderProcessor()

        # Загружаем типы работ (из файла или БД)
        sessions[session_id]["progress"] = 40
        sessions[session_id]["message"] = "Загрузка типов работ..."

        try:
            processor.load_work_types(work_types_path)
        except Exception as e:
            sessions[session_id]["status"] = "error"
            sessions[session_id]["message"] = f"Ошибка загрузки типов работ: {str(e)}"
            sessions[session_id]["updated_at"] = datetime.now()
            save_session_to_db(session_id, sessions[session_id])
            return

        # Загружаем заявки
        sessions[session_id]["progress"] = 50
        sessions[session_id]["message"] = "Загрузка заявок..."

        try:
            processor.load_orders(orders_path)
        except Exception as e:
            sessions[session_id]["status"] = "error"
            sessions[session_id]["message"] = f"Ошибка загрузки заявок: {str(e)}"
            sessions[session_id]["updated_at"] = datetime.now()
            save_session_to_db(session_id, sessions[session_id])
            return

        # Проверяем нарушения
        sessions[session_id]["progress"] = 60
        sessions[session_id]["message"] = "Проверка нарушений..."

        try:
            stats = processor.check_violations()
        except Exception as e:
            sessions[session_id]["status"] = "error"
            sessions[session_id]["message"] = f"Ошибка проверки нарушений: {str(e)}"
            sessions[session_id]["updated_at"] = datetime.now()
            save_session_to_db(session_id, sessions[session_id])
            return

        sessions[session_id]["progress"] = 70
        sessions[session_id]["message"] = f"Найдено {stats['violation_orders']} нарушений"

        result_files = {}

        if processor.violation_orders:
            # Выделяем строки в оригинальном файле
            sessions[session_id]["progress"] = 80
            sessions[session_id]["message"] = "Выделение нарушений в файле..."
            highlight_result = processor.highlight_orders_in_file(orders_path, export_dir)
            result_files["highlighted"] = highlight_result["output_file"]

            # Сохраняем ТО заявки
            sessions[session_id]["progress"] = 85
            sessions[session_id]["message"] = "Сохранение ТО заявок..."
            to_file = processor.save_to_violations_file(export_dir)
            if to_file:
                result_files["to_violations"] = to_file

            # Группируем не-ТО заявки по регионам
            sessions[session_id]["progress"] = 90
            sessions[session_id]["message"] = "Группировка не-ТО заявок по регионам..."
            grouped_data = processor.group_non_to_violations_by_region()

            if grouped_data:
                # Сохраняем общий файл
                non_to_file = processor.save_non_to_to_file(export_dir, grouped_data)
                result_files["non_to_violations"] = non_to_file

                # Сохраняем отдельные файлы по регионам
                regional_files = processor.save_non_to_regional_files(export_dir, grouped_data)
                result_files["regional_files"] = regional_files

                # Сохраняем данные по регионам для API
                sessions[session_id]["regional_data"] = grouped_data

            # Создаем сводный отчет
            sessions[session_id]["progress"] = 95
            sessions[session_id]["message"] = "Создание отчета..."
            summary_file = processor.create_summary_report(stats, export_dir)
            result_files["summary"] = summary_file

        # Обновляем сессию
        sessions[session_id]["status"] = "completed"
        sessions[session_id]["progress"] = 100
        sessions[session_id]["message"] = "Обработка завершена успешно!"
        sessions[session_id]["files"]["result"] = result_files
        sessions[session_id]["stats"] = stats
        sessions[session_id]["updated_at"] = datetime.now()

        # Сохраняем в базу данных
        save_session_to_db(session_id, sessions[session_id])

        # Удаляем временные файлы
        if work_types_path and os.path.exists(work_types_path):
            delete_file(work_types_path)
        if orders_path and os.path.exists(orders_path):
            delete_file(orders_path)

    except Exception as e:
        sessions[session_id]["status"] = "error"
        sessions[session_id]["message"] = f"Ошибка: {str(e)}"
        sessions[session_id]["updated_at"] = datetime.now()
        save_session_to_db(session_id, sessions[session_id])
        raise

def save_session_to_db(session_id: str, session_data: dict):
    """Сохранить информацию о сессии в базу данных"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO processing_sessions 
                (session_id, status, progress, message, stats, regional_data, 
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                session_data["status"],
                session_data["progress"],
                session_data["message"],
                json.dumps(session_data["stats"]) if session_data["stats"] else None,
                json.dumps(session_data["regional_data"]) if session_data.get("regional_data") else None,
                session_data["created_at"],
                session_data["updated_at"]
            ))
    except Exception as e:
        print(f"Ошибка сохранения сессии в БД: {str(e)}")


@router.get("/status/{session_id}")
async def get_session_status(session_id: str):
    """Получить статус сессии обработки"""
    try:
        if session_id not in sessions:
            # Проверяем в базе данных
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM processing_sessions 
                    WHERE session_id = ?
                """, (session_id,))

                session_data = cursor.fetchone()

                if not session_data:
                    raise HTTPException(status_code=404, detail="Сессия не найдена")

                # Восстанавливаем данные из БД
                session_info = {
                    "session_id": session_data["session_id"],
                    "status": session_data["status"],
                    "progress": session_data["progress"],
                    "message": session_data["message"],
                    "files": {},  # Файлы не хранятся в БД
                    "stats": json.loads(session_data["stats"]) if session_data["stats"] else None,
                    "regional_data": json.loads(session_data["regional_data"]) if session_data[
                        "regional_data"] else None,
                    "created_at": datetime.fromisoformat(session_data["created_at"]) if session_data[
                        "created_at"] else None,
                    "updated_at": datetime.fromisoformat(session_data["updated_at"]) if session_data[
                        "updated_at"] else None
                }

                sessions[session_id] = session_info
                return session_info

        return sessions[session_id]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")


@router.get("/files/{session_id}")
async def get_session_files(session_id: str):
    """Получить список файлов сессии"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Сессия не найдена")

        session = sessions[session_id]

        files = []

        # Добавляем выделенный файл
        if session.get("files", {}).get("result", {}).get("highlighted"):
            files.append({
                "type": "highlighted",
                "name": "Выделенный файл с нарушениями",
                "description": "Исходный файл с заявками, где ТО заявки выделены красным, не-ТО - желтым",
                "path": session["files"]["result"]["highlighted"]
            })

        # Добавляем ТО нарушения
        if session.get("files", {}).get("result", {}).get("to_violations"):
            files.append({
                "type": "to_violations",
                "name": "ТО заявки с нарушениями",
                "description": "Список ТО заявок, в которых обнаружены нарушения",
                "path": session["files"]["result"]["to_violations"]
            })

        # Добавляем не-ТО нарушения
        if session.get("files", {}).get("result", {}).get("non_to_violations"):
            files.append({
                "type": "non_to_violations",
                "name": "Не-ТО заявки с нарушениями",
                "description": "Общий файл со всеми не-ТО заявками с нарушениями",
                "path": session["files"]["result"]["non_to_violations"]
            })

        # Добавляем региональные файлы
        if session.get("files", {}).get("result", {}).get("regional_files"):
            regional_files = session["files"]["result"]["regional_files"]
            for region, file_path in regional_files.items():
                files.append({
                    "type": "regional",
                    "name": f"Не-ТО заявки: {region}",
                    "description": f"Файл с не-ТО заявками для региона {region}",
                    "path": file_path,
                    "region": region
                })

        # Добавляем сводный отчет
        if session.get("files", {}).get("result", {}).get("summary"):
            files.append({
                "type": "summary",
                "name": "Сводный отчет",
                "description": "Полная статистика по проверке заявок",
                "path": session["files"]["result"]["summary"]
            })

        return {"session_id": session_id, "files": files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения файлов: {str(e)}")


@router.get("/download/{session_id}/{file_type}")
async def download_file(
        session_id: str,
        file_type: str,
        region: Optional[str] = None
):
    """Скачать файл результата"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Сессия не найдена")

        session = sessions[session_id]
        result_files = session.get("files", {}).get("result", {})

        file_path = None

        if file_type == "highlighted" and "highlighted" in result_files:
            file_path = result_files["highlighted"]
        elif file_type == "to_violations" and "to_violations" in result_files:
            file_path = result_files["to_violations"]
        elif file_type == "non_to_violations" and "non_to_violations" in result_files:
            file_path = result_files["non_to_violations"]
        elif file_type == "summary" and "summary" in result_files:
            file_path = result_files["summary"]
        elif file_type == "regional" and region and "regional_files" in result_files:
            file_path = result_files["regional_files"].get(region)

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Файл не найден")

        filename = os.path.basename(file_path)

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания файла: {str(e)}")


@router.get("/regional-data/{session_id}")
async def get_regional_data(session_id: str):
    """Получить региональные данные сессии"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Сессия не найдена")

        session = sessions[session_id]
        regional_data = session.get("regional_data", {})

        return {"session_id": session_id, "regional_data": regional_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения региональных данных: {str(e)}")


@router.get("/copy-text/{session_id}/{region}")
async def get_copy_text(session_id: str, region: str):
    """Получить текст для копирования по региону"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Сессия не найдена")

        session = sessions[session_id]
        regional_data = session.get("regional_data", {})

        if region not in regional_data:
            raise HTTPException(status_code=404, detail="Регион не найден")

        orders = regional_data[region]

        # Форматируем текст как в файлах
        text_lines = [f"{region.upper()}:", "Привет, не списаны материалы за", ""]

        # Получаем ключ для номера заявки (может быть разным)
        for order in orders:
            order_number = None
            # Пробуем разные возможные ключи
            for key in ['Номер заявки', 'Номер_заявки']:
                if key in order:
                    order_number = order[key]
                    break

            if order_number:
                city = order.get('Город', 'Не указан')
                executor = order.get('Исполнитель', 'Не указан')
                text_lines.append(f"{order_number} - {city} - {executor}")

        text_lines.append(f"\nВсего: {len(orders)} заявок")
        text_lines.append("\n" + "=" * 60)

        text = "\n".join(text_lines)

        return {
            "region": region,
            "orders_count": len(orders),
            "text": text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения текста: {str(e)}")


# ====== API для управления типами работ ======

@router.get("/work-types/list")
async def get_work_types_list(
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        is_to: Optional[str] = None
):
    """Получить список типов работ с пагинацией"""
    try:
        with get_db_cursor() as cursor:
            # Базовый запрос
            base_query = """
                SELECT 
                    id,
                    name as "Наименование",
                    normalized_name as "Нормализованное имя",
                    has_writeoff_materials as "Списание материалов",
                    has_writeoff_equipment as "Списание оборудования",
                    demount_lines_count as "Строк демонтажа",
                    is_to as "ТО",
                    created_at as "Дата создания",
                    updated_at as "Дата обновления"
                FROM work_types 
                WHERE 1=1
            """

            count_query = "SELECT COUNT(*) as total FROM work_types WHERE 1=1"
            params = []

            # Фильтр по поиску
            if search and search.strip():
                base_query += " AND (name LIKE ? OR normalized_name LIKE ?)"
                count_query += " AND (name LIKE ? OR normalized_name LIKE ?)"
                search_term = f"%{search}%"
                params.extend([search_term, search_term])

            # Фильтр по ТО/не-ТО
            if is_to == "to":
                base_query += " AND is_to = 1"
                count_query += " AND is_to = 1"
            elif is_to == "non_to":
                base_query += " AND is_to = 0"
                count_query += " AND is_to = 0"

            # Получаем общее количество
            cursor.execute(count_query, params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0

            # Добавляем сортировку и пагинацию
            base_query += " ORDER BY name LIMIT ? OFFSET ?"
            params.extend([per_page, (page - 1) * per_page])

            cursor.execute(base_query, params)
            work_types = cursor.fetchall()

            # Получаем статистику
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(is_to) as to_count,
                    SUM(has_writeoff_materials) as materials_count,
                    SUM(has_writeoff_equipment) as equipment_count,
                    SUM(demount_lines_count) as demount_count,
                    COUNT(DISTINCT normalized_name) as unique_count
                FROM work_types
            """)

            stats = cursor.fetchone()

            # Получаем распределение по категориям
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN is_to = 1 THEN 'ТО'
                        ELSE 'Не-ТО'
                    END as category,
                    COUNT(*) as count
                FROM work_types
                GROUP BY is_to
                ORDER BY count DESC
            """)

            by_category = cursor.fetchall()

            # Получаем последние добавленные типы
            cursor.execute("""
                SELECT name, created_at 
                FROM work_types 
                ORDER BY created_at DESC 
                LIMIT 5
            """)

            recent_added = cursor.fetchall()

            stats_data = {
                "total": stats['total'] if stats else 0,
                "to_count": stats['to_count'] if stats else 0,
                "materials_count": stats['materials_count'] if stats else 0,
                "equipment_count": stats['equipment_count'] if stats else 0,
                "demount_count": stats['demount_count'] if stats else 0,
                "unique_count": stats['unique_count'] if stats else 0,
                "by_category": by_category,
                "recent_added": recent_added
            }

            return {
                "success": True,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
                "data": work_types,
                "stats": stats_data
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки списка типов работ: {str(e)}")


@router.get("/work-types")
async def get_work_types(
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        is_to: Optional[int] = None
):
    """Получить все типы работ из базы данных с пагинацией"""
    try:
        with get_db_cursor() as cursor:
            # Строим базовый запрос
            base_query = "SELECT * FROM work_types WHERE 1=1"
            count_query = "SELECT COUNT(*) as total FROM work_types WHERE 1=1"
            params = []

            # Добавляем фильтры
            if search:
                base_query += " AND (name LIKE ? OR normalized_name LIKE ?)"
                count_query += " AND (name LIKE ? OR normalized_name LIKE ?)"
                search_term = f"%{search}%"
                params.extend([search_term, search_term])

            if is_to is not None:
                base_query += " AND is_to = ?"
                count_query += " AND is_to = ?"
                params.append(is_to)

            # Получаем общее количество
            cursor.execute(count_query, params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0

            # Добавляем сортировку и пагинацию
            base_query += " ORDER BY name LIMIT ? OFFSET ?"
            params.extend([per_page, (page - 1) * per_page])

            cursor.execute(base_query, params)
            work_types = cursor.fetchall()

            # Получаем статистику
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_count,
                    SUM(is_to) as to_count,
                    SUM(has_writeoff_materials) as materials_count,
                    SUM(has_writeoff_equipment) as equipment_count,
                    SUM(demount_lines_count) as demount_count
                FROM work_types
            """)
            stats = cursor.fetchone()

            return {
                "success": True,
                "total": total,
                "page": page,
                "pages": (total + per_page - 1) // per_page,
                "per_page": per_page,
                "stats": stats,
                "data": work_types
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки типов работ: {str(e)}")


@router.get("/work-types/{work_type_id}")
async def get_work_type(work_type_id: int):
    """Получить конкретный тип работ"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM work_types WHERE id = ?
            """, (work_type_id,))

            work_type = cursor.fetchone()

            if not work_type:
                raise HTTPException(status_code=404, detail="Тип работ не найден")

            return {
                "success": True,
                "data": work_type
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки типа работ: {str(e)}")


@router.post("/work-types/upload")
async def upload_work_types(file: UploadFile = File(...)):
    """Загрузить типы работ из файла Excel"""
    try:
        # Проверяем формат файла
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Файл должен быть в формате Excel (.xlsx или .xls)")

        # Сохраняем файл временно
        upload_dir = os.path.join(settings.WORK_ORDERS_UPLOAD_DIR, "temp")
        os.makedirs(upload_dir, exist_ok=True)

        file_path = save_uploaded_file(file, upload_dir)

        try:
            # Загружаем и сохраняем в БД
            processor = WorkOrderProcessor()

            # Читаем файл
            df = pd.read_excel(file_path)

            # Проверяем обязательные колонки
            required_columns = ['Наименование', 'Наличие списания материалов',
                                'Наличие списания оборудования', 'Количество строк демонтажа', 'ТО']

            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"В файле отсутствуют обязательные колонки: {', '.join(missing_columns)}"
                )

            # Загружаем типы работ
            processor.load_work_types(file_path)

            # Получаем статистику после загрузки
            with get_db_cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM work_types")
                count_result = cursor.fetchone()
                uploaded_count = count_result['count'] if count_result else 0

            return {
                "success": True,
                "message": f"Типы работ успешно загружены в базу данных",
                "uploaded_count": uploaded_count
            }

        finally:
            # Удаляем временный файл
            if os.path.exists(file_path):
                delete_file(file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки типов работ: {str(e)}")


@router.post("/work-types")
async def create_work_type(
        name: str,
        has_writeoff_materials: int = 0,
        has_writeoff_equipment: int = 0,
        demount_lines_count: int = 0,
        is_to: int = 0
):
    """Создать новый тип работ"""
    try:
        with get_db_cursor() as cursor:
            # Нормализуем имя
            processor = WorkOrderProcessor()
            normalized_name = processor.normalize_text(name)

            cursor.execute("""
                INSERT INTO work_types 
                (name, normalized_name, has_writeoff_materials, has_writeoff_equipment, 
                 demount_lines_count, is_to, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (name, normalized_name, has_writeoff_materials, has_writeoff_equipment,
                  demount_lines_count, is_to))

            work_type_id = cursor.lastrowid

            return {
                "success": True,
                "message": "Тип работ создан",
                "id": work_type_id
            }

    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Тип работ с таким названием уже существует")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания типа работ: {str(e)}")


@router.put("/work-types/{work_type_id}")
async def update_work_type(
        work_type_id: int,
        name: Optional[str] = None,
        has_writeoff_materials: Optional[int] = None,
        has_writeoff_equipment: Optional[int] = None,
        demount_lines_count: Optional[int] = None,
        is_to: Optional[int] = None
):
    """Обновить тип работ"""
    try:
        with get_db_cursor() as cursor:
            # Проверяем существование
            cursor.execute("SELECT * FROM work_types WHERE id = ?", (work_type_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Тип работ не найден")

            # Строим запрос обновления
            update_fields = []
            params = []

            if name is not None:
                processor = WorkOrderProcessor()
                normalized_name = processor.normalize_text(name)
                update_fields.append("name = ?")
                update_fields.append("normalized_name = ?")
                params.extend([name, normalized_name])

            if has_writeoff_materials is not None:
                update_fields.append("has_writeoff_materials = ?")
                params.append(has_writeoff_materials)

            if has_writeoff_equipment is not None:
                update_fields.append("has_writeoff_equipment = ?")
                params.append(has_writeoff_equipment)

            if demount_lines_count is not None:
                update_fields.append("demount_lines_count = ?")
                params.append(demount_lines_count)

            if is_to is not None:
                update_fields.append("is_to = ?")
                params.append(is_to)

            if not update_fields:
                raise HTTPException(status_code=400, detail="Нет данных для обновления")

            # Добавляем обновление времени
            update_fields.append("updated_at = CURRENT_TIMESTAMP")

            # Добавляем ID в параметры
            params.append(work_type_id)

            query = f"UPDATE work_types SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, params)

            return {
                "success": True,
                "message": "Тип работ обновлен"
            }

    except HTTPException:
        raise
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Тип работ с таким названием уже существует")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления типа работ: {str(e)}")


@router.delete("/work-types/{work_type_id}")
async def delete_work_type(work_type_id: int):
    """Удалить тип работ"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM work_types WHERE id = ?", (work_type_id,))

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Тип работ не найден")

            return {
                "success": True,
                "message": "Тип работ удален"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления типа работ: {str(e)}")


@router.get("/work-types/export")
async def export_work_types():
    """Экспортировать типы работ в Excel файл"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    name as 'Наименование',
                    has_writeoff_materials as 'Наличие списания материалов',
                    has_writeoff_equipment as 'Наличие списания оборудования',
                    demount_lines_count as 'Количество строк демонтажа',
                    is_to as 'ТО'
                FROM work_types
                ORDER BY name
            """)

            work_types = cursor.fetchall()

            if not work_types:
                raise HTTPException(status_code=404, detail="Нет данных для экспорта")

            # Создаем DataFrame
            df = pd.DataFrame(work_types)

            # Создаем временный файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir = os.path.join(settings.EXPORT_DIR, "work_types")
            os.makedirs(export_dir, exist_ok=True)

            output_file = os.path.join(export_dir, f"work_types_{timestamp}.xlsx")
            df.to_excel(output_file, index=False)

            # Возвращаем файл
            return FileResponse(
                path=output_file,
                filename=f"work_types_{timestamp}.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта типов работ: {str(e)}")


@router.get("/work-types/stats")
async def get_work_types_stats():
    """Получить статистику по типам работ"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(is_to) as to_count,
                    SUM(has_writeoff_materials) as materials_count,
                    SUM(has_writeoff_equipment) as equipment_count,
                    SUM(demount_lines_count) as demount_count,
                    COUNT(DISTINCT normalized_name) as unique_count
                FROM work_types
            """)

            stats = cursor.fetchone()

            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN is_to = 1 THEN 'ТО'
                        ELSE 'Не-ТО'
                    END as category,
                    COUNT(*) as count
                FROM work_types
                GROUP BY is_to
            """)

            by_category = cursor.fetchall()

            return {
                "success": True,
                "stats": stats,
                "by_category": by_category
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


# ====== Endpoints для веб-интерфейса управления типами работ ======

@router.get("/work-types/ui/list")
async def get_work_types_for_ui(
        page: int = 1,
        limit: int = 20,
        search: str = "",
        is_to: str = "all"
):
    """Получить типы работ для веб-интерфейса"""
    try:
        with get_db_cursor() as cursor:
            # Базовый запрос
            query = """
                SELECT 
                    id,
                    name,
                    has_writeoff_materials,
                    has_writeoff_equipment,
                    demount_lines_count,
                    is_to,
                    created_at,
                    updated_at
                FROM work_types 
                WHERE 1=1
            """

            count_query = "SELECT COUNT(*) as total FROM work_types WHERE 1=1"
            params = []

            # Фильтр по поиску
            if search:
                query += " AND (name LIKE ? OR normalized_name LIKE ?)"
                count_query += " AND (name LIKE ? OR normalized_name LIKE ?)"
                search_term = f"%{search}%"
                params.extend([search_term, search_term])

            # Фильтр по ТО/не-ТО
            if is_to == "to":
                query += " AND is_to = 1"
                count_query += " AND is_to = 1"
            elif is_to == "non_to":
                query += " AND is_to = 0"
                count_query += " AND is_to = 0"

            # Получаем общее количество
            cursor.execute(count_query, params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0

            # Добавляем сортировку и пагинацию
            query += " ORDER BY name LIMIT ? OFFSET ?"
            params.extend([limit, (page - 1) * limit])

            cursor.execute(query, params)
            work_types = cursor.fetchall()

            return {
                "success": True,
                "data": work_types,
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit if limit > 0 else 1
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки данных: {str(e)}")


@router.post("/work-types/ui/create")
async def create_work_type_ui(
        name: str,
        has_writeoff_materials: int = 0,
        has_writeoff_equipment: int = 0,
        demount_lines_count: int = 0,
        is_to: int = 0
):
    """Создать тип работ через UI"""
    try:
        with get_db_cursor() as cursor:
            # Нормализуем имя
            processor = WorkOrderProcessor()
            normalized_name = processor.normalize_text(name)

            # Проверяем уникальность
            cursor.execute("SELECT id FROM work_types WHERE normalized_name = ?", (normalized_name,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Тип работ с таким названием уже существует")

            cursor.execute("""
                INSERT INTO work_types 
                (name, normalized_name, has_writeoff_materials, has_writeoff_equipment, 
                 demount_lines_count, is_to, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (name, normalized_name, has_writeoff_materials, has_writeoff_equipment,
                  demount_lines_count, is_to))

            work_type_id = cursor.lastrowid

            return {
                "success": True,
                "message": "Тип работ успешно создан",
                "id": work_type_id
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания типа работ: {str(e)}")


@router.put("/work-types/ui/update/{work_type_id}")
async def update_work_type_ui(
        work_type_id: int,
        name: Optional[str] = None,
        has_writeoff_materials: Optional[int] = None,
        has_writeoff_equipment: Optional[int] = None,
        demount_lines_count: Optional[int] = None,
        is_to: Optional[int] = None
):
    """Обновить тип работ через UI"""
    try:
        with get_db_cursor() as cursor:
            # Проверяем существование
            cursor.execute("SELECT * FROM work_types WHERE id = ?", (work_type_id,))
            existing = cursor.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Тип работ не найден")

            # Собираем данные для обновления
            update_data = {
                "name": name if name is not None else existing["name"],
                "has_writeoff_materials": has_writeoff_materials if has_writeoff_materials is not None else existing[
                    "has_writeoff_materials"],
                "has_writeoff_equipment": has_writeoff_equipment if has_writeoff_equipment is not None else existing[
                    "has_writeoff_equipment"],
                "demount_lines_count": demount_lines_count if demount_lines_count is not None else existing[
                    "demount_lines_count"],
                "is_to": is_to if is_to is not None else existing["is_to"]
            }

            # Нормализуем имя если оно изменилось
            if name is not None and name != existing["name"]:
                processor = WorkOrderProcessor()
                update_data["normalized_name"] = processor.normalize_text(name)
            else:
                update_data["normalized_name"] = existing["normalized_name"]

            # Проверяем уникальность (если имя изменилось)
            if name is not None and name != existing["name"]:
                cursor.execute("SELECT id FROM work_types WHERE normalized_name = ? AND id != ?",
                               (update_data["normalized_name"], work_type_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Тип работ с таким названием уже существует")

            # Обновляем запись
            cursor.execute("""
                UPDATE work_types SET 
                    name = ?,
                    normalized_name = ?,
                    has_writeoff_materials = ?,
                    has_writeoff_equipment = ?,
                    demount_lines_count = ?,
                    is_to = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                update_data["name"],
                update_data["normalized_name"],
                update_data["has_writeoff_materials"],
                update_data["has_writeoff_equipment"],
                update_data["demount_lines_count"],
                update_data["is_to"],
                work_type_id
            ))

            return {
                "success": True,
                "message": "Тип работ успешно обновлен"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления типа работ: {str(e)}")


@router.delete("/work-types/ui/delete/{work_type_id}")
async def delete_work_type_ui(work_type_id: int):
    """Удалить тип работ через UI"""
    try:
        with get_db_cursor() as cursor:
            # Проверяем существование
            cursor.execute("SELECT id FROM work_types WHERE id = ?", (work_type_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Тип работ не найден")

            # Удаляем запись
            cursor.execute("DELETE FROM work_types WHERE id = ?", (work_type_id,))

            return {
                "success": True,
                "message": "Тип работ успешно удален"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления типа работ: {str(e)}")