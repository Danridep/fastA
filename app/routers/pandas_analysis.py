from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response  # Добавьте этот импорт
from typing import Optional
import os
from datetime import datetime
from app.database import get_db_cursor
from app.models import (
    PandasAnalysisRequest, AnalysisHistory,
    BaseResponse, PaginatedResponse
)
from app.services.pandas_service import analyze_excel_data
from app.utils.file_utils import save_uploaded_file, delete_file
from app.config import settings

router = APIRouter()


@router.post("/analyze")
async def pandas_analyze(
        month: int = Form(...),
        file: UploadFile = File(...)
):
    """
    Анализ данных с помощью Pandas
    """
    try:
        print(f"=== Начало анализа ===")
        print(f"Месяц: {month}, Файл: {file.filename}")

        # Валидация месяца
        if not 1 <= month <= 12:
            raise HTTPException(status_code=400, detail="Месяц должен быть в диапазоне 1-12")

        # Проверка расширения файла
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Файл должен быть в формате Excel")

        # Создаем директории если их нет
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)

        print(f"Директории созданы: UPLOAD={settings.UPLOAD_DIR}, EXPORT={settings.EXPORT_DIR}")

        # Сохраняем загруженный файл
        file_path = save_uploaded_file(file, settings.UPLOAD_DIR)
        print(f"Файл сохранен: {file_path}")

        try:
            # Анализируем данные
            print(f"Запуск анализа excel...")
            result_df = analyze_excel_data(file_path, month)

            if result_df is None or result_df.empty:
                raise HTTPException(status_code=400, detail=f"Нет данных за {month} месяц или ошибка при анализе")

            print(f"Анализ завершен, строк в результате: {len(result_df)}")

            # Сохраняем результат
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_filename = f"analysis_month_{month}_{timestamp}.xlsx"
            result_path = os.path.join(settings.EXPORT_DIR, result_filename)

            result_df.to_excel(result_path, index=False)
            print(f"Результат сохранен: {result_path}")

            # Сохраняем в историю
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO analysis_history 
                    (month, original_filename, result_filename, file_size)
                    VALUES (?, ?, ?, ?)
                    """,
                    (month, file.filename, result_filename, os.path.getsize(result_path))
                )

            # Возвращаем файл
            with open(result_path, 'rb') as f:
                file_content = f.read()

            return Response(
                content=file_content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={result_filename}"}
            )

        except HTTPException:
            raise
        except Exception as e:
            print(f"Ошибка в процессе анализа: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка в процессе анализа: {str(e)}")
        finally:
            # Удаляем загруженный файл
            if os.path.exists(file_path):
                delete_file(file_path)
                print(f"Временный файл удален: {file_path}")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Общая ошибка анализа: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе: {str(e)}")


@router.get("/history", response_model=PaginatedResponse)
async def get_analysis_history(
        page: int = 1,
        per_page: int = 20,
        month: Optional[int] = None
):
    """
    Получить историю анализов
    """
    try:
        with get_db_cursor() as cursor:
            # Строим запрос с фильтрами
            query = "SELECT * FROM analysis_history WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM analysis_history WHERE 1=1"
            params = []

            if month:
                query += " AND month = ?"
                count_query += " AND month = ?"
                params.append(month)

            # Получаем общее количество
            cursor.execute(count_query, params)
            result = cursor.fetchone()
            total = result["count"] if result else 0

            # Пагинация
            offset = (page - 1) * per_page
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])

            cursor.execute(query, params)
            history = cursor.fetchall()

            return PaginatedResponse(
                total=total,
                page=page,
                pages=(total + per_page - 1) // per_page,
                per_page=per_page,
                data=history
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки истории: {str(e)}")


@router.get("/history/{history_id}", response_model=BaseResponse)
async def get_analysis_history_item(history_id: int):
    """
    Получить детали анализа из истории
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analysis_history WHERE id = ?",
                (history_id,)
            )
            history_item = cursor.fetchone()

            if not history_item:
                raise HTTPException(status_code=404, detail="Запись истории не найдена")

            # Проверяем существование файла
            result_path = os.path.join(settings.EXPORT_DIR, history_item["result_filename"])
            file_exists = os.path.exists(result_path)

            history_item["file_exists"] = file_exists
            history_item["result_path"] = result_path if file_exists else None

            return BaseResponse(data=history_item)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки истории: {str(e)}")


@router.delete("/history/{history_id}", response_model=BaseResponse)
async def delete_analysis_history_item(history_id: int):
    """
    Удалить запись из истории анализов
    """
    try:
        with get_db_cursor() as cursor:
            # Получаем информацию о файле
            cursor.execute(
                "SELECT result_filename FROM analysis_history WHERE id = ?",
                (history_id,)
            )
            history_item = cursor.fetchone()

            if not history_item:
                raise HTTPException(status_code=404, detail="Запись истории не найдена")

            # Удаляем файл если существует
            result_path = os.path.join(settings.EXPORT_DIR, history_item["result_filename"])
            if os.path.exists(result_path):
                delete_file(result_path)

            # Удаляем запись из БД
            cursor.execute("DELETE FROM analysis_history WHERE id = ?", (history_id,))

            return BaseResponse(message="Запись истории удалена успешно")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления истории: {str(e)}")


@router.get("/download/{filename}")
async def download_analysis_result(filename: str):
    """
    Скачать результат анализа по имени файла
    """
    try:
        result_path = os.path.join(settings.EXPORT_DIR, filename)

        if not os.path.exists(result_path):
            raise HTTPException(status_code=404, detail="Файл не найден")

        with open(result_path, 'rb') as f:
            file_content = f.read()

        return Response(
            content=file_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания файла: {str(e)}")


@router.get("/months/stats", response_model=BaseResponse)
async def get_months_stats():
    """
    Получить статистику по месяцам
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT month, COUNT(*) as count, 
                       SUM(file_size) as total_size,
                       MIN(created_at) as first_date,
                       MAX(created_at) as last_date
                FROM analysis_history 
                GROUP BY month 
                ORDER BY month
                """
            )

            stats = cursor.fetchall()

            # Добавляем названия месяцев
            month_names = [
                'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
            ]

            for stat in stats:
                stat["month_name"] = month_names[stat["month"] - 1] if 1 <= stat["month"] <= 12 else "Неизвестно"

            return BaseResponse(data=stats)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки статистики: {str(e)}")