from fastapi import APIRouter, HTTPException, Response
import json
import uuid
import traceback
from datetime import datetime
from app.database import get_db_cursor
from app.models import (
    OrderSessionCreate, OrderSessionUpdate,
    BaseResponse
)

router = APIRouter()


@router.post("/create/{order_type}", response_model=BaseResponse)
async def create_order_session(order_type: str):
    """
    Создать сессию заказа
    """
    try:
        print(f"Создание сессии заказа типа: {order_type}")

        # Проверяем тип заказа
        if order_type not in ["КЦ", "Расходники"]:
            raise HTTPException(status_code=400, detail="Некорректный тип заказа")

        with get_db_cursor() as cursor:
            # Получаем шаблон
            template_name = "Шаблон КЦ" if order_type == "КЦ" else "Шаблон заказа расходников"
            print(f"Поиск шаблона: {template_name}, тип: {order_type}")

            cursor.execute(
                "SELECT headers FROM templates WHERE name = ? AND type = ?",
                (template_name, order_type)
            )
            template_result = cursor.fetchone()

            if not template_result:
                raise HTTPException(status_code=404, detail="Шаблон не найден")

            headers_str = template_result.get("headers")
            if headers_str:
                try:
                    headers = json.loads(headers_str)
                except Exception as e:
                    print(f"Ошибка парсинга headers: {e}")
                    headers = []
            else:
                headers = []

            print(f"Заголовки шаблона: {headers}")

            # Получаем адреса
            cursor.execute(
                "SELECT np_number, address, contact_person, phone FROM addresses ORDER BY np_number"
            )
            addresses = cursor.fetchall()
            print(f"Найдено адресов: {len(addresses)}")

            # Получаем номенклатуру
            cursor.execute(
                "SELECT name, comment FROM nomenclature WHERE type = ? ORDER BY name",
                (order_type,)
            )
            nomenclature = cursor.fetchall()
            print(f"Найдено номенклатуры: {len(nomenclature)}")

            # Формируем данные для заказа
            addresses_data = {}
            all_addresses = []

            for addr in addresses:
                address_str = addr.get("address", "")
                if not address_str:
                    continue

                all_addresses.append(address_str)
                addresses_data[address_str] = []

                for item in nomenclature:
                    row_data = {}
                    for header in headers:
                        if header == "Наименов ТМЦ":
                            row_data[header] = item.get("name", "")
                        elif header == "Кол-во":
                            row_data[header] = ""
                        elif header == "Адрес отгрузки":
                            row_data[header] = address_str
                        elif header == "ФИО получателя":
                            row_data[header] = addr.get("contact_person", "") or ""
                        elif header == "Телефон":
                            row_data[header] = addr.get("phone", "") or ""
                        elif header == "НП":
                            row_data[header] = addr.get("np_number", "") or ""
                        elif header == "Комментарий":
                            row_data[header] = item.get("comment", "") or ""
                        else:
                            row_data[header] = ""

                    addresses_data[address_str].append(row_data)

            # Создаем сессию
            session_id = str(uuid.uuid4())
            data = {
                "headers": headers,
                "addresses": all_addresses,
                "addresses_data": addresses_data,
                "order_type": order_type
            }

            print(f"Создание сессии с ID: {session_id}")
            print(f"Данные для сохранения: headers={len(headers)}, addresses={len(all_addresses)}")

            cursor.execute(
                """
                INSERT INTO order_sessions (session_id, order_type, data)
                VALUES (?, ?, ?)
                """,
                (session_id, order_type, json.dumps(data, ensure_ascii=False, indent=2))
            )

            return BaseResponse(
                success=True,
                message="Сессия заказа создана успешно",
                data={
                    "session_id": session_id,
                    "order_data": data,
                    "redirect_url": f"/page/order/edit/{session_id}"
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating order session: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка создания сессии заказа: {str(e)}")


@router.get("/session/{session_id}", response_model=BaseResponse)
async def get_order_session(session_id: str):
    """
    Получить данные сессии заказа
    """
    try:
        print(f"Запрос данных сессии: {session_id}")

        # Защита от некорректных session_id
        if not session_id or session_id.lower() in ["undefined", "null", "none"]:
            raise HTTPException(status_code=400, detail="Некорректный идентификатор сессии")

        with get_db_cursor() as cursor:
            print(f"Выполнение запроса для session_id: {session_id}")
            cursor.execute(
                "SELECT data, order_type FROM order_sessions WHERE session_id = ?",
                (session_id,)
            )
            session_result = cursor.fetchone()

            print(f"Результат запроса: {session_result}")

            if not session_result:
                raise HTTPException(status_code=404, detail="Сессия не найдена")

            data_str = session_result.get("data")
            order_type = session_result.get("order_type", "")

            if data_str:
                try:
                    data = json.loads(data_str)
                    print(f"Данные успешно загружены. Тип заказа: {order_type}")
                    print(f"Ключи данных: {list(data.keys())}")
                    print(f"Количество адресов: {len(data.get('addresses', []))}")
                    print(f"Количество заголовков: {len(data.get('headers', []))}")
                except json.JSONDecodeError as e:
                    print(f"Ошибка декодирования JSON для сессии {session_id}: {e}")
                    print(f"Строка данных: {data_str[:200]}...")
                    data = {}
                except Exception as e:
                    print(f"Другая ошибка парсинга JSON: {e}")
                    data = {}
            else:
                print(f"Нет данных в сессии {session_id}")
                data = {}

            return BaseResponse(
                success=True,
                message="Данные сессии загружены",
                data=data
            )

    except HTTPException as he:
        print(f"HTTPException: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        print(f"Критическая ошибка загрузки сессии {session_id}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки сессии: {str(e)}")


@router.post("/session/{session_id}/update", response_model=BaseResponse)
async def update_order_session(session_id: str, update_data: OrderSessionUpdate):
    """
    Обновить данные сессии заказа
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT data FROM order_sessions WHERE session_id = ?",
                (session_id,)
            )
            session_result = cursor.fetchone()

            if not session_result:
                raise HTTPException(status_code=404, detail="Сессия не найдена")

            data_str = session_result.get("data")
            if data_str:
                try:
                    data = json.loads(data_str)
                except:
                    data = {}
            else:
                data = {}

            # Обновляем данные адреса
            address = update_data.address
            items = update_data.items

            if address and "addresses_data" in data and address in data["addresses_data"]:
                data["addresses_data"][address] = items

            # Сохраняем обновленные данные
            cursor.execute(
                """
                UPDATE order_sessions 
                SET data = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (json.dumps(data, ensure_ascii=False), session_id)
            )

            return BaseResponse(
                success=True,
                message="Данные обновлены успешно"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка обновления сессии: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка обновления сессии: {str(e)}")


@router.post("/session/{session_id}/export")
async def export_order_session(session_id: str):
    """
    Экспортировать заказ в Excel
    """
    try:
        from app.services.excel_service import create_order_excel

        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT data, order_type FROM order_sessions WHERE session_id = ?",
                (session_id,)
            )
            session_result = cursor.fetchone()

            if not session_result:
                raise HTTPException(status_code=404, detail="Сессия не найдена")

            data_str = session_result.get("data")
            order_type = session_result.get("order_type", "")

            if data_str:
                try:
                    data = json.loads(data_str)
                except:
                    data = {}
            else:
                data = {}

            # Создаем Excel файл
            excel_data = create_order_excel(data, order_type)

            # Генерируем имя файла
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

            # Создаем безопасное имя файла
            safe_filename = generate_safe_filename(order_type, timestamp)

            # Возвращаем файл
            return Response(
                content=excel_data,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename={safe_filename}"
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка экспорта заказа: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта заказа: {str(e)}")


def generate_safe_filename(order_type: str, timestamp: str) -> str:
    """
    Генерирует безопасное имя файла без русских букв
    """
    # Преобразуем русские буквы в транслитерацию
    translit_map = {
        'КЦ': 'KC',
        'Расходники': 'Rashodniki',
        'заказ': 'order',
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }

    # Преобразуем order_type
    safe_order_type = ''
    for char in order_type:
        safe_order_type += translit_map.get(char, char)

    # Итоговое имя файла
    return f"order_{safe_order_type}_{timestamp}.xlsx"


@router.get("/history/{user_id}", response_model=BaseResponse)
async def get_order_history(user_id: int, limit: int = 10):
    """
    Получить историю заказов пользователя
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT session_id, order_type, created_at, updated_at
                FROM order_sessions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (user_id, limit)
            )

            history = cursor.fetchall()

            return BaseResponse(
                success=True,
                data=history,
                message=f"Найдено {len(history)} заказов"
            )

    except Exception as e:
        print(f"Ошибка загрузки истории: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки истории: {str(e)}")


@router.get("/debug/sessions")
async def debug_sessions():
    """
    Отладочный эндпоинт для проверки сессий
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT session_id, order_type, created_at FROM order_sessions ORDER BY created_at DESC LIMIT 10")
            sessions = cursor.fetchall()

            result = []
            for session in sessions:
                session_id = session.get('session_id')
                cursor.execute("SELECT data FROM order_sessions WHERE session_id = ?", (session_id,))
                data_row = cursor.fetchone()

                data_str = data_row.get('data') if data_row else None
                data = None
                if data_str:
                    try:
                        data = json.loads(data_str)
                    except:
                        pass

                result.append({
                    'session_id': session_id,
                    'order_type': session.get('order_type'),
                    'created_at': session.get('created_at'),
                    'has_data': bool(data_str),
                    'data_keys': list(data.keys()) if data else []
                })

            return {"sessions": result}
    except Exception as e:
        return {"error": str(e)}