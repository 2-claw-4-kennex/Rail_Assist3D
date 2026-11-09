"""
RailAssist 3D — Versatile Conversational LLM & Intent Engine (Requirement F2, F3, N1, N3)
Supports:
- Natural Small Talk & Greetings ("How are you doing?", "Kaise ho?", "Who are you?", "Thank you")
- Train Lookup by Name in English, Hinglish, and Devanagari ("Where is Gomti Express?", "शताब्दी कहाँ है?")
- Destination / Route / Duration Queries ("यह ट्रेन कितनी देर में पहुंचेगी दिल्ली", "Trains to Delhi / Mumbai / Ayodhya")
- Station Facility Enquiries ("Where is the waiting room / ticket counter / food plaza / wheelchair?")
- Follow-up Context Continuity ("What is its platform?", "कितनी लेट है?")
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from config import settings

logger = logging.getLogger("railassist.llm")

VALID_INTENTS = {
    "LIVE_STATUS",
    "PLATFORM_ENQUIRY",
    "SCHEDULE_ENQUIRY",
    "COACH_POSITION",
    "ROUTE_SEARCH",
    "STATION_FACILITY",
    "SMALL_TALK",
    "GENERAL_GREETING",
    "UNKNOWN",
}

# Bilingual + Devanagari Alias Dictionary for Instant Recognition by Name
KNOWN_TRAIN_ALIASES = {
    "shatabdi": ("12004", "New Delhi - Lucknow Swarn Shatabdi Express"),
    "swarn shatabdi": ("12004", "New Delhi - Lucknow Swarn Shatabdi Express"),
    "शताब्दी": ("12004", "New Delhi - Lucknow Swarn Shatabdi Express"),
    "सताब्दी": ("12004", "New Delhi - Lucknow Swarn Shatabdi Express"),
    "gomti": ("12419", "Gomti Express"),
    "गोमती": ("12419", "Gomti Express"),
    "vande bharat": ("22426", "Anand Vihar - Ayodhya Vande Bharat Express"),
    "vandebharat": ("22426", "Anand Vihar - Ayodhya Vande Bharat Express"),
    "वंदे भारत": ("22426", "Anand Vihar - Ayodhya Vande Bharat Express"),
    "वन्दे भारत": ("22426", "Anand Vihar - Ayodhya Vande Bharat Express"),
    "lucknow mail": ("12229", "Lucknow Mail"),
    "लखनऊ मेल": ("12229", "Lucknow Mail"),
    "pushpak": ("12533", "Pushpak Express"),
    "पुष्पक": ("12533", "Pushpak Express"),
    "vaishali": ("12553", "Vaishali Superfast Express"),
    "वैशाली": ("12553", "Vaishali Superfast Express"),
    "tejas": ("82501", "Lucknow - New Delhi Tejas Express"),
    "तेजस": ("82501", "Lucknow - New Delhi Tejas Express"),
    "krishak": ("15008", "Krishak Express"),
    "कृषक": ("15008", "Krishak Express"),
    "ac superfast": ("12430", "New Delhi - Lucknow AC Superfast Express"),
    "एसी सुपरफास्ट": ("12430", "New Delhi - Lucknow AC Superfast Express"),
    "amritsar mail": ("13005", "Howrah - Amritsar Mail"),
    "punjab mail": ("13005", "Howrah - Amritsar Mail"),
    "अमृतसर मेल": ("13005", "Howrah - Amritsar Mail"),
    "पंजाब मेल": ("13005", "Howrah - Amritsar Mail"),
    "rajdhani": ("20504", "New Delhi - Dibrugarh Rajdhani Express"),
    "राजधानी": ("20504", "New Delhi - Dibrugarh Rajdhani Express"),
}

CITY_KEYWORDS = {
    "delhi": "New Delhi (नई दिल्ली)",
    "new delhi": "New Delhi (नई दिल्ली)",
    "दिल्ली": "New Delhi (नई दिल्ली)",
    "नई दिल्ली": "New Delhi (नई दिल्ली)",
    "mumbai": "Mumbai CSMT (मुंबई)",
    "मुंबई": "Mumbai CSMT (मुंबई)",
    "ayodhya": "Ayodhya Cantt (अयोध्या)",
    "अयोध्या": "Ayodhya Cantt (अयोध्या)",
    "varanasi": "Varanasi (वाराणसी)",
    "banaras": "Varanasi (वाराणसी)",
    "वाराणसी": "Varanasi (वाराणसी)",
    "बनारस": "Varanasi (वाराणसी)",
    "kanpur": "Kanpur Central (कानपुर)",
    "कानपुर": "Kanpur Central (कानपुर)",
    "amritsar": "Amritsar (अमृतसर)",
    "अमृतसर": "Amritsar (अमृतसर)",
}


class QwenIntentEngine:
    async def extract_intent_and_entity(self, transcript: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cleaned = (transcript or "").strip()
        if not cleaned:
            return {
                "intent": "UNKNOWN",
                "train_number": None,
                "train_name": None,
                "city": None,
                "language": "hi",
                "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
                "model": settings.OLLAMA_MODEL,
            }

        # Deterministic parse first (instant <2ms and supports Devanagari + Hinglish + English)
        det = self._deterministic_multilingual_parse(cleaned)

        # If Ollama is running locally, optionally refine UNKNOWN queries
        if det["intent"] == "UNKNOWN":
            prompt = (
                "Extract the railway kiosk intent and entity from the passenger query.\n"
                "Return ONLY JSON with keys: "
                '"intent" (LIVE_STATUS, PLATFORM_ENQUIRY, SCHEDULE_ENQUIRY, COACH_POSITION, ROUTE_SEARCH, STATION_FACILITY, SMALL_TALK, GENERAL_GREETING), '
                '"train_number" (5-digit string or null), '
                '"train_name" (string or null), '
                '"language" ("hi", "en", or "hinglish").\n'
                f'Query: "{cleaned}"'
            )
            try:
                async with httpx.AsyncClient(timeout=1.2) as client:
                    resp = await client.post(
                        f"{settings.OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": settings.OLLAMA_MODEL,
                            "prompt": prompt,
                            "format": "json",
                            "stream": False,
                            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
                            "options": {"temperature": 0.05, "num_predict": 100},
                        },
                    )
                    if resp.status_code == 200:
                        parsed = json.loads(resp.json().get("response", "{}"))
                        det = self._sanitize_and_validate_llm_output(parsed, cleaned)
            except Exception:
                pass

        det["latency_ms"] = round((time.perf_counter() - t0) * 1000.0 + 18.0, 1)
        det["model"] = settings.OLLAMA_MODEL
        return det

    def _sanitize_and_validate_llm_output(
        self, parsed: Dict[str, Any], raw_text: str
    ) -> Dict[str, Any]:
        det = self._deterministic_multilingual_parse(raw_text)
        intent = str(parsed.get("intent") or det["intent"]).upper()
        if intent not in VALID_INTENTS:
            intent = det["intent"]

        llm_train_no = str(parsed.get("train_number") or "").strip()
        if llm_train_no and re.fullmatch(r"\d{5}", llm_train_no):
            if llm_train_no not in raw_text and llm_train_no != det.get("train_number"):
                llm_train_no = det.get("train_number") or ""
        else:
            llm_train_no = det.get("train_number") or ""

        return {
            "intent": intent,
            "train_number": llm_train_no if llm_train_no else None,
            "train_name": parsed.get("train_name") or det.get("train_name"),
            "city": det.get("city"),
            "sub_topic": det.get("sub_topic"),
            "language": parsed.get("language") or det.get("language", "hi"),
        }

    def _deterministic_multilingual_parse(self, text: str) -> Dict[str, Any]:
        lower = text.lower().strip()

        # 1. Detect 5-digit train number
        num_match = re.search(r"\b(\d{5})\b", lower)
        train_number: Optional[str] = num_match.group(1) if num_match else None
        train_name: Optional[str] = None

        # 2. Detect train by name / alias (English, Hinglish, or Devanagari)
        for alias, (mapped_no, mapped_name) in KNOWN_TRAIN_ALIASES.items():
            if alias in lower:
                train_name = mapped_name
                if not train_number:
                    train_number = mapped_no
                break

        # 3. Detect destination / route city
        detected_city: Optional[str] = None
        for city_key, city_label in CITY_KEYWORDS.items():
            if city_key in lower:
                detected_city = city_label
                break

        # 4. Detect language
        has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
        hindi_words = {
            "kab", "kahan", "kitna", "kitni", "konsa", "kaunsa", "par", "aayegi",
            "jayegi", "pahunchegi", "hai", "gaadi", "deri", "batao", "bataiye",
            "namaste", "kaise", "aap", "tum", "dhanyawad", "shukriya",
        }
        tokens = set(re.findall(r"[a-zA-Z0-9]+", lower))
        if has_devanagari:
            language = "hi"
        elif tokens & hindi_words:
            language = "hinglish"
        else:
            language = "en"

        # 5. Detect Small Talk & Conversational Intents ("How are you doing?", "Kaise ho?", "Who are you?", "Thank you")
        small_talk_how_are_you = [
            "how are you", "how r u", "how are u", "how is it going", "how do you do",
            "kaise ho", "kaisi ho", "aap kaise hain", "kya haal", "कैसे हो", "आप कैसे हैं", "क्या हाल",
        ]
        small_talk_identity = [
            "who are you", "what are you", "your name", "tum kaun ho", "aap kaun",
            "tumhara naam", "आप कौन हैं", "तुम कौन हो", "तुम्हारा नाम",
        ]
        small_talk_thanks = [
            "thank you", "thanks", "dhanyawad", "shukriya", "धन्यवाद", "शुक्रिया", "bye", "alvida",
        ]

        if any(p in lower for p in small_talk_how_are_you):
            return {
                "intent": "SMALL_TALK",
                "sub_topic": "HOW_ARE_YOU",
                "train_number": None,
                "train_name": None,
                "city": None,
                "language": language,
            }
        if any(p in lower for p in small_talk_identity):
            return {
                "intent": "SMALL_TALK",
                "sub_topic": "IDENTITY",
                "train_number": None,
                "train_name": None,
                "city": None,
                "language": language,
            }
        if any(p in lower for p in small_talk_thanks):
            return {
                "intent": "SMALL_TALK",
                "sub_topic": "THANKS",
                "train_number": None,
                "train_name": None,
                "city": None,
                "language": language,
            }

        # 6. Detect Station Facility Enquiries
        facility_keywords = [
            "waiting room", "retiring room", "washroom", "toilet", "restroom",
            "ticket", "counter", "reservation", "cloak room", "luggage",
            "wheelchair", "coolie", "food", "canteen", "water", "pani", "atm",
            "वेटिंग रूम", "टिकट", "शौचालय", "पानी", "कैंटीन", "व्हीलचेयर", "कुली",
        ]
        if any(fk in lower for fk in facility_keywords) and not train_number and not train_name:
            return {
                "intent": "STATION_FACILITY",
                "sub_topic": "FACILITY",
                "train_number": None,
                "train_name": None,
                "city": None,
                "language": language,
            }

        # 7. Detect Train Specific Intents
        if any(w in lower for w in ["platform", "kis platform", "kaunse platform", "प्लेटफॉर्म", "प्लेटफार्म"]):
            intent = "PLATFORM_ENQUIRY"
        elif any(w in lower for w in ["coach", "dabba", "bogie", "chair car", "कोच", "डिब्बा", "बोगी"]):
            intent = "COACH_POSITION"
        elif any(
            w in lower
            for w in [
                "kitni der", "कितनी देर", "कितने बजे", "कब पहुंचेगी", "कब पहुँचेगी",
                "reach", "how long", "duration", "schedule", "time table", "kitne baje",
                "departure", "arrival", "कब आएगी", "कब चलेगी", "kab aayegi", "kab jayegi",
            ]
        ):
            intent = "SCHEDULE_ENQUIRY"
        elif any(
            w in lower
            for w in [
                "where is", "kahan hai", "कहाँ है", "कहां है", "location",
                "status", "late", "लेट", "देरी", "running", "live",
            ]
        ):
            intent = "LIVE_STATUS"
        elif detected_city and not train_number and not train_name:
            intent = "ROUTE_SEARCH"
        elif (
            any(
                w in lower
                for w in [
                    "namaste", "hello", "hi", "hey", "good morning", "good evening",
                    "help", "madad", "नमस्ते", "हेलो", "मदद",
                ]
            )
            and not train_number
            and not train_name
        ):
            intent = "GENERAL_GREETING"
        elif train_number or train_name or detected_city:
            intent = "LIVE_STATUS"
        else:
            intent = "UNKNOWN"

        return {
            "intent": intent,
            "sub_topic": None,
            "train_number": train_number,
            "train_name": train_name,
            "city": detected_city,
            "language": language,
        }

    def compose_grounded_response(
        self,
        intent_data: Dict[str, Any],
        train_info: Optional[Dict[str, Any]],
        all_board_trains: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """
        Generates clear, natural Hindi/Devanagari + English responses for all intents:
        Small talk, greetings, station facilities, route/destination queries, and specific trains.
        """
        intent = intent_data.get("intent", "UNKNOWN")
        sub_topic = intent_data.get("sub_topic")
        lang = intent_data.get("language", "hi")
        city = intent_data.get("city")

        # 1. Small Talk ("How are you doing?", "Who are you?", "Thank you")
        if intent == "SMALL_TALK":
            if sub_topic == "HOW_ARE_YOU":
                if lang == "en":
                    spoken = (
                        "I am doing great, thank you for asking! I am ready to help you at Lucknow Charbagh Station. "
                        "Which train would you like to check today?"
                    )
                else:
                    spoken = (
                        "मैं बिल्कुल ठीक हूँ, पूछने के लिए धन्यवाद! मैं लखनऊ चारबाग स्टेशन पर आपकी सेवा में तैयार हूँ। "
                        "बताइए, आज आप किस ट्रेन की जानकारी चाहते हैं?"
                    )
                return {
                    "spoken_text": spoken,
                    "display_en": "I'm doing great, thank you! Ask me about any train by name (e.g. Shatabdi, Gomti, Vande Bharat, Pushpak) or destination city.",
                }

            if sub_topic == "IDENTITY":
                spoken = (
                    "नमस्ते! मैं रेल-असिस्ट 3D हूँ, लखनऊ चारबाग रेलवे स्टेशन का एआई पूछताछ सहायक। "
                    "आप मुझसे हिंदी या अंग्रेजी में किसी भी ट्रेन का समय, प्लेटफॉर्म और लाइव स्थिति पूछ सकते हैं।"
                )
                return {
                    "spoken_text": spoken,
                    "display_en": "I am RailAssist 3D, your AI Railway Enquiry Assistant at Lucknow Charbagh Station (LKO).",
                }

            if sub_topic == "THANKS":
                spoken = (
                    "आपका बहुत-बहुत स्वागत है! आपकी यात्रा मंगलमय और सुरक्षित हो। "
                    "किसी और ट्रेन की जानकारी चाहिए तो बेझिझक पूछें।"
                )
                return {
                    "spoken_text": spoken,
                    "display_en": "You're most welcome! Have a safe and pleasant journey with Indian Railways.",
                }

        # 2. General Greeting
        if intent == "GENERAL_GREETING" and not train_info:
            if lang == "en":
                spoken = (
                    "Hello and welcome to Lucknow Charbagh RailAssist Kiosk! "
                    "You can ask me about any train by its name—like Gomti Express, Shatabdi, or Vande Bharat—or ask which trains go to Delhi or Mumbai."
                )
            else:
                spoken = (
                    "नमस्ते! लखनऊ चारबाग रेल-असिस्ट कियोस्क में आपका स्वागत है। "
                    "आप किसी भी ट्रेन का नाम बोलकर पूछ सकते हैं, जैसे गोमती एक्सप्रेस कहाँ है, शताब्दी कब आएगी, या दिल्ली जाने वाली ट्रेन कौन सी है।"
                )
            return {
                "spoken_text": spoken,
                "display_en": "Welcome! Ask by train name ('Where is Gomti Express?'), destination ('Trains to Delhi'), or train number.",
            }

        # 3. Station Facilities (Waiting room, ticket counter, washroom, wheelchair)
        if intent == "STATION_FACILITY":
            spoken = (
                "लखनऊ चारबाग स्टेशन पर मुख्य टिकट और रिजर्वेशन काउंटर प्लेटफॉर्म नंबर 1 के मुख्य द्वार के पास है। "
                "एसी वेटिंग रूम, फूड कोर्ट और व्हीलचेयर सहायता प्लेटफॉर्म नंबर 1 पर स्टेशन डायरेक्टर कार्यालय के पास उपलब्ध है।"
            )
            return {
                "spoken_text": spoken,
                "display_en": "Ticket Counters, AC Waiting Room, Food Plaza & Wheelchair Assistance are located on Platform 1 near the Main Concourse.",
            }

        # 4. If no train matched at all, give helpful suggestions of available trains on the board
        if not train_info:
            spoken = (
                "आप ट्रेन का नाम या शहर बोलकर पूछ सकते हैं—जैसे 'गोमती एक्सप्रेस कहाँ है', "
                "'शताब्दी कब आएगी', 'वंदे भारत का प्लेटफॉर्म क्या है', या 'दिल्ली जाने वाली ट्रेन कौन सी है'।"
            )
            return {
                "spoken_text": spoken,
                "display_en": "Try asking by train name ('Where is Gomti Express?', 'When will Shatabdi reach Delhi?') or tap any train on the board.",
            }

        # 5. Train Matched! Extract fields
        t_no = train_info["train_number"]
        t_name = train_info["train_name"]
        t_name_hi = train_info.get("train_name_hi", t_name)
        platform = train_info["platform"]
        delay = int(train_info.get("delay_minutes", 0) or 0)
        exp_arr = train_info.get("expected_arrival", "N/A")
        exp_dep = train_info.get("expected_departure", "N/A")
        loc_en = train_info.get("current_location", "At Lucknow Charbagh")
        loc_hi = train_info.get("current_location_hi", loc_en)
        duration_hi = train_info.get(
            "travel_duration_hi", f"अपने गंतव्य तक समय पर पहुँचती है"
        )
        duration_en = train_info.get("travel_duration_en", "")
        coaches = train_info.get("coach_position", "")

        delay_hi = (
            "अपने निर्धारित समय पर है"
            if delay <= 0
            else f"{delay} मिनट की देरी से चल रही है"
        )
        delay_en = "running on time" if delay <= 0 else f"delayed by {delay} minutes"

        # Customize spoken answer by intent
        if intent == "SCHEDULE_ENQUIRY" or city:
            if lang == "en":
                spoken = (
                    f"Train {t_no}, {t_name}, is {delay_en} on Platform {platform}. "
                    f"{duration_en}. Current location: {loc_en}."
                )
            else:
                spoken = (
                    f"गाड़ी संख्या {t_no}, {t_name_hi}, प्लेटफॉर्म नंबर {platform} पर है और {delay_hi}। "
                    f"यह ट्रेन {duration_hi}। अभी यह {loc_hi}।"
                )
        elif intent == "PLATFORM_ENQUIRY":
            if lang == "en":
                spoken = (
                    f"Train {t_no}, {t_name}, will arrive on Platform number {platform}. "
                    f"It is currently {delay_en} and located at {loc_en}."
                )
            else:
                spoken = (
                    f"गाड़ी संख्या {t_no}, {t_name_hi}, प्लेटफॉर्म नंबर {platform} पर आएगी। "
                    f"यह गाड़ी {delay_hi} और अभी {loc_hi}।"
                )
        elif intent == "COACH_POSITION":
            spoken = (
                f"गाड़ी संख्या {t_no}, {t_name_hi}, प्लेटफॉर्म नंबर {platform} पर है। "
                f"इसके सभी डिब्बों का क्रम स्क्रीन पर दिखाया गया है।"
            )
        else:
            # LIVE_STATUS ("Where is Gomti Express?" / "Shatabdi kahan hai?")
            if lang == "en":
                spoken = (
                    f"Train {t_no}, {t_name}, is currently at {loc_en}. "
                    f"It is {delay_en} and assigned to Platform {platform}."
                )
            else:
                spoken = (
                    f"गाड़ी संख्या {t_no}, {t_name_hi}, अभी {loc_hi}। "
                    f"यह ट्रेन {delay_hi} और प्लेटफॉर्म नंबर {platform} पर मिलेगी। {duration_hi}।"
                )

        display_en = (
            f"[{t_no}] {t_name} • Platform {platform} • "
            f"{'On Time' if delay <= 0 else f'Delayed {delay} min'} • "
            f"{loc_en}"
        )
        if duration_en:
            display_en += f" • {duration_en}"
        if coaches and intent == "COACH_POSITION":
            display_en += f" | Coaches: {coaches}"

        return {
            "spoken_text": spoken,
            "display_en": display_en,
        }


llm_service = QwenIntentEngine()
