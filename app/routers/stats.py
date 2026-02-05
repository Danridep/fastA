from fastapi import APIRouter
from app.database import get_db_cursor
from app.models import StatsResponse, BaseResponse

router = APIRouter()


@router.get("/", response_model=StatsResponse)
async def get_stats():
    """
    Получить общую статистику приложения
    """
    try:
        with get_db_cursor() as cursor:
            # Номенклатура
            cursor.execute("SELECT COUNT(*) as count FROM nomenclature")
            nomenclature_result = cursor.fetchone()
            nomenclature_count = nomenclature_result["count"] if nomenclature_result else 0

            cursor.execute("SELECT type, COUNT(*) as count FROM nomenclature GROUP BY type")
            nomenclature_by_type = {row["type"]: row["count"] for row in cursor.fetchall()}

            # Адреса
            cursor.execute("SELECT COUNT(*) as count FROM addresses")
            addresses_result = cursor.fetchone()
            addresses_count = addresses_result["count"] if addresses_result else 0

            # Шаблоны
            cursor.execute("SELECT COUNT(*) as count FROM templates")
            templates_result = cursor.fetchone()
            templates_count = templates_result["count"] if templates_result else 0

            # Сессии заказов
            cursor.execute("SELECT COUNT(*) as count FROM order_sessions")
            order_sessions_result = cursor.fetchone()
            order_sessions_count = order_sessions_result["count"] if order_sessions_result else 0

            # История анализов
            cursor.execute("SELECT COUNT(*) as count FROM analysis_history")
            analysis_history_result = cursor.fetchone()
            analysis_history_count = analysis_history_result["count"] if analysis_history_result else 0

            # Статистика сравнений файлов (particle)
            cursor.execute("SELECT COUNT(*) as count FROM particle_history")
            particle_comparisons_result = cursor.fetchone()
            particle_comparisons_count = particle_comparisons_result["count"] if particle_comparisons_result else 0

            # Детальная статистика по сравнениям
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_comparisons,
                    SUM(CASE WHEN comparison = 'match' THEN 1 ELSE 0 END) as matches,
                    SUM(CASE WHEN comparison = 'mismatch' THEN 1 ELSE 0 END) as mismatches,
                    MIN(created_at) as first_comparison,
                    MAX(created_at) as last_comparison
                FROM particle_history
            """)
            particle_stats_result = cursor.fetchone()

            particle_stats = None
            if particle_stats_result and particle_stats_result["total_comparisons"] > 0:
                particle_stats = dict(particle_stats_result)

            return StatsResponse(
                nomenclature_count=nomenclature_count,
                addresses_count=addresses_count,
                templates_count=templates_count,
                order_sessions_count=order_sessions_count,
                analysis_history_count=analysis_history_count,
                nomenclature_by_type=nomenclature_by_type,
                particle_comparisons_count=particle_comparisons_count,
                particle_stats=particle_stats
            )

    except Exception as e:
        print(f"Error in get_stats: {e}")
        return StatsResponse(
            nomenclature_count=0,
            addresses_count=0,
            templates_count=0,
            order_sessions_count=0,
            analysis_history_count=0,
            nomenclature_by_type={},
            particle_comparisons_count=0
        )


@router.get("/dashboard", response_model=BaseResponse)
async def get_dashboard_stats():
    """
    Получить статистику для дашборда
    """
    try:
        with get_db_cursor() as cursor:
            # Сегодняшние активности
            cursor.execute("""
                SELECT COUNT(*) as today_orders 
                FROM order_sessions 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_orders_result = cursor.fetchone()
            today_orders = today_orders_result["today_orders"] if today_orders_result else 0

            cursor.execute("""
                SELECT COUNT(*) as today_analysis 
                FROM analysis_history 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_analysis_result = cursor.fetchone()
            today_analysis = today_analysis_result["today_analysis"] if today_analysis_result else 0

            cursor.execute("""
                SELECT COUNT(*) as today_comparisons 
                FROM particle_history 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_comparisons_result = cursor.fetchone()
            today_comparisons = today_comparisons_result["today_comparisons"] if today_comparisons_result else 0

            # Статистика за неделю
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count
                FROM order_sessions 
                WHERE created_at >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            weekly_orders = cursor.fetchall()

            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count
                FROM analysis_history 
                WHERE created_at >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            weekly_analysis = cursor.fetchall()

            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count
                FROM particle_history 
                WHERE created_at >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            weekly_comparisons = cursor.fetchall()

            # Топ номенклатуры
            cursor.execute("""
                SELECT type, COUNT(*) as count
                FROM nomenclature 
                GROUP BY type 
                ORDER BY count DESC
            """)
            top_nomenclature = cursor.fetchall()

            # Статистика по сравнению файлов
            cursor.execute("""
                SELECT 
                    comparison as status,
                    COUNT(*) as count
                FROM particle_history 
                GROUP BY comparison
                ORDER BY count DESC
            """)
            comparison_stats = cursor.fetchall()

            return BaseResponse(data={
                "today": {
                    "orders": today_orders,
                    "analysis": today_analysis,
                    "comparisons": today_comparisons
                },
                "weekly": {
                    "orders": weekly_orders,
                    "analysis": weekly_analysis,
                    "comparisons": weekly_comparisons
                },
                "top_nomenclature": top_nomenclature,
                "comparison_stats": comparison_stats,
                "activity_summary": {
                    "total": today_orders + today_analysis + today_comparisons,
                    "by_type": {
                        "orders": today_orders,
                        "analysis": today_analysis,
                        "comparisons": today_comparisons
                    }
                }
            })

    except Exception as e:
        print(f"Error in get_dashboard_stats: {e}")
        return BaseResponse(
            success=False,
            message=f"Ошибка загрузки статистики: {str(e)}",
            data={}
        )


@router.get("/particle", response_model=BaseResponse)
async def get_particle_stats():
    """
    Получить детальную статистику по сравнениям файлов
    """
    try:
        with get_db_cursor() as cursor:
            # Общая статистика
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN comparison = 'match' THEN 1 ELSE 0 END) as matches,
                    SUM(CASE WHEN comparison = 'mismatch' THEN 1 ELSE 0 END) as mismatches,
                    AVG(minus_count1) as avg_minus1,
                    AVG(minus_count2) as avg_minus2,
                    MIN(created_at) as first_date,
                    MAX(created_at) as last_date
                FROM particle_history
            """)
            stats = cursor.fetchone()

            # Статистика по дням за последнюю неделю
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count,
                    SUM(CASE WHEN comparison = 'match' THEN 1 ELSE 0 END) as matches,
                    SUM(CASE WHEN comparison = 'mismatch' THEN 1 ELSE 0 END) as mismatches
                FROM particle_history 
                WHERE created_at >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)
            daily_stats = cursor.fetchall()

            # Самые активные дни
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count
                FROM particle_history 
                GROUP BY DATE(created_at)
                ORDER BY count DESC
                LIMIT 5
            """)
            top_days = cursor.fetchall()

            # Статистика по файлам
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT file1_name) as unique_files1,
                    COUNT(DISTINCT file2_name) as unique_files2,
                    COUNT(DISTINCT file1_name || file2_name) as unique_combinations
                FROM particle_history
            """)
            file_stats = cursor.fetchone()

            return BaseResponse(data={
                "summary": stats,
                "daily_stats": daily_stats,
                "top_days": top_days,
                "file_stats": file_stats,
                "current_month": {
                    "total": 0,  # Можно добавить запрос для текущего месяца
                    "matches": 0,
                    "mismatches": 0
                }
            })

    except Exception as e:
        print(f"Error in get_particle_stats: {e}")
        return BaseResponse(
            success=False,
            message=f"Ошибка загрузки статистики: {str(e)}",
            data={}
        )