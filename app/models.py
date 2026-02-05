from pydantic import BaseModel, EmailStr, validator, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from decimal import Decimal

# Базовые модели
class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class PaginatedResponse(BaseResponse):
    total: int = 0
    page: int = 1
    pages: int = 1
    per_page: int = 20
    data: Optional[List[Dict[str, Any]]] = None

# Модели пользователей
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=6)

class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Модели аутентификации
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

# Модели номенклатуры
class NomenclatureBase(BaseModel):
    type: str = Field(..., pattern="^(КЦ|Расходники)$")
    name: str = Field(..., min_length=1, max_length=200)
    comment: Optional[str] = Field(None, max_length=500)

class NomenclatureCreate(NomenclatureBase):
    pass

class NomenclatureUpdate(NomenclatureBase):
    pass

class Nomenclature(NomenclatureBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Модели адресов
class AddressBase(BaseModel):
    np_number: Optional[str] = Field(None, max_length=20)
    address: str = Field(..., min_length=1, max_length=300)
    contact_person: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

class AddressCreate(AddressBase):
    pass

class AddressUpdate(AddressBase):
    pass

class Address(AddressBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Модели шаблонов
class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern="^(КЦ|Расходники)$")
    headers: List[str] = Field(..., min_items=1)

class TemplateCreate(TemplateBase):
    pass

class TemplateUpdate(TemplateBase):
    pass

class Template(TemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Модели заказов
class OrderItem(BaseModel):
    address: str
    items: List[Dict[str, str]]

class OrderSessionCreate(BaseModel):
    order_type: str = Field(..., pattern="^(КЦ|Расходники)$")

class OrderSessionUpdate(BaseModel):
    address: str
    items: List[Dict[str, str]] = Field(..., min_items=1)

class OrderSession(BaseModel):
    session_id: str
    order_type: str
    data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

# Модели анализа Pandas
class PandasAnalysisRequest(BaseModel):
    month: int = Field(..., ge=1, le=12)

class AnalysisHistory(BaseModel):
    id: int
    month: int
    original_filename: str
    result_filename: str
    file_size: int
    status: str
    created_at: datetime

# Модели статистики
class StatsResponse(BaseModel):
    nomenclature_count: int
    addresses_count: int
    templates_count: int
    order_sessions_count: int
    analysis_history_count: int
    nomenclature_by_type: Dict[str, int]
    particle_comparisons_count: int = 0
    particle_stats: Optional[Dict[str, Any]] = None

# ============================================
# Модели для сравнения Excel файлов (Particle)
# ============================================

class CellInfo(BaseModel):
    """Информация о ячейке с отрицательным значением"""
    cell: str = Field(..., description="Ссылка на ячейку в формате R1C1")
    value: float = Field(..., description="Значение в ячейке")
    row: int = Field(..., ge=1, description="Номер строки")
    column: int = Field(..., ge=1, description="Номер столбца")

class FileComparison(BaseModel):
    """Информация о сравнении одного файла"""
    name: str = Field(..., description="Имя файла")
    minus_cells: List[CellInfo] = Field(default_factory=list, description="Ячейки с отрицательными значениями")
    minus_count: int = Field(0, ge=0, description="Количество отрицательных значений")
    total: Optional[float] = Field(None, description="Итоговое значение из файла")
    total_cell: Optional[str] = Field(None, description="Ссылка на ячейку с итогом")

class ComparisonStatus(BaseModel):
    """Статус сравнения итоговых значений"""
    status: str = Field(..., pattern="^(match|mismatch)$", description="Статус сравнения")
    message: str = Field(..., description="Сообщение о результате сравнения")
    total1: Optional[float] = Field(None, description="Итог из первого файла")
    total2: Optional[float] = Field(None, description="Итог из второго файла")

class ComparisonResult(BaseModel):
    """Результат сравнения двух файлов"""
    history_id: Optional[int] = Field(None, description="ID записи в истории")
    file1: FileComparison = Field(..., description="Информация о первом файле")
    file2: FileComparison = Field(..., description="Информация о втором файле")
    comparison: ComparisonStatus = Field(..., description="Результат сравнения итогов")
    timestamp: str = Field(..., description="Временная метка выполнения сравнения")

class ComparisonHistoryBase(BaseModel):
    """Базовая модель истории сравнений"""
    file1_name: str = Field(..., min_length=1, max_length=255, description="Имя первого файла")
    file2_name: str = Field(..., min_length=1, max_length=255, description="Имя второго файла")
    total1: Optional[float] = Field(None, description="Итог из первого файла")
    total2: Optional[float] = Field(None, description="Итог из второго файла")
    comparison: str = Field(..., pattern="^(match|mismatch)$", description="Результат сравнения")

class ComparisonHistory(ComparisonHistoryBase):
    """Полная модель истории сравнений"""
    id: int = Field(..., description="ID записи")
    minus_count1: int = Field(0, ge=0, description="Количество минусов в первом файле")
    minus_count2: int = Field(0, ge=0, description="Количество минусов во втором файле")
    created_at: str = Field(..., description="Дата и время создания")