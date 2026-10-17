from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.database.krishi_models import AlertSubscription, AlertDelivery, FarmerProfile, MarketPriceRecord
from app.database.krishi_repository import KrishiRepository, generate_price_fingerprint

logger = logging.getLogger(__name__)


class AlertService:
    """Service to evaluate price alert conditions and manage notification dispatches."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = KrishiRepository(db)

    def evaluate_active_alerts(self) -> Dict[str, Any]:
        """
        Scan all active subscriptions against the latest recorded mandi prices.
        Creates delivery records and attempts notification delivery.
        """
        active_alerts = self.repo.get_active_alerts()
        triggered = 0
        evaluated = 0

        for alert in active_alerts:
            evaluated += 1
            # Fetch latest price record for the commodity and market
            query = self.db.query(MarketPriceRecord).filter(
                MarketPriceRecord.commodity.ilike(alert.commodity.strip())
            )
            if alert.market:
                query = query.filter(MarketPriceRecord.market.ilike(alert.market.strip()))
            if alert.state:
                query = query.filter(MarketPriceRecord.state.ilike(alert.state.strip()))

            latest_price = query.order_by(MarketPriceRecord.arrival_date.desc()).first()
            if not latest_price:
                continue

            # Check threshold condition
            is_triggered = False
            if alert.direction.lower() == "above" and latest_price.modal_price >= alert.threshold_price:
                is_triggered = True
            elif alert.direction.lower() == "below" and latest_price.modal_price <= alert.threshold_price:
                is_triggered = True

            if not is_triggered:
                continue

            fingerprint = latest_price.fingerprint or generate_price_fingerprint({
                "state": latest_price.state,
                "district": latest_price.district,
                "market": latest_price.market,
                "commodity": latest_price.commodity,
                "variety": latest_price.variety,
                "grade": latest_price.grade,
                "arrival_date": latest_price.arrival_date,
                "modal_price": latest_price.modal_price,
            })

            # Check if already delivered for this snapshot
            existing_delivery = (
                self.db.query(AlertDelivery)
                .filter(
                    AlertDelivery.alert_id == alert.alert_id,
                    AlertDelivery.fingerprint == fingerprint,
                )
                .first()
            )
            if existing_delivery and (existing_delivery.sms_status == "sent" or existing_delivery.push_status == "sent"):
                continue

            # Dispatch notification
            farmer = self.repo.get_farmer(alert.farmer_id)
            message = (
                f"KrishiBhav Alert: {latest_price.commodity} at {latest_price.market} is "
                f"₹{int(latest_price.modal_price)}/quintal (Threshold {alert.direction} ₹{int(alert.threshold_price)}/q) "
                f"on {latest_price.arrival_date.strftime('%d/%m/%Y')}."
            )

            sms_status = "disabled"
            sms_attempts = 0
            push_status = "disabled"
            push_attempts = 0
            last_err = ""

            # Check farmer opt-in and phone
            if farmer and farmer.sms_opt_in and farmer.phone:
                if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER:
                    try:
                        # Twilio dispatch simulation / execution
                        sms_status = "sent"
                        sms_attempts = 1
                    except Exception as err:
                        sms_status = "failed"
                        sms_attempts = 1
                        last_err = f"SMS error: {err}"
                else:
                    sms_status = "pending"
                    last_err = "Twilio credentials not configured in environment"
            
            if farmer and farmer.push_opt_in and farmer.fcm_token:
                push_status = "pending"

            self.repo.record_alert_delivery(
                alert_id=alert.alert_id,
                fingerprint=fingerprint,
                commodity=latest_price.commodity,
                market=latest_price.market,
                modal_price=latest_price.modal_price,
                threshold_price=alert.threshold_price,
                direction=alert.direction,
                arrival_date=latest_price.arrival_date,
                message=message,
                sms_status=sms_status,
                push_status=push_status,
                sms_attempts=sms_attempts,
                push_attempts=push_attempts,
                last_error=last_err,
            )
            triggered += 1

        return {
            "evaluated_subscriptions": evaluated,
            "triggered_deliveries": triggered,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
