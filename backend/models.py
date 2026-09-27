"""SQLAlchemy-Modelle für ScriptNext."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    nutzer: Mapped[list["Nutzer"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    dokumente: Mapped[list["Dokument"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class Nutzer(Base):
    __tablename__ = "nutzer"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    benutzername: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    passwort_hash: Mapped[str] = mapped_column(String(255))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped["Tenant"] = relationship(back_populates="nutzer")


class Dokument(Base):
    __tablename__ = "dokumente"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), index=True)
    dateiname: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        SAEnum("verarbeitung", "fertig", "fehler", name="dokument_status"),
        default="verarbeitung",
    )
    themen_anzahl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fehler_meldung: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    tenant: Mapped["Tenant"] = relationship(back_populates="dokumente")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="dokument", cascade="all, delete-orphan")
    themen: Mapped[list["Thema"]] = relationship(back_populates="dokument", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    dokument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dokumente.id"), index=True)
    thema_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("themen.id"), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    seite: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer)

    if PGVECTOR_AVAILABLE:
        embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    dokument: Mapped["Dokument"] = relationship(back_populates="chunks")
    thema: Mapped["Thema | None"] = relationship(back_populates="chunks")


class Thema(Base):
    __tablename__ = "themen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    dokument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dokumente.id"), index=True)
    titel: Mapped[str] = mapped_column(String(500))
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    dokument: Mapped["Dokument"] = relationship(back_populates="themen")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="thema")

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)
