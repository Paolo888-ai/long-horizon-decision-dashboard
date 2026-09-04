from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IndicatorDefinition(Base):
    __tablename__ = "indicator_definition"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.id"), index=True)
    external_code: Mapped[str] = mapped_column(String(160))
    name_zh: Mapped[str] = mapped_column(String(160))
    name_en: Mapped[str | None] = mapped_column(String(160))
    geography: Mapped[str] = mapped_column(String(16), index=True)
    dimension: Mapped[str] = mapped_column(String(32), index=True)
    frequency: Mapped[str] = mapped_column(String(8))
    unit: Mapped[str | None] = mapped_column(String(64))
    transformation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    quality_grade: Mapped[str] = mapped_column(String(4))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SourceRegistry(Base):
    __tablename__ = "source_registry"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(120))
    dataset: Mapped[str] = mapped_column(String(160))
    official_url: Mapped[str] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    license_status: Mapped[str] = mapped_column(String(32))
    attribution_text: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[date] = mapped_column(Date)


class RawAsset(Base):
    __tablename__ = "raw_asset"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.id"), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    request_url: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(120))
    storage_path: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(Integer)


class ObservationVintage(Base):
    __tablename__ = "observation_vintage"
    __table_args__ = (
        UniqueConstraint(
            "indicator_id", "observation_date", "vintage_at", name="uq_observation_vintage"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    indicator_id: Mapped[str] = mapped_column(ForeignKey("indicator_definition.id"), index=True)
    observation_date: Mapped[date] = mapped_column(Date, index=True)
    vintage_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="published")
    raw_asset_hash: Mapped[str | None] = mapped_column(String(128))


class FeatureMonthly(Base):
    __tablename__ = "feature_monthly"
    __table_args__ = (
        UniqueConstraint(
            "indicator_id", "month", "vintage_cutoff", name="uq_feature_monthly_vintage"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    indicator_id: Mapped[str] = mapped_column(ForeignKey("indicator_definition.id"), index=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    vintage_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_observation_date: Mapped[date] = mapped_column(Date)
    level: Mapped[float | None] = mapped_column(Float)
    robust_z: Mapped[float | None] = mapped_column(Float)
    momentum_3m: Mapped[float | None] = mapped_column(Float)
    change_12m: Mapped[float | None] = mapped_column(Float)
    freshness_weight: Mapped[float] = mapped_column(Float)
    is_carried_forward: Mapped[bool] = mapped_column(Boolean)


class ModelVersion(Base):
    __tablename__ = "model_version"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(32))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)


class PublicationSnapshot(Base):
    __tablename__ = "publication_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "geography", "publication_date", "model_version_id", name="uq_publication_snapshot"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    geography: Mapped[str] = mapped_column(String(16), index=True)
    publication_date: Mapped[date] = mapped_column(Date, index=True)
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_version.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(128), unique=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)


class ManualAdjustment(Base):
    __tablename__ = "manual_adjustment"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    publication_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("publication_snapshot.id"))
    scenario_key: Mapped[str] = mapped_column(String(64))
    original_probability: Mapped[float] = mapped_column(Float)
    adjusted_probability: Mapped[float] = mapped_column(Float)
    evidence: Mapped[str] = mapped_column(Text)
    proposed_by: Mapped[str] = mapped_column(String(120))
    approved_by: Mapped[str] = mapped_column(String(120))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QualityIssue(Base):
    __tablename__ = "quality_issue"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    indicator_id: Mapped[str | None] = mapped_column(ForeignKey("indicator_definition.id"))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String(16))
    issue_type: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
