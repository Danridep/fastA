from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.database import get_db_cursor
from app.models import (
    Nomenclature, NomenclatureCreate, NomenclatureUpdate,
    BaseResponse, PaginatedResponse
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def get_nomenclature(
        type: Optional[str] = Query(None, description="Тип номенклатуры"),
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        search: Optional[str] = Query(None, description="Поиск по названию")
):
    """
    Получить список номенклатуры с пагинацией
    """
    try:
        with get_db_cursor() as cursor:
            # Строим запрос с фильтрами
            query = "SELECT * FROM nomenclature WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM nomenclature WHERE 1=1"
            params = []

            if type and type != "Все":
                query += " AND type = ?"
                count_query += " AND type = ?"
                params.append(type)

            if search:
                query += " AND (name LIKE ? OR comment LIKE ?)"
                count_query += " AND (name LIKE ? OR comment LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            # Получаем общее количество
            cursor.execute(count_query, params)
            result = cursor.fetchone()
            total = result["count"] if result else 0

            # Пагинация
            offset = (page - 1) * per_page
            query += " ORDER BY type, name LIMIT ? OFFSET ?"
            params.extend([per_page, offset])

            cursor.execute(query, params)
            items = cursor.fetchall()

            return PaginatedResponse(
                total=total,
                page=page,
                pages=(total + per_page - 1) // per_page,
                per_page=per_page,
                data=items
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки номенклатуры: {str(e)}")


@router.get("/{item_id}", response_model=Nomenclature)
async def get_nomenclature_item(item_id: int):
    """
    Получить номенклатуру по ID
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM nomenclature WHERE id = ?", (item_id,))
            item = cursor.fetchone()

            if not item:
                raise HTTPException(status_code=404, detail="Номенклатура не найдена")

            return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки номенклатуры: {str(e)}")


@router.post("/", response_model=BaseResponse)
async def create_nomenclature(item: NomenclatureCreate):
    """
    Создать новую номенклатуру
    """
    try:
        with get_db_cursor() as cursor:
            # Проверяем, не существует ли уже такая номенклатура
            cursor.execute(
                "SELECT id FROM nomenclature WHERE type = ? AND name = ?",
                (item.type, item.name)
            )
            existing = cursor.fetchone()

            if existing:
                raise HTTPException(status_code=400, detail="Такая номенклатура уже существует")

            cursor.execute(
                """
                INSERT INTO nomenclature (type, name, comment)
                VALUES (?, ?, ?)
                """,
                (item.type, item.name, item.comment or "")
            )

            return BaseResponse(
                message="Номенклатура создана успешно",
                data={"id": cursor.lastrowid}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания номенклатуры: {str(e)}")


@router.put("/{item_id}", response_model=BaseResponse)
async def update_nomenclature(item_id: int, item: NomenclatureUpdate):
    """
    Обновить номенклатуру
    """
    try:
        with get_db_cursor() as cursor:
            # Проверяем существование
            cursor.execute("SELECT id FROM nomenclature WHERE id = ?", (item_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Номенклатура не найдена")

            # Проверяем уникальность
            cursor.execute(
                "SELECT id FROM nomenclature WHERE type = ? AND name = ? AND id != ?",
                (item.type, item.name, item_id)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Такая номенклатура уже существует")

            cursor.execute(
                """
                UPDATE nomenclature 
                SET type = ?, name = ?, comment = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (item.type, item.name, item.comment or "", item_id)
            )

            return BaseResponse(message="Номенклатура обновлена успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления номенклатуры: {str(e)}")


@router.delete("/{item_id}", response_model=BaseResponse)
async def delete_nomenclature(item_id: int):
    """
    Удалить номенклатуру
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM nomenclature WHERE id = ?", (item_id,))

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Номенклатура не найдена")

            return BaseResponse(message="Номенклатура удалена успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления номенклатуры: {str(e)}")


@router.get("/types/list", response_model=BaseResponse)
async def get_nomenclature_types():
    """
    Получить список типов номенклатуры
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT DISTINCT type FROM nomenclature ORDER BY type")
            types = [row["type"] for row in cursor.fetchall()]

            return BaseResponse(data=types)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки типов: {str(e)}")