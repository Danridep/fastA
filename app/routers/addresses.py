from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from typing import Optional
import pandas as pd
from app.database import get_db_cursor
from app.models import (
    Address, AddressCreate, AddressUpdate,
    BaseResponse, PaginatedResponse
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def get_addresses(
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        search: Optional[str] = Query(None, description="Поиск по адресу, ФИО или телефону")
):
    """
    Получить список адресов с пагинацией
    """
    try:
        with get_db_cursor() as cursor:
            # Строим запрос с фильтрами
            query = "SELECT * FROM addresses WHERE 1=1"
            count_query = "SELECT COUNT(*) as count FROM addresses WHERE 1=1"
            params = []

            if search:
                query += """ AND (
                    address LIKE ? OR 
                    contact_person LIKE ? OR 
                    phone LIKE ? OR
                    np_number LIKE ?
                )"""
                count_query += """ AND (
                    address LIKE ? OR 
                    contact_person LIKE ? OR 
                    phone LIKE ? OR
                    np_number LIKE ?
                )"""
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param, search_param])

            # Получаем общее количество
            cursor.execute(count_query, params)
            result = cursor.fetchone()
            total = result["count"] if result else 0

            # Пагинация
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
    """
    Получить адрес по ID
    """
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
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки адреса: {str(e)}")


@router.post("/", response_model=BaseResponse)
async def create_address(address: AddressCreate):
    """
    Создать новый адрес
    """
    try:
        with get_db_cursor() as cursor:
            # Проверяем, не существует ли уже такой адрес
            cursor.execute(
                "SELECT id FROM addresses WHERE np_number = ? AND address = ?",
                (address.np_number, address.address)
            )
            existing = cursor.fetchone()

            if existing:
                raise HTTPException(status_code=400, detail="Такой адрес уже существует")

            cursor.execute(
                """
                INSERT INTO addresses (np_number, address, contact_person, phone)
                VALUES (?, ?, ?, ?)
                """,
                (address.np_number, address.address, address.contact_person, address.phone or "")
            )

            return BaseResponse(
                message="Адрес создан успешно",
                data={"id": cursor.lastrowid}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания адреса: {str(e)}")


@router.put("/{address_id}", response_model=BaseResponse)
async def update_address(address_id: int, address: AddressUpdate):
    """
    Обновить адрес
    """
    try:
        with get_db_cursor() as cursor:
            # Проверяем существование
            cursor.execute("SELECT id FROM addresses WHERE id = ?", (address_id,))
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Адрес не найден")

            # Проверяем уникальность
            cursor.execute(
                """SELECT id FROM addresses 
                WHERE np_number = ? AND address = ? AND id != ?""",
                (address.np_number, address.address, address_id)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Такой адрес уже существует")

            cursor.execute(
                """
                UPDATE addresses 
                SET np_number = ?, address = ?, contact_person = ?, phone = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (address.np_number, address.address, address.contact_person,
                 address.phone or "", address_id)
            )

            return BaseResponse(message="Адрес обновлен успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления адреса: {str(e)}")


@router.delete("/{address_id}", response_model=BaseResponse)
async def delete_address(address_id: int):
    """
    Удалить адрес
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM addresses WHERE id = ?", (address_id,))

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Адрес не найден")

            return BaseResponse(message="Адрес удален успешно")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления адреса: {str(e)}")


@router.post("/import", response_model=BaseResponse)
async def import_addresses(file: UploadFile = File(...)):
    """
    Импортировать адреса из Excel файла
    """
    try:
        # Проверяем расширение файла
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(status_code=400, detail="Формат файла должен быть Excel или CSV")

        # Читаем файл в зависимости от формата
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)

        # Проверяем необходимые колонки
        required_columns = ['address', 'contact_person']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"В файле отсутствуют обязательные колонки: {', '.join(missing_columns)}"
            )

        # Обрабатываем данные
        imported_count = 0
        errors = []

        with get_db_cursor() as cursor:
            for index, row in df.iterrows():
                try:
                    np_number = str(row.get('np_number', '')).strip()
                    address = str(row['address']).strip()
                    contact_person = str(row['contact_person']).strip()
                    phone = str(row.get('phone', '')).strip()

                    # Проверяем обязательные поля
                    if not address or not contact_person:
                        errors.append(f"Строка {index + 2}: Отсутствуют обязательные поля")
                        continue

                    # Проверяем существование адреса
                    cursor.execute(
                        "SELECT id FROM addresses WHERE np_number = ? AND address = ?",
                        (np_number, address)
                    )
                    if cursor.fetchone():
                        errors.append(f"Строка {index + 2}: Адрес уже существует")
                        continue

                    # Добавляем адрес
                    cursor.execute(
                        """
                        INSERT INTO addresses (np_number, address, contact_person, phone)
                        VALUES (?, ?, ?, ?)
                        """,
                        (np_number, address, contact_person, phone)
                    )

                    imported_count += 1

                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")

        message = f"Импортировано {imported_count} адресов"
        if errors:
            message += f". Ошибки: {len(errors)}"

        return BaseResponse(
            message=message,
            data={
                "imported": imported_count,
                "errors": errors[:10]  # Ограничиваем количество ошибок для вывода
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка импорта адресов: {str(e)}")