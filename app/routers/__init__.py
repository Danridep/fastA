"""
Маршруты приложения
"""

from .auth import router as auth_router
from .nomenclature import router as nomenclature_router
from .addresses import router as addresses_router
from .templates import router as templates_router
from .orders import router as orders_router
from .pandas_analysis import router as pandas_analysis_router
from .stats import router as stats_router
from .particle import router as particle_router
from .work_orders import router as work_orders_router  # Добавлен новый роутер

__all__ = [
    'auth_router',
    'nomenclature_router',
    'addresses_router',
    'templates_router',
    'orders_router',
    'pandas_analysis_router',
    'stats_router',
    'particle_router',
    'work_orders_router'  # Добавлен новый роутер
]