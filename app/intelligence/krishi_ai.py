from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.database.krishi_models import MarketPriceRecord
from app.database.krishi_repository import KrishiRepository

logger = logging.getLogger(__name__)

CROP_ALIASES = {
    "tomato": ["tomato", "टमाटर", "ಟೊಮೇಟೊ", "ಟೊಮೆಟೊ"],
    "onion": ["onion", "प्याज", "ಈರುಳ್ಳಿ", "pyaz", "eerulli"],
    "potato": ["potato", "आलू", "ಆಲೂಗಡ್ಡೆ", "aaloo", "aloo"],
    "brinjal": ["brinjal", "eggplant", "बैंगन", "ಬದನೆಕಾಯಿ", "baingan"],
    "cabbage": ["cabbage", "पत्ता गोभी", "ಎಲೆಕೋಸು", "patta gobhi"],
    "cauliflower": ["cauliflower", "फूलगोभी", "ಹೂಕೋಸು", "phool gobhi"],
    "green chilli": ["green chilli", "chilli", "chili", "हरी मिर्च", "ಹಸಿಮೆಣಸು", "hari mirch"],
    "carrot": ["carrot", "गाजर", "ಕ್ಯಾರೆಟ್", "gajar"],
    "wheat": ["wheat", "गेहूं", "ಗೋಧಿ", "gehun", "godhi"],
    "rice": ["rice", "चावल", "ಅಕ್ಕಿ", "chawal", "akki", "paddy"],
    "cotton": ["cotton", "कपास", "ಹತ್ತಿ", "kapas", "hatti"],
}

CROP_DISPLAY_NAMES = {
    "hi": {
        "Tomato": "टमाटर (Tomato)",
        "Onion": "प्याज (Onion)",
        "Potato": "आलू (Potato)",
        "Brinjal": "बैंगन (Brinjal)",
        "Cabbage": "पत्ता गोभी (Cabbage)",
        "Green Chilli": "हरी मिर्च (Green Chilli)",
        "Carrot": "गाजर (Carrot)",
        "Wheat": "गेहूं (Wheat)",
        "Rice": "चावल (Rice)",
        "Cotton": "कपास (Cotton)",
    },
    "kn": {
        "Tomato": "ಟೊಮೇಟೊ (Tomato)",
        "Onion": "ಈರುಳ್ಳಿ (Onion)",
        "Potato": "ಆಲೂಗಡ್ಡೆ (Potato)",
        "Brinjal": "ಬದನೆಕಾಯಿ (Brinjal)",
        "Cabbage": "ಎಲೆಕೋಸು (Cabbage)",
        "Green Chilli": "ಹಸಿಮೆಣಸು (Green Chilli)",
        "Carrot": "ಕ್ಯಾರೆಟ್ (Carrot)",
        "Wheat": "ಗೋಧಿ (Wheat)",
        "Rice": "ಅಕ್ಕಿ (Rice)",
        "Cotton": "ಹತ್ತಿ (Cotton)",
    },
}

MARKET_DISPLAY_NAMES = {
    "hi": {
        "Mysore": "मैसूर (Mysore)",
        "Bangalore": "बेंगलुरु (Bangalore)",
        "Kolar": "कोलार (Kolar)",
        "Mandya": "मंड्या (Mandya)",
        "Pune": "पुणे (Pune)",
        "Nashik": "नासिक (Nashik)",
        "Lasalgaon": "लासलगांव (Lasalgaon)",
        "Agra": "आगरा (Agra)",
        "Azadpur": "आज़ादपुर (Azadpur)",
        "Khanna": "खन्ना (Khanna)",
        "Rajkot": "राजकोट (Rajkot)",
    },
    "kn": {
        "Mysore": "ಮೈಸೂರು (Mysore)",
        "Bangalore": "ಬೆಂಗಳೂರು (Bangalore)",
        "Kolar": "ಕೋಲಾರ (Kolar)",
        "Mandya": "ಮಂಡ್ಯ (Mandya)",
        "Pune": "ಪುಣೆ (Pune)",
        "Nashik": "ನಾಸಿಕ್ (Nashik)",
        "Lasalgaon": "ಲಾಸಲಗಾಂವ್ (Lasalgaon)",
        "Agra": "ಆಗ್ರಾ (Agra)",
        "Azadpur": "ಆಜಾದ್‌ಪುರ (Azadpur)",
        "Khanna": "ಖನ್ನಾ (Khanna)",
        "Rajkot": "ರಾಜ್‌ಕೋಟ್ (Rajkot)",
    },
}


