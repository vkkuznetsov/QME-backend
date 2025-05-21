import math
import numbers
import pandas as pd
from sqlalchemy import select

from backend.database.database import AsyncSessionLocal
from backend.database.models.student import Student


class StudentsDataParser:
    """
    Parser to update Student.diagnostics and Student.competencies
    from uploaded Excel files.
    """

    def __init__(self, diagnostics_file, competencies_file):
        self.diagnostics_file = diagnostics_file
        self.competencies_file = competencies_file

    async def __call__(self):
        # Read diagnostics sheet with nested headers
        df_diag = pd.read_excel(
            self.diagnostics_file.file,
            sheet_name="Контингент",
            header=[0, 1]
        )
        # Flatten MultiIndex columns if present
        if isinstance(df_diag.columns, pd.MultiIndex):
            new_cols = []
            for top, sub in df_diag.columns:
                sub_str = str(sub).strip()
                if sub_str.startswith("Unnamed"):
                    new_cols.append(top)
                else:
                    new_cols.append(f"{top} {sub_str}")
            df_diag.columns = new_cols

        # Keep only rows with valid corporate email
        df_diag = df_diag[df_diag["Корпоративный Email"].str.contains("@", na=False)]

        # Read competencies sheet (flat header)
        df_comp = pd.read_excel(self.competencies_file.file, sheet_name=0)
        df_comp = df_comp[df_comp["Названия строк"].notna()]

        async with AsyncSessionLocal() as session:
            # Update diagnostics by email
            for _, row in df_diag.iterrows():
                email = row["Корпоративный Email"]
                # Average analytic reading scores
                reading_cols = [col for col in df_diag.columns if col.startswith("Аналитическое чтение")]
                def to_float(val):
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None
                reading_values = [to_float(row[col]) for col in reading_cols if to_float(row[col]) is not None]
                avg_reading = sum(reading_values) / len(reading_values) if reading_values else None
                # Average digital literacy scores
                digital_cols = [col for col in df_diag.columns if col.startswith("Цифровая грамотность")]
                digital_values = [to_float(row[col]) for col in digital_cols if to_float(row[col]) is not None]
                avg_digital = sum(digital_values) / len(digital_values) if digital_values else None
                history_val = to_float(row["История России"])
                scores = {
                    "reading": avg_reading,
                    "history": history_val,
                    "digital": avg_digital
                }
                # Replace NaN or None with 0 for JSON compatibility
                for k, v in scores.items():
                    if v is None or (isinstance(v, float) and math.isnan(v)):
                        scores[k] = 0

                stmt = select(Student).where(Student.email == email)
                result = await session.execute(stmt)
                student = result.scalar_one_or_none()
                if student:
                    student.diagnostics = scores

            # Update competencies by full name
            for _, row in df_comp.iterrows():
                fio = row["Названия строк"]
                indices = list(range(1, 7)) + [8]
                comps = [
                    float(row[f"Среднее по полю Н-{i}"])
                    for i in indices
                ]
                stmt = select(Student).where(Student.fio == fio)
                result = await session.execute(stmt)
                student = result.scalar_one_or_none()
                if student:
                    student.competencies = comps

            await session.commit()