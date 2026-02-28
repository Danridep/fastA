from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from app.config import settings
from app.routers import excel_text
# Импорт маршрутов
from app.routers import (
    auth,
    nomenclature,
    addresses,
    templates as templates_router,  # Переименовываем, чтобы избежать конфликта
    orders,
    pandas_analysis,
    stats,
    particle,
    work_orders
)
from app.database import init_database, get_db_connection

# Создаем приложение
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Создаем директории если их нет
Path("static").mkdir(exist_ok=True)
Path("uploads").mkdir(exist_ok=True)
Path("exports").mkdir(exist_ok=True)
Path("templates").mkdir(exist_ok=True)

# Настройка статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
# Используем jinja_templates вместо templates
jinja_templates = Jinja2Templates(directory="templates")

# Инициализация базы данных при запуске
@app.on_event("startup")
async def startup_event():
    init_database()
    # Создаем таблицу для истории сравнений, если она не существует
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS particle_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file1_name TEXT NOT NULL,
                file2_name TEXT NOT NULL,
                total1 REAL,
                total2 REAL,
                comparison TEXT NOT NULL,
                minus_count1 INTEGER DEFAULT 0,
                minus_count2 INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

# Подключение маршрутов
# API маршруты
app.include_router(auth.router, prefix="/api/auth", tags=["Аутентификация"])
app.include_router(nomenclature.router, prefix="/api/nomenclature", tags=["Номенклатура"])
app.include_router(addresses.router, prefix="/api/addresses", tags=["Адреса"])
app.include_router(templates_router.router, prefix="/api/templates", tags=["Шаблоны"])  # Используем переименованный импорт
app.include_router(orders.router, prefix="/api/orders", tags=["Заказы"])
app.include_router(pandas_analysis.router, prefix="/api/pandas", tags=["Pandas анализ"])
app.include_router(stats.router, prefix="/api/stats", tags=["Статистика"])
app.include_router(particle.router, prefix="/api/particle", tags=["Сравнение файлов"])
app.include_router(work_orders.router, prefix="/api/work_orders", tags=["Обработка заявок"])
app.include_router(excel_text.router, prefix="/api/excel-text", tags=["excel-text"])

# HTML страницы
@app.get("/", include_in_schema=False)
async def index(request: Request):
    """Главная страница приложения"""
    return jinja_templates.TemplateResponse("index.html", {"request": request})

@app.get("/page/nomenclature", include_in_schema=False)
async def nomenclature_page(request: Request):
    """Страница управления номенклатурой"""
    return jinja_templates.TemplateResponse("nomenclature.html", {"request": request})

@app.get("/page/addresses", include_in_schema=False)
async def addresses_page(request: Request):
    """Страница управления адресами"""
    return jinja_templates.TemplateResponse("addresses.html", {"request": request})

@app.get("/page/templates", include_in_schema=False)
async def templates_page(request: Request):
    """Страница управления шаблонами"""
    return jinja_templates.TemplateResponse("templates.html", {"request": request})

@app.get("/page/order/{order_type}", include_in_schema=False)
async def order_page(request: Request, order_type: str):
    """Страница создания заказа"""
    return jinja_templates.TemplateResponse("order.html", {"request": request, "order_type": order_type})

@app.get("/page/order/edit/{session_id}", include_in_schema=False)
async def order_edit_page(request: Request, session_id: str):
    """Страница редактирования заказа"""
    return jinja_templates.TemplateResponse("order_edit.html", {"request": request, "session_id": session_id})

@app.get("/page/pandas", include_in_schema=False)
async def pandas_page(request: Request):
    """Страница анализа Pandas"""
    return jinja_templates.TemplateResponse("pandas.html", {"request": request})

@app.get("/page/particle", include_in_schema=False)
async def particle_page(request: Request):
    """Страница обработки партийного учета"""
    return jinja_templates.TemplateResponse("particle.html", {"request": request})

@app.get("/page/work_orders", include_in_schema=False)
async def work_orders_page(request: Request):
    """Страница обработки заявок"""
    return jinja_templates.TemplateResponse("work_orders.html", {"request": request})

@app.get("/page/work-types", include_in_schema=False)  # Добавляем правильный endpoint
async def work_types_list(request: Request):
    """Страница управления типами работ"""
    return jinja_templates.TemplateResponse("work_types_list.html", {"request": request})

# Обработка 404 ошибок
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc):
    return jinja_templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.get("/page/excel-text")
async def excel_text_page(request: Request):
    return jinja_templates.TemplateResponse("excel_text.html", {"request": request})

# Health check endpoint
@app.get("/health")
async def health_check():
    """Проверка работоспособности приложения"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "database": "connected" if get_db_connection() else "disconnected",
        "modules": {
            "auth": "active",
            "nomenclature": "active",
            "addresses": "active",
            "templates": "active",
            "orders": "active",
            "pandas_analysis": "active",
            "stats": "active",
            "particle": "active",
            "work_orders": "active",
            "work_types": "active"
        }
    }