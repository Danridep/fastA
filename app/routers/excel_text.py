"""
Роутер: генератор текста из Excel.
Подключить в main.py:
    from app.routers import excel_text
    app.include_router(excel_text.router, prefix="/api/excel-text", tags=["excel-text"])
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
from typing import Optional
import json

from app.services.excel_text_service import parse_excel_preview, generate_text
from app.models import BaseResponse

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".ods"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def _check_file(file: UploadFile):
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,
                            detail=f"Неподдерживаемый формат. Допустимы: {', '.join(ALLOWED_EXTENSIONS)}")


@router.post("/preview", response_model=BaseResponse)
async def preview_excel(
    file: UploadFile = File(...),
    sheet_index: int = Form(0),
    header_row:  int = Form(1),
    preview_rows: int = Form(5)
):
    """
    Загрузить Excel и получить список столбцов + первые N строк.
    Используется для настройки маппинга в UI.
    """
    _check_file(file)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс. 20 МБ)")

    try:
        result = parse_excel_preview(
            content,
            sheet_index=sheet_index,
            header_row=header_row,
            preview_rows=min(preview_rows, 20)
        )
        return BaseResponse(
            success=True,
            data={**result, "filename": file.filename}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {str(e)}")


@router.post("/generate", response_model=BaseResponse)
async def generate_text_api(
    file: UploadFile = File(...),
    config: str = Form(...)  # JSON-строка конфига
):
    """
    Сгенерировать текст из Excel по конфигу.
    Возвращает текст + статистику.
    """
    _check_file(file)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой")

    try:
        cfg = json.loads(config)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный JSON конфига")

    try:
        result = generate_text(content, cfg)
        return BaseResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")


@router.post("/download")
async def download_text(
    file: UploadFile = File(...),
    config: str = Form(...),
    filename: Optional[str] = Form("output.txt")
):
    """Скачать сгенерированный текст как .txt файл."""
    _check_file(file)
    content = await file.read()

    try:
        cfg = json.loads(config)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный JSON конфига")

    try:
        result = generate_text(content, cfg)
        text = result["text"]
        safe_filename = filename if filename.endswith(".txt") else filename + ".txt"
        return PlainTextResponse(
            content=text,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))