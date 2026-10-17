from __future__ import annotations

import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database.database import Base


class MarketPriceRecord(Base):
    """Authoritative normalized Agmarknet market price record."""
    __tablename__ = "krishi_market_prices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fingerprint = Column(String(64), index=True, nullable=False, doc="Deterministic hash for price snapshot")
    state = Column(String(100), index=True, default="", nullable=False)
    district = Column(String(100), index=True, default="", nullable=False)
    market = Column(String(100), index=True, nullable=False)
    commodity = Column(String(100), index=True, nullable=False)
    variety = Column(String(100), default="", nullable=False)
    grade = Column(String(50), default="", nullable=False)
    arrival_date = Column(DateTime, index=True, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    modal_price = Column(Float, nullable=False)
    unit = Column(String(50), default="Rs/Quintal", nullable=False)
    source = Column(String(100), default="data.gov.in Agmarknet", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("state", "district", "market", "commodity", "variety", "grade", "arrival_date", name="uq_market_price_slot"),
        Index("ix_market_price_search", "commodity", "market", "arrival_date"),
    )


class FarmerProfile(Base):
    """Farmer profile and notification preference record."""
    __tablename__ = "farmer_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    farmer_id = Column(String(128), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    phone = Column(String(30), default="", index=True)
    email = Column(String(255), default="")
    preferred_language = Column(String(10), default="en", nullable=False)
    sms_opt_in = Column(Boolean, default=False, nullable=False)
    push_opt_in = Column(Boolean, default=False, nullable=False)
    fcm_token = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    alerts = relationship("AlertSubscription", back_populates="farmer", cascade="all, delete-orphan")


class AlertSubscription(Base):
    """Price threshold alert subscription created by a farmer."""
    __tablename__ = "alert_subscriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id = Column(String(64), unique=True, index=True, nullable=False)
    farmer_id = Column(String(128), ForeignKey("farmer_profiles.farmer_id", ondelete="CASCADE"), index=True, nullable=False)
    commodity = Column(String(100), index=True, nullable=False)
    market = Column(String(100), index=True, nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    direction = Column(String(20), nullable=False, doc="'above' or 'below'")
    threshold_price = Column(Float, nullable=False)
    channel = Column(String(50), default="in_app", nullable=False)
    active = Column(Boolean, default=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    farmer = relationship("FarmerProfile", back_populates="alerts")


class AlertDelivery(Base):
    """Delivery and retry record for triggered price alerts."""
    __tablename__ = "alert_deliveries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id = Column(String(64), index=True, nullable=False)
    fingerprint = Column(String(64), index=True, nullable=False)
    commodity = Column(String(100), nullable=False)
    market = Column(String(100), nullable=False)
    modal_price = Column(Float, nullable=False)
    threshold_price = Column(Float, nullable=False)
    direction = Column(String(20), nullable=False)
    arrival_date = Column(DateTime, nullable=False)
    message = Column(Text, nullable=False)
    sms_status = Column(String(20), default="disabled", nullable=False)
    sms_attempts = Column(Integer, default=0, nullable=False)
    push_status = Column(String(20), default="disabled", nullable=False)
    push_attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, default="", nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("alert_id", "fingerprint", name="uq_alert_delivery_fingerprint"),
    )


class WeatherRecord(Base):
    """Agricultural weather data for a district/state."""
    __tablename__ = "weather_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    district = Column(String(100), index=True, nullable=False)
    state = Column(String(100), index=True, default="", nullable=False)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    rainfall_mm = Column(Float, default=0.0, nullable=False)
    wind_speed_kmh = Column(Float, default=0.0, nullable=False)
    condition = Column(String(100), nullable=False)
    advisory = Column(Text, nullable=False)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class MarketInsightLog(Base):
    """Log of grounded AI questions, citations, and market insights."""
    __tablename__ = "market_insight_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    query_text = Column(Text, nullable=False)
    language = Column(String(10), default="en", nullable=False)
    response_text = Column(Text, nullable=False)
    commodity = Column(String(100), nullable=True)
    market = Column(String(100), nullable=True)
    citations = Column(JSON, nullable=True)
    grounded_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
