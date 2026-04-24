from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "chat"}

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.users.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    interactions: Mapped[list["InteractionRow"]] = relationship(
        back_populates="session",
        order_by="InteractionRow.sequence",
        cascade="all, delete-orphan",
    )


class InteractionRow(Base):
    __tablename__ = "interactions"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_chat_interactions_session_sequence"),
        {"schema": "chat"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat.sessions.session_id", ondelete="CASCADE"),
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer)
    query: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped["SessionRow"] = relationship(back_populates="interactions")
    stages: Mapped[list["StageRow"]] = relationship(
        back_populates="interaction",
        order_by="StageRow.id",
        cascade="all, delete-orphan",
    )


class StageRow(Base):
    __tablename__ = "stages"
    __table_args__ = {"schema": "chat"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat.interactions.id", ondelete="CASCADE"),
        index=True,
    )
    stage_name: Mapped[str] = mapped_column(String(255))
    scene_plan: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    raw_scene_plan: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    interaction: Mapped["InteractionRow"] = relationship(back_populates="stages")
