from __future__ import annotations

import datetime
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.database.krishi_models import (
    MarketPriceRecord,
    FarmerProfile,
    AlertSubscription,
    AlertDelivery,
    WeatherRecord,
    MarketInsightLog,
)

logger = logging.getLogger(__name__)


def generate_price_fingerprint(record: Dict[str, Any]) -> str:
    """Generate deterministic SHA-256 fingerprint for a market price snapshot."""
    arrival_str = (
        record["arrival_date"].strftime("%Y-%m-%d")
        if isinstance(record.get("arrival_date"), (datetime.date, datetime.datetime))
        else str(record.get("arrival_date", ""))
    )
    raw = f"{record.get('state','')}|{record.get('district','')}|{record.get('market','')}|{record.get('commodity','')}|{record.get('variety','')}|{record.get('grade','')}|{arrival_str}|{record.get('modal_price','')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class KrishiRepository:
    """Repository handling all agricultural persistence and analytical queries."""

    def __init__(self, db: Session):
        self.db = db

    def save_market_prices(self, records: List[Dict[str, Any]]) -> int:
        """Upsert Agmarknet market price records."""
        inserted_or_updated = 0
        for rec in records:
            fingerprint = generate_price_fingerprint(rec)
            arrival_date = rec["arrival_date"]
            if isinstance(arrival_date, str):
                try:
                    arrival_date = datetime.datetime.fromisoformat(arrival_date)
                except Exception:
                    continue

            # Query existing slot
            existing = (
                self.db.query(MarketPriceRecord)
                .filter(
                    MarketPriceRecord.state == rec.get("state", ""),
                    MarketPriceRecord.district == rec.get("district", ""),
                    MarketPriceRecord.market == rec["market"],
                    MarketPriceRecord.commodity == rec["commodity"],
                    MarketPriceRecord.variety == rec.get("variety", ""),
                    MarketPriceRecord.grade == rec.get("grade", ""),
                    MarketPriceRecord.arrival_date == arrival_date,
                )
                .first()
            )

            if existing:
                existing.min_price = float(rec["min_price"])
                existing.max_price = float(rec["max_price"])
                existing.modal_price = float(rec["modal_price"])
                existing.fingerprint = fingerprint
                existing.source = rec.get("source", "data.gov.in Agmarknet")
                existing.updated_at = datetime.datetime.utcnow()
            else:
                new_entry = MarketPriceRecord(
                    fingerprint=fingerprint,
                    state=rec.get("state", ""),
                    district=rec.get("district", ""),
                    market=rec["market"],
                    commodity=rec["commodity"],
                    variety=rec.get("variety", ""),
                    grade=rec.get("grade", ""),
                    arrival_date=arrival_date,
                    min_price=float(rec["min_price"]),
                    max_price=float(rec["max_price"]),
                    modal_price=float(rec["modal_price"]),
                    unit=rec.get("unit", "Rs/Quintal"),
                    source=rec.get("source", "data.gov.in Agmarknet"),
                    created_at=datetime.datetime.utcnow(),
                    updated_at=datetime.datetime.utcnow(),
                )
                self.db.add(new_entry)
            inserted_or_updated += 1

        self.db.commit()
        return inserted_or_updated

    def get_market_prices(
        self,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        commodity: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[MarketPriceRecord], int]:
        """Query market prices with filtering, text search, and pagination."""
        query = self.db.query(MarketPriceRecord)

        if state:
            query = query.filter(func.lower(MarketPriceRecord.state) == state.strip().lower())
        if district:
            query = query.filter(func.lower(MarketPriceRecord.district) == district.strip().lower())
        if market:
            query = query.filter(func.lower(MarketPriceRecord.market) == market.strip().lower())
        if commodity:
            query = query.filter(func.lower(MarketPriceRecord.commodity) == commodity.strip().lower())

        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(MarketPriceRecord.commodity).like(term),
                    func.lower(MarketPriceRecord.market).like(term),
                    func.lower(MarketPriceRecord.district).like(term),
                    func.lower(MarketPriceRecord.state).like(term),
                )
            )

        total = query.count()
        results = (
            query.order_by(
                desc(MarketPriceRecord.arrival_date),
                MarketPriceRecord.commodity,
                MarketPriceRecord.market,
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return results, total

    def get_market_price_history(
        self,
        commodity: str,
        market: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        days: int = 7,
    ) -> List[MarketPriceRecord]:
        """Fetch chronological records over the specified window (up to 7 days)."""
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        query = self.db.query(MarketPriceRecord).filter(
            func.lower(MarketPriceRecord.commodity) == commodity.strip().lower(),
            MarketPriceRecord.arrival_date >= cutoff,
        )
        if market:
            query = query.filter(func.lower(MarketPriceRecord.market) == market.strip().lower())
        if state:
            query = query.filter(func.lower(MarketPriceRecord.state) == state.strip().lower())
        if district:
            query = query.filter(func.lower(MarketPriceRecord.district) == district.strip().lower())

        return query.order_by(MarketPriceRecord.arrival_date.asc()).all()

    def calculate_trend_for_record(self, record: MarketPriceRecord) -> Dict[str, Any]:
        """Compute 7-day trend direction, percentage change, and history points for a record."""
        history = self.get_market_price_history(
            commodity=record.commodity,
            market=record.market,
            state=record.state,
            district=record.district,
            days=7,
        )

        if len(history) < 2:
            return {
                "direction": "steady",
                "percentage_change": 0.0,
                "first_price": record.modal_price,
                "latest_price": record.modal_price,
                "points_count": len(history),
            }

        first_price = history[0].modal_price
        latest_price = history[-1].modal_price

        if first_price > 0:
            pct_change = round(((latest_price - first_price) / first_price) * 100, 2)
        else:
            pct_change = 0.0

        if pct_change > 1.5:
            direction = "up"
        elif pct_change < -1.5:
            direction = "down"
        else:
            direction = "steady"

        return {
            "direction": direction,
            "percentage_change": pct_change,
            "first_price": first_price,
            "latest_price": latest_price,
            "points_count": len(history),
        }

    def get_distinct_commodities(self) -> List[str]:
        """List all distinct agricultural commodities available in the database."""
        rows = (
            self.db.query(MarketPriceRecord.commodity)
            .distinct()
            .order_by(MarketPriceRecord.commodity.asc())
            .all()
        )
        return [row[0] for row in rows if row[0]]

    def get_distinct_markets(self) -> List[Dict[str, str]]:
        """List distinct mandis along with their district and state."""
        rows = (
            self.db.query(
                MarketPriceRecord.market,
                MarketPriceRecord.district,
                MarketPriceRecord.state,
            )
            .distinct()
            .order_by(MarketPriceRecord.market.asc())
            .all()
        )
        return [
            {"market": row[0], "district": row[1], "state": row[2]}
            for row in rows
            if row[0]
        ]

    # --- Farmer Profiles ---

    def create_or_update_farmer(
        self,
        farmer_id: str,
        name: str,
        phone: str = "",
        email: str = "",
        preferred_language: str = "en",
        sms_opt_in: bool = False,
        push_opt_in: bool = False,
        fcm_token: Optional[str] = None,
    ) -> FarmerProfile:
        """Create or update a farmer profile."""
        farmer = (
            self.db.query(FarmerProfile)
            .filter(FarmerProfile.farmer_id == farmer_id)
            .first()
        )
        if farmer:
            farmer.name = name
            farmer.phone = phone
            farmer.email = email
            farmer.preferred_language = preferred_language
            farmer.sms_opt_in = sms_opt_in
            farmer.push_opt_in = push_opt_in
            if fcm_token:
                farmer.fcm_token = fcm_token
            farmer.updated_at = datetime.datetime.utcnow()
        else:
            farmer = FarmerProfile(
                farmer_id=farmer_id,
                name=name,
                phone=phone,
                email=email,
                preferred_language=preferred_language,
                sms_opt_in=sms_opt_in,
                push_opt_in=push_opt_in,
                fcm_token=fcm_token,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow(),
            )
            self.db.add(farmer)

        self.db.commit()
        self.db.refresh(farmer)
        return farmer

    def get_farmer(self, farmer_id: str) -> Optional[FarmerProfile]:
        """Retrieve farmer profile by id."""
        return (
            self.db.query(FarmerProfile)
            .filter(FarmerProfile.farmer_id == farmer_id)
            .first()
        )

    # --- Alert Subscriptions ---

    def create_alert_subscription(
        self,
        alert_id: str,
        farmer_id: str,
        commodity: str,
        direction: str,
        threshold_price: float,
        market: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        channel: str = "in_app",
    ) -> AlertSubscription:
        """Register a new price threshold alert subscription."""
        alert = AlertSubscription(
            alert_id=alert_id,
            farmer_id=farmer_id,
            commodity=commodity,
            market=market,
            state=state,
            district=district,
            direction=direction.lower(),
            threshold_price=float(threshold_price),
            channel=channel,
            active=True,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_farmer_alerts(self, farmer_id: str) -> List[AlertSubscription]:
        """Fetch all active alerts for a farmer."""
        return (
            self.db.query(AlertSubscription)
            .filter(AlertSubscription.farmer_id == farmer_id, AlertSubscription.active == True)
            .order_by(desc(AlertSubscription.created_at))
            .all()
        )

    def deactivate_alert(self, alert_id: str, farmer_id: Optional[str] = None) -> bool:
        """Deactivate an alert subscription."""
        query = self.db.query(AlertSubscription).filter(AlertSubscription.alert_id == alert_id)
        if farmer_id:
            query = query.filter(AlertSubscription.farmer_id == farmer_id)
        alert = query.first()
        if not alert:
            return False
        alert.active = False
        alert.updated_at = datetime.datetime.utcnow()
        self.db.commit()
        return True

    def get_active_alerts(self) -> List[AlertSubscription]:
        """Retrieve all active subscriptions for the background evaluation engine."""
        return (
            self.db.query(AlertSubscription)
            .filter(AlertSubscription.active == True)
            .all()
        )

    def record_alert_delivery(
        self,
        alert_id: str,
        fingerprint: str,
        commodity: str,
        market: str,
        modal_price: float,
        threshold_price: float,
        direction: str,
        arrival_date: datetime.datetime,
        message: str,
        sms_status: str = "disabled",
        push_status: str = "disabled",
        sms_attempts: int = 0,
        push_attempts: int = 0,
        last_error: str = "",
    ) -> AlertDelivery:
        """Record or update alert notification delivery tracking."""
        delivery = (
            self.db.query(AlertDelivery)
            .filter(
                AlertDelivery.alert_id == alert_id,
                AlertDelivery.fingerprint == fingerprint,
            )
            .first()
        )
        if delivery:
            delivery.sms_status = sms_status
            delivery.push_status = push_status
            delivery.sms_attempts = sms_attempts
            delivery.push_attempts = push_attempts
            delivery.last_error = last_error
            if sms_status == "sent" or push_status == "sent":
                delivery.delivered_at = datetime.datetime.utcnow()
        else:
            delivery = AlertDelivery(
                alert_id=alert_id,
                fingerprint=fingerprint,
                commodity=commodity,
                market=market,
                modal_price=modal_price,
                threshold_price=threshold_price,
                direction=direction,
                arrival_date=arrival_date,
                message=message,
                sms_status=sms_status,
                push_status=push_status,
                sms_attempts=sms_attempts,
                push_attempts=push_attempts,
                last_error=last_error,
                delivered_at=datetime.datetime.utcnow() if (sms_status == "sent" or push_status == "sent") else None,
                created_at=datetime.datetime.utcnow(),
            )
            self.db.add(delivery)

        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    # --- Weather & Agromet Records ---

    def save_weather(
        self,
        district: str,
        state: str,
        temperature: float,
        humidity: float,
        rainfall_mm: float,
        wind_speed_kmh: float,
        condition: str,
        advisory: str,
    ) -> WeatherRecord:
        """Store or update district agricultural weather record."""
        rec = (
            self.db.query(WeatherRecord)
            .filter(
                func.lower(WeatherRecord.district) == district.strip().lower(),
                func.lower(WeatherRecord.state) == state.strip().lower(),
            )
            .first()
        )
        if rec:
            rec.temperature = temperature
            rec.humidity = humidity
            rec.rainfall_mm = rainfall_mm
            rec.wind_speed_kmh = wind_speed_kmh
            rec.condition = condition
            rec.advisory = advisory
            rec.recorded_at = datetime.datetime.utcnow()
        else:
            rec = WeatherRecord(
                district=district,
                state=state,
                temperature=temperature,
                humidity=humidity,
                rainfall_mm=rainfall_mm,
                wind_speed_kmh=wind_speed_kmh,
                condition=condition,
                advisory=advisory,
                recorded_at=datetime.datetime.utcnow(),
            )
            self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def get_weather(self, district: str, state: Optional[str] = None) -> Optional[WeatherRecord]:
        """Fetch latest agricultural weather report for a district."""
        query = self.db.query(WeatherRecord).filter(
            func.lower(WeatherRecord.district) == district.strip().lower()
        )
        if state:
            query = query.filter(func.lower(WeatherRecord.state) == state.strip().lower())
        return query.order_by(desc(WeatherRecord.recorded_at)).first()

    # --- AI Logs & Citations ---

    def log_insight(
        self,
        query_text: str,
        language: str,
        response_text: str,
        commodity: Optional[str] = None,
        market: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        grounded_count: int = 0,
    ) -> MarketInsightLog:
        """Log grounded AI conversation and citations."""
        log = MarketInsightLog(
            query_text=query_text,
            language=language,
            response_text=response_text,
            commodity=commodity,
            market=market,
            citations=citations or [],
            grounded_count=grounded_count,
            created_at=datetime.datetime.utcnow(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
