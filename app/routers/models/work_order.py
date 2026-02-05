from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class WorkOrderBase(BaseModel):
    """Базовая модель для работы с заявками"""
    work_types_file: Optional[str] = None
    orders_file: Optional[str] = None


class WorkOrderRequest(BaseModel):
    """Модель запроса для обработки заявок"""
    session_id: Optional[str] = Field(None, description="ID сессии для отслеживания")
    work_types_file: str = Field(..., description="Имя файла с типами работ")
    orders_file: str = Field(..., description="Имя файла с заявками")


class ViolationOrder(BaseModel):
    """Модель заявки с нарушением"""
    index: int
    Наряд: str
    Исполнитель: str
    Город: str
    Номер_заявки: str = Field(..., alias="Номер заявки")
    Тип_работ: str = Field(..., alias="Тип работ")
    Тип_работ_оригинал_из_правил: str
    is_to: int
    violations: List[str]
    actual: Dict[str, int]


class ViolationStats(BaseModel):
    """Статистика нарушений"""
    total_checked: int
    matched_types: int
    unmatched_types: int
    skipped_orders: int
    violation_orders: int
    to_violations: int
    non_to_violations: int
    matched_types_list: List[str]
    unmatched_types_list: List[str]


class RegionViolation(BaseModel):
    """Нарушения по региону"""
    region: str
    orders: List[Dict[str, str]]
    count: int


class WorkOrderResult(BaseModel):
    """Результат обработки заявок"""
    session_id: str
    success: bool = True
    message: Optional[str] = None
    stats: Optional[ViolationStats] = None
    files: Optional[Dict[str, str]] = None
    regional_data: Optional[Dict[str, List[Dict[str, str]]]] = None
    created_at: datetime = Field(default_factory=datetime.now)


class DownloadRequest(BaseModel):
    """Запрос на скачивание файла"""
    file_path: str
    file_type: str = "highlighted"


class SessionStatus(BaseModel):
    session_id: str
    status: str
    progress: int
    message: str
    files: Dict[str, Any]  # Измените с List на Dict
    created_at: datetime
    updated_at: datetime
    stats: Optional[Dict[str, Any]] = None  # Добавьте это поле
    regional_data: Optional[Dict[str, Any]] = None  # И это поле

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }