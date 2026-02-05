import pandas as pd
from datetime import datetime
from typing import Optional
import os


def analyze_excel_data(file_path: str, month: int) -> pd.DataFrame:
    """
    Анализ Excel файла с помощью Pandas
    """
    try:
        # Читаем Excel файл
        df = pd.read_excel(
            file_path,
            skiprows=7,
            skipfooter=2,
            usecols=["Родитель", "Дата статуса", "Количество", "Стоимость (с НДС)"]
        )

        # Преобразуем даты
        df["Дата статуса"] = pd.to_datetime(
            df["Дата статуса"],
            format="%d.%m.%Y %H:%M:%S",
            errors='coerce'
        )

        # Преобразуем числовые колонки
        df[["Количество", "Стоимость (с НДС)"]] = df[
            ["Количество", "Стоимость (с НДС)"]
        ].apply(pd.to_numeric, errors='coerce')

        # Фильтруем по месяцу
        df = df[df["Дата статуса"].dt.month == month]

        if df.empty:
            return df

        # Группируем по филиалам
        df = df.groupby("Родитель", as_index=False)[
            ['Количество', 'Стоимость (с НДС)']
        ].sum()

        # Переименовываем колонки
        df.columns = ["Филиал", "Сумма по полю Кількість", "Сумма по полю Стоимость СНДС"]

        # Добавляем общий итог
        total_row = pd.DataFrame({
            "Филиал": ["Общий итог"],
            "Сумма по полю Кількість": [df["Сумма по полю Кількість"].sum()],
            "Сумма по полю Стоимость СНДС": [df["Сумма по полю Стоимость СНДС"].sum()]
        })

        df = pd.concat([df, total_row], ignore_index=True)

        return df

    except Exception as e:
        raise Exception(f"Ошибка анализа данных: {str(e)}")