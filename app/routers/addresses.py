from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from typing import Optional, List
from pydantic import BaseModel
import pandas as pd
from app.database import get_db_cursor
from app.models import (
    Address, AddressCreate, AddressUpdate,
    BaseResponse, PaginatedResponse
)

router = APIRouter()


# ---------- доп. модели ----------

class NomenclatureAssignment(BaseModel):
    """Список ID номенклатур для адреса"""
    nomenclature_ids: List[int]


# ---------- CRUD адресов ----------

@router.get("/", response_model=PaginatedResponse)
async def get_addresses(
        page: int = Query(1, ge=1),
        per_page: int = Query(200, ge=1, le=500),
        search: Optional[str] = Query(None)
):
    try:
        with get_db_cursor() as cursor:
            query = "SELECT * FROM addresses WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM addresses WHERE 1=1"
            params = []

            if search:
                query += " AND (address LIKE ? OR contact_person LIKE ? OR phone LIKE ? OR np_number LIKE ?)"
                count_query += " AND (address LIKE ? OR contact_person LIKE ? OR phone LIKE ? OR np_number LIKE ?)"
                s = f"%{search}%"
                params.extend([s, s, s, s])

            cursor.execute(count_query, params)
            total = (cursor.fetchone() or {}).get("count", 0)

            offset = (page - 1) * per_page
            query += " ORDER BY np_number, address LIMIT ? OFFSET ?"
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
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки адресов: {str(e)}")


@router.get("/{address_id}", response_model=Address)
async def get_address(address_id: int):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM addresses WHERE id = ?", (address_id,))
            address = cursor.fetchone()
            if not address:
                raise HTTPException(status_code=404, detail="Адрес не найден")
            return address
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=BaseResponse)
async def create_address(address: AddressCreate):
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT id FROM addresses WHERE np_number = ? AND address = ?",
                (address.np_number, address.address)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Такой адрес уже существует")

            cursor.execute(
                "INSERT INTO addresses (np_number, address, contact_person, phone) VALUES (?, ?, ?, ?)",
                (address.np_number, address.address, address.contact_person, address.phone or "")
            )
            return BaseResponse(message="Адрес создан успешно", data={"id": cursor.lastrowid})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{address_id}", response_model=BaseResponse)