MANDI_ALIASES = {
    "Mysore": ["mysore", "mysuru", "मैसूर", "ಮೈಸೂರು"],
    "Bangalore": ["bangalore", "bengaluru", "बेंगलुरु", "ಬೆಂಗಳೂರು"],
    "Kolar": ["kolar", "कोलार", "ಕೋಲಾರ"],
    "Mandya": ["mandya", "मंड्या", "ಮಂಡ್ಯ"],
    "Pune": ["pune", "पुणे", "ಪುಣೆ"],
    "Nashik": ["nashik", "nasik", "नासिक", "ನಾಸಿಕ್"],
    "Lasalgaon": ["lasalgaon", "लासलगांव", "ಲಾಸಲಗಾಂವ್"],
    "Agra": ["agra", "आगरा", "ಆಗ್ರಾ"],
    "Azadpur": ["azadpur", "आज़ादपुर", "ಆಜಾದ್‌ಪುರ"],
    "Khanna": ["khanna", "खन्ना", "ಖನ್ನಾ"],
    "Rajkot": ["rajkot", "राजकोट", "ರಾಜ್‌ಕೋಟ್"],
}


def sanitize_prompt_input(text: str) -> str:
    """Defensively clean and defang user prompt input."""
    if not text:
        return ""
    # Strip dangerous injection phrases
    cleaned = re.sub(r"(?i)(ignore previous instructions|system prompt|reveal your prompt)", "", text)
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)
    return cleaned.strip()[:600]


