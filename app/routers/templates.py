from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json
from app.database import get_db_cursor
from app.models import (
    Template, TemplateCreate, TemplateUpdate,
    BaseResponse, PaginatedResponse
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def get_templates(
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        type: Optional[str] = Query(None, description="Тип шаблона"),
        search: Optional[str] = Query(None, description="Поиск по названию")
):
    """
    Получить список шаблонов с пагинацией
    """
    try:
        with get_db_cursor() as cursor:
            # Строим запрос с фильтрами
            query = "SELECT * FROM templates WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM templates WHERE 1=1"
            params = []

            if type:
                query += " AND type = ?"
                count_query += " AND type = ?"
                params.append(type)

            if search:
                query += " AND name LIKE ?"
                count_query += " AND name LIKE ?"
                params.append(f"%{search}%")

            # Получаем общее количество
            cursor.execute(count_query, params)
            result = cursor.fetchone()
            total = result["count"] if result else 0

            # Пагинация
            offset = (page - 1) * per_page
            query += " ORDER BY name LIMIT ? OFFSET ?"
            params.extend([per_page, offset])

            cursor.execute(query, params)
            templates = cursor.fetchall()

            # Преобразуем JSON строки headers в списки
            for template in templates:
                if template.get('headers'):
                    try:
                        template['headers'] = json.loads(template['headers'])
                    except:
                        template['headers'] = []

            return PaginatedResponse(
                total=total,
                page=page,
                pages=(total + per_page - 1) // per_page,
                per_page=per_page,
                data=templates
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки шаблонов: {str(e)}")


@router.get("/{template_id}", response_model=Template)
async def get_template(template_id: int):
    """
    Получить шаблон по ID
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            template = cursor.fetchone()

            if not template:
                raise HTTPException(status_code=404, detail="Шаблон не найден")

            # Преобразуем JSON строку headers в список
            if template.get('headers'):
                try:
                    template['headers'] = json.loads(template['headers'])
                except:
                    template['headers'] = []

            return template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки шаблона: {str(e)}")


@router.post("/", response_model=BaseResponse)
async def create_template(template: TemplateCreate):
    """
    Создать новый шаблон
    """
    try:
        # Валидация заголовков
        if not template.headers:
            raise HTTPException(status_code=400, detail="Шаблон должен содержать хотя бы один заголовок")

        headers_json = json.dumps(template.headers, ensure_ascii=False)

        with get_db_cursor() as cursor:
            # Проверяем, не существует ли уже такой шаблон
            cursor.execute(
                "SELECT id FROM templates WHERE name = ? AND type = ?",
                (template.name, template.type)
            )
            existing = cursor.fetchone()

            if existing:
                raise HTTPException(status_code=400, detail="Такой шаблон уже существует")

            cursor.execute(
                """
                INSERT INTO templates (name, type, headers)
                VALUES (?, ?, ?)
                """,
                (template.name, template.type, headers_json)
            )

            return BaseResponse(
                message="Шаблон создан успешно",
                data={"id": cursor.lastrowid}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания шаблона: {str(e)}")


@router.put("/{template_id}", response_model=BaseResponse)
async def update_template(template_id: int, template: TemplateUpdate):
    """
    Обновить шаблон
    """
    try:
        # Валидация заголовков
        if not template.headers:
            raise HTTPException(status_code=400, detail="Шаблон должен содержать хотя бы один заголовок")

        headers_json = json.dumps(template.headers, ensure_ascii=False)

        with get_db_cursor() as cursor:
            # Проверяем существование
            cursor.execute("SELECT id FROM templates WHERE id = ?", (template_id,))
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Шаблон не найден")

            # Проверяем уникальность
            cursor.execute(
                "SELECT id FROM templates WHERE name = ? AND type = ? AND id != ?",
                (template.name, template.type, template_id)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Такой шаблон уже существует")

            cursor.execute(
                """
                UPDATE templates 
                SET name = ?, type = ?, headers = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (template.name, template.type, headers_json, template_id)
            )

            return BaseResponse(message="Шаблон обновлен успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления шаблона: {str(e)}")


@router.delete("/{template_id}", response_model=BaseResponse)
async def delete_template(template_id: int):
    """
    Удалить шаблон
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Шаблон не найден")

            return BaseResponse(message="Шаблон удален успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления шаблона: {str(e)}")


@router.get("/types/list", response_model=BaseResponse)
async def get_template_types():
    """
    Получить список типов шаблонов
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT DISTINCT type FROM templates ORDER BY type")
            types = [row["type"] for row in cursor.fetchall()]

            return BaseResponse(data=types)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки типов: {str(e)}")


@router.get("/presets/{preset_name}", response_model=BaseResponse)
async def get_template_preset(preset_name: str):
    """
    Получить предустановленный шаблон
    """
    try:
        if preset_name == "kc":
            headers = ["Наименов ТМЦ", "Кол-во", "Адрес отгрузки", "ФИО получателя", "Телефон"]
            return BaseResponse(data={"name": "Шаблон КЦ", "type": "КЦ", "headers": headers})

        elif preset_name == "consumables":
            headers = ["Наименов ТМЦ", "Кол-во", "НП", "Адрес отгрузки", "ФИО получателя", "Телефон", "Комментарий"]
            return BaseResponse(data={"name": "Шаблон заказа расходников", "type": "Расходники", "headers": headers})

        else:
            raise HTTPException(status_code=404, detail="Предустановленный шаблон не найден")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки шаблона: {str(e)}")