async def update_address(address_id: int, address: AddressUpdate):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM addresses WHERE id = ?", (address_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Адрес не найден")

            cursor.execute(
                "SELECT id FROM addresses WHERE np_number = ? AND address = ? AND id != ?",
                (address.np_number, address.address, address_id)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Такой адрес уже существует")

            cursor.execute(
                """UPDATE addresses 
                   SET np_number=?, address=?, contact_person=?, phone=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (address.np_number, address.address, address.contact_person, address.phone or "", address_id)
            )
            return BaseResponse(message="Адрес обновлен успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{address_id}", response_model=BaseResponse)
async def delete_address(address_id: int):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM addresses WHERE id = ?", (address_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Адрес не найден")
            return BaseResponse(message="Адрес удален успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Назначение номенклатур адресу ----------

@router.get("/{address_id}/nomenclature", response_model=BaseResponse)
async def get_address_nomenclature(address_id: int):
    """
    Вернуть список ID номенклатур, привязанных к адресу.
    Пустой список означает «все номенклатуры» (режим по умолчанию).
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM addresses WHERE id = ?", (address_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Адрес не найден")

            cursor.execute(
                """SELECT an.nomenclature_id, n.name, n.type, n.comment
                   FROM address_nomenclature an
                   JOIN nomenclature n ON n.id = an.nomenclature_id
                   WHERE an.address_id = ?
                   ORDER BY n.type, n.name""",
                (address_id,)
            )
            rows = cursor.fetchall()
            return BaseResponse(data={
                "address_id": address_id,
                "assigned": rows,
                "ids": [r["nomenclature_id"] for r in rows]
            })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{address_id}/nomenclature", response_model=BaseResponse)
async def set_address_nomenclature(address_id: int, body: NomenclatureAssignment):
    """
    Полностью заменить список номенклатур адреса.
    Передай пустой список — сброс в режим «все номенклатуры».
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM addresses WHERE id = ?", (address_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Адрес не найден")

            # Удаляем старые связи
            cursor.execute("DELETE FROM address_nomenclature WHERE address_id = ?", (address_id,))

            # Вставляем новые
            if body.nomenclature_ids:
                # Проверяем что все ID существуют
                placeholders = ",".join("?" * len(body.nomenclature_ids))
                cursor.execute(
                    f"SELECT id FROM nomenclature WHERE id IN ({placeholders})",
                    body.nomenclature_ids
                )
                found_ids = {r["id"] for r in cursor.fetchall()}
                missing = set(body.nomenclature_ids) - found_ids
                if missing:
                    raise HTTPException(status_code=400, detail=f"Номенклатуры не найдены: {missing}")

                cursor.executemany(
                    "INSERT OR IGNORE INTO address_nomenclature (address_id, nomenclature_id) VALUES (?, ?)",
                    [(address_id, nid) for nid in body.nomenclature_ids]
                )

            return BaseResponse(
                message=f"Назначено {len(body.nomenclature_ids)} номенклатур",
                data={"assigned_count": len(body.nomenclature_ids)}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{address_id}/nomenclature/add", response_model=BaseResponse)
async def add_nomenclature_to_address(address_id: int, body: NomenclatureAssignment):
    """Добавить номенклатуры к адресу (не затирая существующие)"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM addresses WHERE id = ?", (address_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Адрес не найден")

            cursor.executemany(
                "INSERT OR IGNORE INTO address_nomenclature (address_id, nomenclature_id) VALUES (?, ?)",
                [(address_id, nid) for nid in body.nomenclature_ids]
            )
            return BaseResponse(message="Номенклатуры добавлены")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{address_id}/nomenclature/{nomenclature_id}", response_model=BaseResponse)
async def remove_nomenclature_from_address(address_id: int, nomenclature_id: int):
    """Убрать одну номенклатуру из адреса"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "DELETE FROM address_nomenclature WHERE address_id=? AND nomenclature_id=?",
                (address_id, nomenclature_id)
            )
            return BaseResponse(message="Номенклатура удалена из адреса")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Импорт ----------

@router.post("/import", response_model=BaseResponse)
async def import_addresses(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(status_code=400, detail="Формат файла должен быть Excel или CSV")

        df = pd.read_csv(file.file) if file.filename.endswith('.csv') else pd.read_excel(file.file)

        required_columns = ['address', 'contact_person']
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Отсутствуют колонки: {', '.join(missing)}")

        imported_count = 0
        errors = []

        with get_db_cursor() as cursor:
            for index, row in df.iterrows():
                try:
                    np_number = str(row.get('np_number', '')).strip()
                    address = str(row['address']).strip()
                    contact_person = str(row['contact_person']).strip()
                    phone = str(row.get('phone', '')).strip()

                    if not address or not contact_person:
                        errors.append(f"Строка {index + 2}: Пустые обязательные поля")
                        continue

                    cursor.execute(
                        "SELECT id FROM addresses WHERE np_number = ? AND address = ?",
                        (np_number, address)
                    )
                    if cursor.fetchone():
                        errors.append(f"Строка {index + 2}: Адрес уже существует")
                        continue

                    cursor.execute(
                        "INSERT INTO addresses (np_number, address, contact_person, phone) VALUES (?, ?, ?, ?)",
                        (np_number, address, contact_person, phone)
                    )
                    imported_count += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")

        return BaseResponse(
            message=f"Импортировано {imported_count} адресов" + (f". Ошибок: {len(errors)}" if errors else ""),
            data={"imported": imported_count, "errors": errors[:10]}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))