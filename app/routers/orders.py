from fastapi import APIRouter, HTTPException, Response
import json, uuid, traceback
from datetime import datetime
from app.database import get_db_cursor
from app.models import OrderSessionUpdate, BaseResponse

router = APIRouter()


def _get_nom_for_address(cursor, address_id: int, order_type: str, mapping: dict) -> list:
    if address_id in mapping and mapping[address_id]:
        ids = mapping[address_id]
        ph = ",".join("?" * len(ids))
        cursor.execute(f"SELECT id, name, comment FROM nomenclature WHERE id IN ({ph}) AND type=? ORDER BY name", (*ids, order_type))
    else:
        cursor.execute("SELECT id, name, comment FROM nomenclature WHERE type=? ORDER BY name", (order_type,))
    return cursor.fetchall()


@router.post("/create/{order_type}", response_model=BaseResponse)
async def create_order_session(order_type: str):
    try:
        if order_type not in ["КЦ", "Расходники"]:
            raise HTTPException(status_code=400, detail="Некорректный тип заказа")
        with get_db_cursor() as cursor:
            tpl_name = "Шаблон КЦ" if order_type == "КЦ" else "Шаблон заказа расходников"
            cursor.execute("SELECT headers, address_mapping FROM templates WHERE name=? AND type=?", (tpl_name, order_type))
            tpl = cursor.fetchone()
            if not tpl:
                raise HTTPException(status_code=404, detail="Шаблон не найден")
            try:
                headers = json.loads(tpl.get("headers") or "[]")
            except Exception:
                headers = []
            try:
                mapping = {int(k): v for k, v in json.loads(tpl.get("address_mapping") or "{}").items()}
            except Exception:
                mapping = {}
            cursor.execute("SELECT id, np_number, address, contact_person, phone FROM addresses ORDER BY np_number")
            addresses = cursor.fetchall()
            addresses_data = {}
            all_addresses = []
            for addr in addresses:
                addr_id = addr["id"]
                addr_str = addr.get("address", "")
                if not addr_str:
                    continue
                all_addresses.append(addr_str)
                nom = _get_nom_for_address(cursor, addr_id, order_type, mapping)
                rows = []
                for item in nom:
                    rd = {}
                    for h in headers:
                        if   h == "Наименов ТМЦ":   rd[h] = item.get("name","")
                        elif h == "Кол-во":          rd[h] = ""
                        elif h == "Адрес отгрузки":  rd[h] = addr_str
                        elif h == "ФИО получателя":  rd[h] = addr.get("contact_person","") or ""
                        elif h == "Телефон":         rd[h] = addr.get("phone","") or ""
                        elif h == "НП":              rd[h] = addr.get("np_number","") or ""
                        elif h == "Комментарий":     rd[h] = item.get("comment","") or ""
                        else:                        rd[h] = ""
                    rows.append(rd)
                addresses_data[addr_str] = rows
            session_id = str(uuid.uuid4())
            data = {"headers": headers, "addresses": all_addresses, "addresses_data": addresses_data, "order_type": order_type}
            cursor.execute("INSERT INTO order_sessions (session_id, order_type, data) VALUES (?, ?, ?)",
                           (session_id, order_type, json.dumps(data, ensure_ascii=False)))
            return BaseResponse(success=True, message="Сессия создана",
                                data={"session_id": session_id, "order_data": data, "redirect_url": f"/page/order/edit/{session_id}"})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=BaseResponse)
async def get_order_session(session_id: str):
    try:
        if not session_id or session_id.lower() in ["undefined","null","none"]:
            raise HTTPException(status_code=400, detail="Некорректный session_id")
        with get_db_cursor() as cursor:
            cursor.execute("SELECT data FROM order_sessions WHERE session_id=?", (session_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Сессия не найдена")
            try:
                data = json.loads(row["data"] or "{}")
            except Exception:
                data = {}
            return BaseResponse(success=True, message="OK", data=data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/update", response_model=BaseResponse)
async def update_order_session(session_id: str, update_data: OrderSessionUpdate):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT data FROM order_sessions WHERE session_id=?", (session_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Сессия не найдена")
            try:
                data = json.loads(row["data"] or "{}")
            except Exception:
                data = {}
            addr = update_data.address
            if addr and "addresses_data" in data and addr in data["addresses_data"]:
                data["addresses_data"][addr] = update_data.items
            cursor.execute("UPDATE order_sessions SET data=?, updated_at=CURRENT_TIMESTAMP WHERE session_id=?",
                           (json.dumps(data, ensure_ascii=False), session_id))
            return BaseResponse(success=True, message="Обновлено")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/export")
async def export_order_session(session_id: str):
    try:
        from app.services.excel_service import create_order_excel
        with get_db_cursor() as cursor:
            cursor.execute("SELECT data, order_type FROM order_sessions WHERE session_id=?", (session_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Сессия не найдена")
            try:
                data = json.loads(row["data"] or "{}")
            except Exception:
                data = {}
            order_type = row["order_type"]
            excel_data = create_order_excel(data, order_type)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
            tr = str.maketrans("КЦРасходники", "KCRashodniki")
            safe = order_type.translate(tr)
            return Response(content=excel_data,
                            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": f"attachment; filename=order_{safe}_{ts}.xlsx"})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{user_id}", response_model=BaseResponse)
async def get_order_history(user_id: int, limit: int = 10):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT session_id, order_type, created_at FROM order_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            return BaseResponse(success=True, data=cursor.fetchall())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))