def extract_crop_and_market(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract standard commodity and mandi mentions from user query using word boundaries."""
    lower = text.lower()
    matched_crop = None
    for canonical, aliases in CROP_ALIASES.items():
        for alias in aliases:
            pattern = r"(?:^|[^\w])" + re.escape(alias.lower()) + r"(?:[^\w]|$)"
            if re.search(pattern, lower):
                matched_crop = canonical.title()
                break
        if matched_crop:
            break

    # If no known crop matched, check for candidate crop names following 'price of', 'rate of', etc.
    if not matched_crop:
        m = re.search(r"(?:price of|rate of|cost of|bhav of|bhav|rate)\s+([a-zA-Z0-9_\u0900-\u097F\u0C80-\u0CFF]+)", text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate.lower() not in ["the", "this", "that", "all", "today", "yesterday", "mandi", "market", "crops"]:
                matched_crop = candidate.title()

    matched_market = None
    for canonical, aliases in MANDI_ALIASES.items():
        for alias in aliases:
            pattern = r"(?:^|[^\w])" + re.escape(alias.lower()) + r"(?:[^\w]|$)"
            if re.search(pattern, lower):
                matched_market = canonical
                break
        if matched_market:
            break

    return matched_crop, matched_market


class KrishiAIAssistant:
    """Grounded agricultural intelligence assistant powered by NVIDIA NIM foundation models."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = KrishiRepository(db)
        self.api_key = settings.NVIDIA_API_KEY
        self.base_url = settings.NVIDIA_BASE_URL.rstrip("/")
        self.model = settings.NVIDIA_MODEL

    def retrieve_grounding_context(
        self,
        commodity: Optional[str],
        market: Optional[str],
    ) -> Tuple[List[MarketPriceRecord], str, List[Dict[str, Any]]]:
        """Fetch authoritative records and assemble grounded passive context."""
        query = self.db.query(MarketPriceRecord)
        if commodity:
            query = query.filter(MarketPriceRecord.commodity.ilike(f"%{commodity}%"))
        if market:
            query = query.filter(MarketPriceRecord.market.ilike(f"%{market}%"))

        records = query.order_by(MarketPriceRecord.arrival_date.desc()).limit(15).all()

        citations: List[Dict[str, Any]] = []
        lines: List[str] = []

        for r in records:
            cite_str = f"[Mandi: {r.market}, Crop: {r.commodity}, Date: {r.arrival_date.strftime('%d/%m/%Y')}, Modal: ₹{int(r.modal_price)}/q (Min: ₹{int(r.min_price)}, Max: ₹{int(r.max_price)})]"
            lines.append(cite_str)
            citations.append({
                "market": r.market,
                "commodity": r.commodity,
                "state": r.state,
                "arrival_date": r.arrival_date.strftime("%d/%m/%Y"),
                "modal_price": r.modal_price,
                "min_price": r.min_price,
                "max_price": r.max_price,
                "source": r.source,
            })

        context_str = "\n".join(lines) if lines else "No verified records found in database."
        return records, context_str, citations

    async def answer_query(
        self,
        query: str,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Process user question with defensive prompt encapsulation,
        grounding with live database records, and multi-language response.
        """
        clean_q = sanitize_prompt_input(query)
        detected_crop, detected_market = extract_crop_and_market(clean_q)

        # Retrieve verified grounding records
        records, context_str, citations = self.retrieve_grounding_context(
            detected_crop, detected_market
        )

        # If user asked about a specific crop/market and we have no records, strictly refuse hallucination
        if detected_crop and not records:
            refusal_messages = {
                "en": f"I do not have verified Agmarknet price records for {detected_crop} in the requested market. KrishiBhav never fabricates prices. Please check back after the next market arrival update.",
                "hi": f"मेरे पास अनुरोधित मंडी में {detected_crop} के लिए प्रमाणित एगमार्कनेट भाव रिकॉर्ड उपलब्ध नहीं हैं। कृषिभाव कभी भी असत्यापित आंकड़े नहीं देता। कृपया अगली आवक अपडेट तक प्रतीक्षा करें।",
                "kn": f"ವಿನಂತಿಸಿದ ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ {detected_crop} ಗಾಗಿ ಅಧಿಕೃತ ಎಗ್ಮಾರ್ಕ್‌ನೆಟ್ ಬೆಲೆ ದಾಖಲೆಗಳು ಲಭ್ಯವಿಲ್ಲ. ಕೃಷಿಭಾವ ಎಂದಿಗೂ ಕಾಲ್ಪನಿಕ ಬೆಲೆಗಳನ್ನು ನೀಡುವುದಿಲ್ಲ. ಮುಂದಿನ ಮಾರುಕಟ್ಟೆ ನವೀಕರಣದ ನಂತರ ಪರಿಶೀಲಿಸಿ.",
            }
            refusal = refusal_messages.get(language, refusal_messages["en"])
            return {
                "response": refusal,
                "language": language,
                "grounded": True,
                "citations": [],
                "provider": "KrishiBhav Grounding Guard",
            }

        system_instructions = (
            "You are KrishiBhav AI, an authoritative, factual agricultural market intelligence assistant for Indian farmers.\n"
            "STRICT RULES:\n"
            "1. ONLY state facts and prices present in the VERIFIED_RECORDS below.\n"
            "2. NEVER fabricate, extrapolate, or guess prices.\n"
            "3. Always cite the market, arrival date, and modal price in ₹/quintal.\n"
            "4. Provide practical selling insights based solely on the recorded prices.\n"
            f"5. Answer fluently in the requested language: {language.upper()} ('en' = English, 'hi' = Hindi, 'kn' = Kannada).\n"
        )

        user_prompt = (
            f"VERIFIED_RECORDS:\n{context_str}\n\n"
            f"USER_QUESTION:\n<farmer_query>{clean_q}</farmer_query>\n\n"
            "Provide a clear, grounded response with verifiable citations."
        )

        # Try calling NVIDIA NIM endpoint
        if self.api_key and self.base_url:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 800,
                }
                async with httpx.AsyncClient(timeout=float(settings.NVIDIA_TIMEOUT_SECONDS)) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        msg = data.get("choices", [{}])[0].get("message", {})
                        content = msg.get("content") or msg.get("reasoning_content")
                        if content and isinstance(content, str) and content.strip():
                            content = content.strip()
                            self.repo.log_insight(
                                query_text=clean_q,
                                language=language,
                                response_text=content,
                                commodity=detected_crop,
                                market=detected_market,
                                citations=citations,
                                grounded_count=len(records),
                            )
                            return {
                                "response": content,
                                "language": language,
                                "grounded": True,
                                "citations": citations,
                                "provider": f"NVIDIA NIM ({self.model})",
                            }
            except Exception as exc:
                logger.warning(f"NVIDIA NIM remote call failed/timed out: {exc}. Falling back to deterministic local intelligence.")

        # Deterministic Grounded Fallback Provider
        fallback_reply = self._build_deterministic_answer(clean_q, records, language, detected_crop, detected_market)
        self.repo.log_insight(
            query_text=clean_q,
            language=language,
            response_text=fallback_reply,
            commodity=detected_crop,
            market=detected_market,
            citations=citations,
            grounded_count=len(records),
        )
        return {
            "response": fallback_reply,
            "language": language,
            "grounded": True,
            "citations": citations,
            "provider": "KrishiBhav Grounded Intelligence (Authoritative Fallback)",
        }

    def _build_deterministic_answer(
        self,
        query: str,
        records: List[MarketPriceRecord],
        language: str,
        crop: Optional[str],
        market: Optional[str],
    ) -> str:
        """Synthesize a factual, grounded answer in English, Hindi, or Kannada using retrieved records."""
        if not records:
            if language == "hi":
                return "क्षमा करें, आपके प्रश्न के लिए डेटाबेस में कोई सत्यापित एगमार्कनेट भाव उपलब्ध नहीं हैं।"
            elif language == "kn":
                return "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಪ್ರಶ್ನೆಗೆ ಡೇಟಾಬೇಸ್‌ನಲ್ಲಿ ಯಾವುದೇ ಪರಿಶೀಲಿಸಿದ ಎಗ್ಮಾರ್ಕ್‌ನೆಟ್ ಬೆಲೆಗಳು ಲಭ್ಯವಿಲ್ಲ."
            return "No verified Agmarknet price records were found matching your query."

        # Compute summary
        crops_found = sorted(list(set(r.commodity for r in records)))
        markets_found = sorted(list(set(r.market for r in records)))
        latest_rec = records[0]

        highest_rec = max(records, key=lambda x: x.modal_price)
        lowest_rec = min(records, key=lambda x: x.modal_price)

        if language == "hi":
            # Hindi synthesis
            crop_name = CROP_DISPLAY_NAMES.get("hi", {}).get(highest_rec.commodity, highest_rec.commodity)
            market_name = MARKET_DISPLAY_NAMES.get("hi", {}).get(highest_rec.market, highest_rec.market)
            lines = [
                f"कृषिभाव बाज़ार विश्लेषण ({latest_rec.arrival_date.strftime('%d/%m/%Y')} तक):",
                f"• {crop_name} का सबसे उच्चतम मॉडल भाव **{market_name} मंडी** में ₹{int(highest_rec.modal_price)}/क्विंटल (न्यूनतम: ₹{int(highest_rec.min_price)}, अधिकतम: ₹{int(highest_rec.max_price)}) दर्ज किया गया।",
            ]
            if len(records) > 1 and highest_rec.market != lowest_rec.market:
                comp_m = MARKET_DISPLAY_NAMES.get("hi", {}).get(lowest_rec.market, lowest_rec.market)
                lines.append(f"• तुलनात्मक दृष्टि से {comp_m} मंडी में भाव ₹{int(lowest_rec.modal_price)}/क्विंटल रहा।")
            lines.append("• सलाह: यदि आप अपनी उपज बेचने की योजना बना रहे हैं, तो परिवहन लागत और आवक की स्थिति को ध्यान में रखकर उच्चतम भाव वाली मंडी का चयन करें।")
            lines.append(f"\nप्रमाणित संदर्भ: [मंडी: {market_name}, फसल: {crop_name}, तारीख: {highest_rec.arrival_date.strftime('%d/%m/%Y')}, मॉडल भाव: ₹{int(highest_rec.modal_price)}/क्विंटल]")
            return "\n".join(lines)

        elif language == "kn":
            # Kannada synthesis
            crop_name = CROP_DISPLAY_NAMES.get("kn", {}).get(highest_rec.commodity, highest_rec.commodity)
            market_name = MARKET_DISPLAY_NAMES.get("kn", {}).get(highest_rec.market, highest_rec.market)
            lines = [
                f"ಕೃಷಿಭಾವ ಮಾರುಕಟ್ಟೆ ವಿಶ್ಲೇಷಣೆ ({latest_rec.arrival_date.strftime('%d/%m/%Y')} ರವರೆಗೆ):",
                f"• {crop_name} ಬೆಳೆಯ ಅತಿ ಹೆಚ್ಚಿನ ಮಾದರಿ ಬೆಲೆ **{market_name} ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ** ₹{int(highest_rec.modal_price)}/ಕ್ವಿಂಟಾಲ್ (ಕನಿಷ್ಠ: ₹{int(highest_rec.min_price)}, ಗರಿಷ್ಠ: ₹{int(highest_rec.max_price)}) ದಾಖಲಾಗಿದೆ.",
            ]
            if len(records) > 1 and highest_rec.market != lowest_rec.market:
                comp_m = MARKET_DISPLAY_NAMES.get("kn", {}).get(lowest_rec.market, lowest_rec.market)
                lines.append(f"• ಹೋಲಿಕೆಯಲ್ಲಿ {comp_m} ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಬೆಲೆ ₹{int(lowest_rec.modal_price)}/ಕ್ವಿಂಟಾಲ್ ಆಗಿದೆ.")
            lines.append("• ಸಲಹೆ: ಸಾಗಾಣಿಕೆ ವೆಚ್ಚ ಮತ್ತು ಸ್ಥಳೀಯ ಮಾರುಕಟ್ಟೆ ಆಗಮನವನ್ನು ಪರಿಗಣಿಸಿ ಉತ್ತಮ ಬೆಲೆ ಇರುವ ಮಾರುಕಟ್ಟೆಯನ್ನು ಆಯ್ಕೆ ಮಾಡಿಕೊಳ್ಳಿ.")
            lines.append(f"\nದೃಢೀಕರಿಸಿದ ಉಲ್ಲೇಖ: [ಮಾರುಕಟ್ಟೆ: {market_name}, ಬೆಳೆ: {crop_name}, ದಿನಾಂಕ: {highest_rec.arrival_date.strftime('%d/%m/%Y')}, ಮಾದರಿ ಬೆಲೆ: ₹{int(highest_rec.modal_price)}/ಕ್ವಿಂಟಾಲ್]")
            return "\n".join(lines)

        else:
            # English synthesis
            lines = [
                f"KrishiBhav Market Intelligence (as of {latest_rec.arrival_date.strftime('%d/%m/%Y')}):",
                f"• The highest modal price for **{highest_rec.commodity}** is at **{highest_rec.market} Mandi** at **₹{int(highest_rec.modal_price)}/quintal** (Min: ₹{int(highest_rec.min_price)}, Max: ₹{int(highest_rec.max_price)}).",
            ]
            if len(records) > 1 and highest_rec.market != lowest_rec.market:
                lines.append(f"• For comparison, {lowest_rec.market} reported a modal price of ₹{int(lowest_rec.modal_price)}/quintal.")
            lines.append("• Recommendation: Farmers planning dispatch should factor in transport differentials to realize the best net realization at the highest-paying mandi.")
            lines.append(f"\nGrounding Citation: [Mandi: {highest_rec.market}, Commodity: {highest_rec.commodity}, Arrival Date: {highest_rec.arrival_date.strftime('%d/%m/%Y')}, Modal Price: ₹{int(highest_rec.modal_price)}/q]")
            return "\n".join(lines)
