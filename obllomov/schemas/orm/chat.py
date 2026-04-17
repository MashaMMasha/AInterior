from datetime import datetime

from sqlalchemy import String, Text, Integer, ForeignKey, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    interactions: Mapped[list["InteractionRow"]] = relationship(
        back_populates="session", order_by="InteractionRow.sequence"
    )


class InteractionRow(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    query: Mapped[str] = mapped_column(Text)
    scene_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_scene_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped["SessionRow"] = relationship(back_populates="interactions")
