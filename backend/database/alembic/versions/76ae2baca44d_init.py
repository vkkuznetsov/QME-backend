"""init

Revision ID: 76ae2baca44d
Revises:
Create Date: 2025-01-29 01:17:29.346717

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "76ae2baca44d"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "elective",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("modeus_link", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("text", sa.String(), nullable=True),
        sa.Column("questions", sa.String(), nullable=True),
        sa.Column("cluster", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "student",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fio", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("sp_code", sa.String(), nullable=False),
        sa.Column("sp_profile", sa.String(), nullable=False),
        sa.Column("potok", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "group",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("elective_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["elective_id"],
            ["elective.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "student_group",
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
        ),
        sa.PrimaryKeyConstraint("student_id", "group_id"),
    )
    op.create_table(
        "transfer",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("to_lecture_group_id", sa.Integer(), nullable=True),
        sa.Column("to_practice_group_id", sa.Integer(), nullable=True),
        sa.Column("to_lab_group_id", sa.Integer(), nullable=True),
        sa.Column("to_consultation_group_id", sa.Integer(), nullable=True),
        sa.Column("from_elective_id", sa.Integer(), nullable=False),
        sa.Column("to_elective_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["from_elective_id"],
            ["elective.id"],
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_consultation_group_id"],
            ["group.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_elective_id"],
            ["elective.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_lab_group_id"],
            ["group.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_lecture_group_id"],
            ["group.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_practice_group_id"],
            ["group.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("transfer")
    op.drop_table("student_group")
    op.drop_table("group")
    op.drop_table("student")
    op.drop_table("elective")
    # ### end Alembic commands ###
