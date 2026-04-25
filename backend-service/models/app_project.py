from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend_service.db import Base


class AppProjectRow(Base):
    """Сохраняемый проект UI (id строкой, сцена, привязка к чату)."""

    __tablename__ = "app_projects"
    __table_args__ = {"schema": "interior"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255))
    objects: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    conversation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
