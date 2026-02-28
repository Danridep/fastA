from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from pydantic import BaseModel
import json
from app.database import get_db_cursor
from app.models import Template, TemplateCreate, TemplateUpdate, BaseResponse, PaginatedResponse

router = APIRouter()


class AddressMappingUpdate(BaseModel):
    address_mapping: Dict[str, List[int]]


def _parse(t: dict) -> dict:
    if t.get("headers"):
        try: t["headers"] = json.loads(t["headers"])
        except: t["headers"] = []
    try: t["address_mapping"] = {int(k): v for k, v in json.loads(t.get("address_mapping") or "{}").items()}
    except: t["address_mapping"] = {}
    return t


@router.get("/", response_model=PaginatedResponse)
async def get_templates(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                        type: Optional[str] = Query(None), search: Optional[str] = Query(None)):
    try:
        with get_db_cursor() as cursor:
            q = "SELECT * FROM templates WHERE 1=1"; cq = "SELECT COUNT(*) as count FROM templates WHERE 1=1"; p = []
            if type:   q += " AND type=?";       cq += " AND type=?";       p.append(type)
            if search: q += " AND name LIKE ?";   cq += " AND name LIKE ?";  p.append(f"%{search}%")
            cursor.execute(cq, p); total = (cursor.fetchone() or {}).get("count", 0)
            q += " ORDER BY name LIMIT ? OFFSET ?"; p.extend([per_page, (page-1)*per_page])
            cursor.execute(q, p)
            return PaginatedResponse(total=total, page=page, pages=(total+per_page-1)//per_page,
                                     per_page=per_page, data=[_parse(t) for t in cursor.fetchall()])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=BaseResponse)
async def get_template(template_id: int):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM templates WHERE id=?", (template_id,))
            t = cursor.fetchone()
            if not t: raise HTTPException(status_code=404, detail="Шаблон не найден")
            return BaseResponse(data=_parse(t))
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=BaseResponse)
async def create_template(template: TemplateCreate):
    try:
        if not template.headers: raise HTTPException(status_code=400, detail="Шаблон должен содержать заголовки")
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM templates WHERE name=? AND type=?", (template.name, template.type))
            if cursor.fetchone(): raise HTTPException(status_code=400, detail="Шаблон уже существует")
            cursor.execute("INSERT INTO templates (name, type, headers, address_mapping) VALUES (?, ?, ?, ?)",
                           (template.name, template.type, json.dumps(template.headers, ensure_ascii=False), "{}"))
            return BaseResponse(message="Шаблон создан", data={"id": cursor.lastrowid})
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}", response_model=BaseResponse)
async def update_template(template_id: int, template: TemplateUpdate):
    try:
        if not template.headers: raise HTTPException(status_code=400, detail="Шаблон должен содержать заголовки")
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM templates WHERE id=?", (template_id,))
            if not cursor.fetchone(): raise HTTPException(status_code=404, detail="Шаблон не найден")
            cursor.execute("SELECT id FROM templates WHERE name=? AND type=? AND id!=?", (template.name, template.type, template_id))
            if cursor.fetchone(): raise HTTPException(status_code=400, detail="Шаблон уже существует")
            cursor.execute("UPDATE templates SET name=?, type=?, headers=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                           (template.name, template.type, json.dumps(template.headers, ensure_ascii=False), template_id))
            return BaseResponse(message="Шаблон обновлён")
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}", response_model=BaseResponse)
async def delete_template(template_id: int):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM templates WHERE id=?", (template_id,))
            if cursor.rowcount == 0: raise HTTPException(status_code=404, detail="Шаблон не найден")
            return BaseResponse(message="Шаблон удалён")
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}/mapping", response_model=BaseResponse)
async def get_mapping(template_id: int):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT address_mapping FROM templates WHERE id=?", (template_id,))
            row = cursor.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Шаблон не найден")
            try: mapping = {int(k): v for k, v in json.loads(row["address_mapping"] or "{}").items()}
            except: mapping = {}
            return BaseResponse(data={"mapping": mapping})
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/mapping", response_model=BaseResponse)
async def set_mapping(template_id: int, body: AddressMappingUpdate):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM templates WHERE id=?", (template_id,))
            if not cursor.fetchone(): raise HTTPException(status_code=404, detail="Шаблон не найден")
            mapping_str = json.dumps({str(k): v for k, v in body.address_mapping.items()}, ensure_ascii=False)
            cursor.execute("UPDATE templates SET address_mapping=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                           (mapping_str, template_id))
            return BaseResponse(message="Маппинг сохранён", data={"count": len(body.address_mapping)})
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{template_id}/mapping/{address_id}", response_model=BaseResponse)
async def patch_address_mapping(template_id: int, address_id: int, body: dict):
    try:
        nom_ids = body.get("nomenclature_ids", [])
        with get_db_cursor() as cursor:
            cursor.execute("SELECT address_mapping FROM templates WHERE id=?", (template_id,))
            row = cursor.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Шаблон не найден")
            try: mapping = json.loads(row["address_mapping"] or "{}")
            except: mapping = {}
            if nom_ids: mapping[str(address_id)] = nom_ids
            else:       mapping.pop(str(address_id), None)
            cursor.execute("UPDATE templates SET address_mapping=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                           (json.dumps(mapping, ensure_ascii=False), template_id))
            return BaseResponse(message=f"{'Назначено ' + str(len(nom_ids)) if nom_ids else 'Сброшено'}",
                                data={"address_id": address_id, "count": len(nom_ids)})
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


@router.get("/types/list", response_model=BaseResponse)
async def get_types():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT DISTINCT type FROM templates ORDER BY type")
            return BaseResponse(data=[r["type"] for r in cursor.fetchall()])
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))