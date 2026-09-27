"""SQLAlchemy-Modelle für ScriptNext."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

import os
try:
    from pgvector.sqlalchemy import Vector
    _pgvector_env = os.environ.get("SCRIPTNEXT_PGVECTOR_ENABLED", "false").lower()
    PGVECTOR_AVAILABLE = _pgvector_env == "true"
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

    quelldatum: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rechtslage_gueltig_ab: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ist_veraltet: Mapped[bool] = mapped_column(default=False)
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
    seminare: Mapped[list["Seminar"]] = relationship(back_populates="thema", cascade="all, delete-orphan")

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


class Seminar(Base):
    __tablename__ = "seminare"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    thema_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("themen.id"), index=True)
    titel: Mapped[str] = mapped_column(String(500))
    zielgruppe: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dauer_minuten: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lernziele: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    thema: Mapped["Thema"] = relationship(back_populates="seminare")
    abschnitte: Mapped[list["SeminarAbschnitt"]] = relationship(
        back_populates="seminar", cascade="all, delete-orphan", order_by="SeminarAbschnitt.reihenfolge"
    )


class SeminarAbschnitt(Base):
    __tablename__ = "seminar_abschnitte"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seminar_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("seminare.id"), index=True)
    reihenfolge: Mapped[int] = mapped_column(Integer)
    typ: Mapped[str] = mapped_column(
        SAEnum("einstieg", "inhalt", "uebung", "abschluss", name="abschnitt_typ"), default="inhalt"
    )
    titel: Mapped[str] = mapped_column(String(500))
    inhalt: Mapped[str | None] = mapped_column(Text, nullable=True)
    w_frage: Mapped[str | None] = mapped_column(Text, nullable=True)
    dauer_minuten: Mapped[int | None] = mapped_column(Integer, nullable=True)

    seminar: Mapped["Seminar"] = relationship(back_populates="abschnitte")


class SeminarFeedback(Base):
    """Nutzerfeedback zu einem generierten Seminar."""
    __tablename__ = "seminar_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    seminar_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("seminare.id"), index=True)
    bewertung: Mapped[str] = mapped_column(
        SAEnum("gut", "zu_langweilig", "falsche_ebene", name="feedback_bewertung")
    )
    kommentar: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    seminar: Mapped["Seminar"] = relationship()


class SharepointToken(Base):
    """Gespeicherter MSAL-Token-Cache je Tenant für SharePoint-Zugriff."""
    __tablename__ = "sharepoint_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, index=True)
    encrypted_token: Mapped[str] = mapped_column(Text)  # serialisierter MSAL-Cache, ggf. Fernet-verschlüsselt
    account_upn: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Rechtsquelle(Base):
    """Verifizierte Rechtsquellen-DB (Gesetze, BFH-Urteile, BMF-Schreiben)."""
    __tablename__ = "rechtsquellen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titel: Mapped[str] = mapped_column(String(500))
    typ: Mapped[str] = mapped_column(
        SAEnum("gesetz", "urteil", "schreiben", name="rechtsquelle_typ"), default="gesetz", index=True
    )
    paragraph: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gesetz: Mapped[str | None] = mapped_column(String(200), nullable=True)
    aktenzeichen: Mapped[str | None] = mapped_column(String(200), nullable=True)
    volltext: Mapped[str | None] = mapped_column(Text, nullable=True)
    quelle_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    datum: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fundstelle: Mapped[str | None] = mapped_column(Text, nullable=True)
    gueltig_ab: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    externe_id: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True, index=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
