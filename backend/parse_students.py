import math
import pandas as pd
from sqlalchemy import select

# Компетенции, которые храним в JSONB‑поле Student.competencies
COMP_KEYS = ["H1", "H2", "H3", "H4", "H5", "H6", "H8"]

from backend.database.database import AsyncSessionLocal
from backend.database.models.student import Student


class StudentsDataParser:
    """
    Parser to update Student.diagnostics (JSONB) and Student.competencies (JSONB‑object with keys H1‑H6, H8)
    from uploaded Excel files.
    """

    def __init__(self, diagnostics_file, competencies_file):
        self.diagnostics_file = diagnostics_file
        self.competencies_file = competencies_file

    async def __call__(self):
        # 1. Читаем лист "Контингент" с вложенными заголовками
        df_diag = pd.read_excel(
            self.diagnostics_file.file,
            sheet_name="Контингент",
            header=[0, 1]
        )
        # Расплющиваем MultiIndex, если он есть
        if isinstance(df_diag.columns, pd.MultiIndex):
            new_cols = []
            for top, sub in df_diag.columns:
                sub_str = str(sub).strip()
                if sub_str.startswith("Unnamed"):
                    new_cols.append(top)
                else:
                    new_cols.append(f"{top} {sub_str}")
            df_diag.columns = new_cols

        # Фильтруем по валидному корпоративному email
        df_diag = df_diag[df_diag["Корпоративный Email"].str.contains("@", na=False)]

        # 2. Читаем лист с компетенциями
        df_comp = pd.read_excel(self.competencies_file.file, sheet_name=0)
        df_comp = df_comp[df_comp["Названия строк"].notna()]

        # 3. Открываем сессию и обновляем данные
        async with AsyncSessionLocal() as session:
            # --- Обновление diagnostics по email ---
            for _, row in df_diag.iterrows():
                email = row["Корпоративный Email"]

                # вычисляем среднее по аналитическому чтению
                reading_cols = [c for c in df_diag.columns if c.startswith("Аналитическое чтение")]
                def to_float(val):
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None
                reading_vals = [to_float(row[c]) for c in reading_cols if to_float(row[c]) is not None]
                avg_reading = sum(reading_vals) / len(reading_vals) if reading_vals else 0

                # вычисляем среднее по цифровой грамотности
                digital_cols = [c for c in df_diag.columns if c.startswith("Цифровая грамотность")]
                digital_vals = [to_float(row[c]) for c in digital_cols if to_float(row[c]) is not None]
                avg_digital = sum(digital_vals) / len(digital_vals) if digital_vals else 0

                # история России
                history_val = to_float(row.get("История России")) or 0

                scores = {
                    "reading": avg_reading,
                    "history": history_val,
                    "digital": avg_digital
                }
                # Replace NaN or None with 0 for JSON compatibility
                for key, val in scores.items():
                    if val is None or (isinstance(val, float) and math.isnan(val)):
                        scores[key] = 0

                # Выбираем всех студентов с таким email
                stmt = select(Student).where(Student.email == email)
                result = await session.execute(stmt)
                students = result.scalars().all()

                if students:
                    # Функция для извлечения года из potok
                    def extract_year(s: Student) -> int:
                        try:
                            year_str = s.potok.split(",", 1)[0].strip()
                            return int(year_str)
                        except Exception:
                            return -1

                    # Выбираем студента с максимальным годом потока
                    chosen = max(students, key=extract_year)
                    chosen.diagnostics = scores

            # --- Обновление competencies по ФИО ---
            for _, row in df_comp.iterrows():
                fio = row["Названия строк"]
                # собираем средние значения по компетенциям H1–H6 и H8
                comps = {}
                for i in range(1, 7):
                    col = f"Среднее по полю Н-{i}"
                    try:
                        comps[f"H{i}"] = float(row.get(col, 0))
                    except Exception:
                        comps[f"H{i}"] = 0.0
                # H8
                try:
                    comps["H8"] = float(row.get("Среднее по полю Н-8", 0))
                except Exception:
                    comps["H8"] = 0.0

                # ищем всех студентов с таким ФИО
                stmt = select(Student).where(Student.fio == fio)
                result = await session.execute(stmt)
                students = result.scalars().all()

                if students:
                    # используем ту же логику выбора по потоку
                    chosen = max(students, key=lambda s: extract_year(s))
                    chosen.competencies = comps

            # --- Заполнение нулевыми векторами для студентов без данных ---
            stmt_all = select(Student)
            result_all = await session.execute(stmt_all)
            all_students = result_all.scalars().all()
            # Нулевой словарь компетенций
            zero_comps = {k: 0.0 for k in COMP_KEYS}
            for student in all_students:
                # Диагностика
                if not student.diagnostics:
                    student.diagnostics = {"reading": 0, "history": 0, "digital": 0}
                # Компетенции
                comps_attr = student.competencies
                if not isinstance(comps_attr, dict) or any(k not in comps_attr for k in COMP_KEYS):
                    student.competencies = zero_comps
            # Сохраняем изменения
            await session.commit()