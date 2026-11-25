import asyncio
import os
import random
import re
import time
import httpx
from dotenv import load_dotenv
from services.nlp import extract_intent, is_hinglish
from services.railradar import railradar

load_dotenv()

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
COOLDOWN_SECONDS = 60.0
CACHE_TTL_SECONDS = 60.0

SYSTEM_PROMPT = (
    "You are RailAssist 3D, a railway enquiry assistant at Lucknow Station. "
    "STRICT LANGUAGE RULE: If the user writes in English, reply ONLY in clear, natural English—zero Hindi or Hinglish words. "
    "Only reply in Hinglish if the user explicitly uses Hindi words. "
    "Use tools for verified data and never invent times, delays, locations, or platforms. "
    "If search_train returns an UP/DOWN pair for the same train name, check only the train departing from or arriving at Lucknow next. "
    "Keep replies to 1-2 short spoken sentences."
)

TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "search_train",
                "description": "Find a verified 5-digit Indian Railways train number by name.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"query": {"type": "STRING"}},
                    "required": ["query"],
                },
            },
            {
                "name": "get_live_train",
                "description": "Get live status, location, delay, and platform for a 5-digit train number.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"train_number": {"type": "STRING"}},
                    "required": ["train_number"],
                },
            },
            {
                "name": "get_lucknow_board",
                "description": "Get the Lucknow Station arrivals and departures board.",
            },
            {
                "name": "trigger_dance",
                "description": "Trigger the 3D avatar dance animation.",
            },
        ]
    }
]

GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|namaste|namaskar|good\s+(morning|afternoon|evening)|"
    r"how\s+are\s+you(\s+doing)?|what'?s\s+up|who\s+are\s+you|"
    r"aap\s+kaise\s+(hain|ho)|kaise\s+(hain|ho)|kya\s+haal\s+hai)[\s?!.]*$",
    re.IGNORECASE,
)


def _project_live_train(data: dict) -> dict:
    loc = data.get("currentLocation") or {}
    nxt = data.get("nextStation") or {}
    route = data.get("routeSummary") or []
    first_stop = route[0] if route else {}
    next_upcoming = next(
        (s for s in route if str(s.get("status") or "").lower() == "upcoming"),
        {},
    )
    return {
        "trainNumber": data.get("trainNumber"),
        "trainName": data.get("trainName"),
        "status": data.get("status"),
        "delayMinutes": data.get("delayMinutes"),
        "current": loc.get("stationName") or loc.get("name") or loc.get("stationCode"),
        "next": (
            nxt.get("stationName")
            or nxt.get("name")
            or nxt.get("stationCode")
            or next_upcoming.get("name")
            or next_upcoming.get("code")
        ),
        "nextEta": (
            nxt.get("expectedArrival")
            or nxt.get("scheduledArrival")
            or nxt.get("eta")
            or next_upcoming.get("eta")
        ),
        "originDeparture": first_stop.get("etd") or first_stop.get("eta"),
        "platform": data.get("platform") or nxt.get("platform") or next_upcoming.get("platform"),
    }


def _format_fast_reply(user_text: str, data: dict) -> str:
    info = _project_live_train(data)
    hinglish = is_hinglish(user_text)
    num = info.get("trainNumber") or ""
    name = info.get("trainName") or ""
    title = f"Train {num} {name}".strip()
    status = str(info.get("status") or "")
    status_lower = status.lower()
    station = info.get("current") or info.get("next") or ""
    platform = info.get("platform")
    dep_time = info.get("originDeparture")

    try:
        delay = int(info["delayMinutes"]) if info.get("delayMinutes") is not None else 0
    except (ValueError, TypeError):
        delay = 0

    pre_departure = any(
        k in status_lower for k in ("yet to", "not started", "scheduled", "right time to start")
    )

    if pre_departure:
        if hinglish:
            msg = f"{title} abhi {station or 'origin'} se start nahi hui hai"
            if dep_time:
                msg += f" aur {dep_time} par scheduled hai"
            if platform:
                msg += f", platform {platform} par"
            return msg + "."
        msg = f"{title} has not departed yet from {station or 'its origin'}"
        if dep_time:
            msg += f" and is scheduled at {dep_time}"
        if platform:
            msg += f" on platform {platform}"
        return msg + "."

    if hinglish:
        msg = f"{title} abhi {station} ke paas hai" if station else f"{title} chal rahi hai"
        msg += f" aur {delay} minute late hai." if delay > 0 else " aur time par chal rahi hai."
        if platform:
            msg += f" Expected platform {platform} hai."
        return msg

    msg = f"{title} is currently near {station}" if station else f"{title} is currently running"
    msg += f", delayed by {delay} minutes." if delay > 0 else " and is on time."
    if platform:
        msg += f" Expected platform is {platform}."
    return msg


def _project_search(res: dict) -> dict:
    if not res.get("success", True):
        return {"error": res.get("error", "SEARCH_FAILED")}
    raw = res.get("data")
    items = raw if isinstance(raw, list) else (raw.get("trains") if isinstance(raw, dict) else [])
    compact = [
        {
            "number": t.get("trainNumber") or t.get("number"),
            "name": t.get("trainName") or t.get("name"),
        }
        for t in (items or [])[:3]
        if isinstance(t, dict)
    ]
    return {"matches": compact}


def _project_board(board: dict) -> dict:
    def slim(rows):
        return [f"{r['number']} {r['name']} ({r['platform']}, {r['status']})" for r in rows]
    return {
        "arrivals": slim(board.get("arrivals") or []),
        "departures": slim(board.get("departures") or []),
    }


def _trim_history(history: list[dict], max_turns: int = 10) -> None:
    if len(history) <= max_turns:
        return
    del history[:-max_turns]
    while history:
        first = history[0]
        parts = first.get("parts") or []
        if first.get("role") == "user" and parts and "text" in parts[0]:
            break
        history.pop(0)


class GeminiAgent:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=6.0)
        self.sessions: dict[str, list[dict]] = {}
        self.cooldowns: dict[str, float] = {}
        self.live_cache: dict[str, tuple[float, dict]] = {}

    def clear_session(self, session_id: str):
        self.sessions.pop(session_id, None)

    def _model_cascade(self) -> list[str]:
        primary = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
        raw_fallbacks = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.8-flash")
        fallbacks = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]
        ordered = []
        for m in [primary, *fallbacks]:
            if m and m not in ordered:
                ordered.append(m)
        now = time.monotonic()
        healthy = [m for m in ordered if self.cooldowns.get(m, 0.0) <= now]
        cooling = [m for m in ordered if self.cooldowns.get(m, 0.0) > now]
        return healthy + cooling

    async def _fetch_live_cached(self, train_no: str) -> dict:
        key = train_no.strip().upper()
        now = time.monotonic()
        cached = self.live_cache.get(key)
        if cached and cached[0] > now:
            print(f"[TIMING] railradar ({key}) = 0 ms (cache hit)")
            return cached[1]
        t0 = time.perf_counter()
        try:
            res = await asyncio.wait_for(railradar.get_live_train(key), timeout=10.0)
        except asyncio.TimeoutError:
            print(f"[TIMING] railradar ({key}) = TIMEOUT (>10s)")
            return {"success": False, "error": "UPSTREAM_TIMEOUT"}
        print(f"[TIMING] railradar ({key}) = {int((time.perf_counter() - t0) * 1000)} ms")
        if res.get("success"):
            self.live_cache[key] = (now + CACHE_TTL_SECONDS, res)
        return res

    async def _post_with_failover(
        self,
        api_key: str,
        models: list[str],
        contents: list[dict],
        use_tools: bool = True,
    ) -> tuple[dict | None, str | None]:
        last_error = "UPSTREAM_UNAVAILABLE"

        for model in models:
            body = {
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 150},
            }
            if use_tools:
                body["tools"] = TOOLS

            for attempt in range(2):
                t_req = time.perf_counter()
                try:
                    resp = await self.client.post(
                        f"{GEMINI_BASE}/{model}:generateContent",
                        headers={"x-goog-api-key": api_key},
                        json=body,
                    )
                except httpx.HTTPError as exc:
                    self.cooldowns[model] = time.monotonic() + COOLDOWN_SECONDS
                    last_error = f"NETWORK_ERROR: {exc}"
                    print(f"[GEMINI {model}] {last_error}")
                    break

                elapsed_ms = int((time.perf_counter() - t_req) * 1000)
                if resp.status_code == 200:
                    print(f"[TIMING] gemini ({model}) = {elapsed_ms} ms")
                    return resp.json(), None

                try:
                    err_msg = resp.json().get("error", {}).get("message", resp.text)
                except Exception:
                    err_msg = resp.text
                last_error = f"({resp.status_code}) {err_msg}"
                print(f"[GEMINI {model} {elapsed_ms}ms] {last_error}")

                if resp.status_code in RETRYABLE_STATUS or resp.status_code == 404:
                    self.cooldowns[model] = time.monotonic() + COOLDOWN_SECONDS
                    await asyncio.sleep(random.uniform(0.1, 0.25))
                    break
                return None, last_error

        return None, last_error

    async def chat(self, session_id: str, user_text: str, board: dict) -> dict:
        load_dotenv(override=True)
        history = self.sessions.setdefault(session_id, [])
        _trim_history(history, max_turns=10)
        snapshot_len = len(history)

        cleaned = user_text.strip()
        if GREETING_PATTERNS.match(cleaned):
            reply = (
                "Main theek hoon! Boliye, Lucknow station par main aapki kya madad kar sakta hoon?"
                if is_hinglish(cleaned)
                else "Hello! I am doing great. Ask me about any train by name or 5-digit number."
            )
            history.append({"role": "user", "parts": [{"text": cleaned}]})
            history.append({"role": "model", "parts": [{"text": reply}]})
            return {"reply": reply, "animation": "talk", "liveTrain": None}

        trains = (board.get("arrivals") or []) + (board.get("departures") or [])
        fast = extract_intent(cleaned, trains)

        if fast["intent"] == "dance":
            reply = (
                "Chaliye thoda dance karte hain! Kisi train ka status chahiye toh boliye."
                if is_hinglish(cleaned)
                else "Taking a quick dance break! Ask me any train number whenever you are ready."
            )
            return {"reply": reply, "animation": "dance", "liveTrain": None}

        if fast["train_number"]:
            res = await self._fetch_live_cached(fast["train_number"])
            if res.get("success"):
                live_data = res["data"]
                reply = _format_fast_reply(cleaned, live_data)
                history.append({"role": "user", "parts": [{"text": cleaned}]})
                history.append({"role": "model", "parts": [{"text": reply}]})
                return {"reply": reply, "animation": "talkHands", "liveTrain": live_data}
            err = res.get("error", "LIVE_FETCH_FAILED")
            err_replies = {
                "TRAIN_NOT_FOUND": f"Train {fast['train_number']} was not found. Please check the 5-digit number.",
                "TRAIN_NOT_RUNNING": f"Train {fast['train_number']} is not running today.",
                "UPSTREAM_TIMEOUT": f"RailRadar timed out fetching train {fast['train_number']}. Please try again.",
                "RATE_LIMITED": "RailRadar API quota limit has been reached.",
            }
            return {
                "reply": err_replies.get(err, f"Live status for train {fast['train_number']} is unavailable right now."),
                "animation": "talk",
                "liveTrain": None,
            }

        api_key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
        if not api_key or api_key == "AIza_your_gemini_key_here":
            return {
                "reply": "Gemini API key is missing. Add GEMINI_API_KEY in backend/.env.",
                "animation": "talk",
                "liveTrain": None,
            }

        models = self._model_cascade()
        history.append({"role": "user", "parts": [{"text": cleaned}]})
        live_train = None
        animation = "talk"

        for _ in range(3):
            payload, _ = await self._post_with_failover(api_key, models, history, use_tools=True)
            if payload is None:
                del history[snapshot_len:]
                if live_train:
                    return {
                        "reply": _format_fast_reply(cleaned, live_train),
                        "animation": "talkHands",
                        "liveTrain": live_train,
                    }
                return {
                    "reply": "AI server is temporarily busy. Say or type a 5-digit train number like 12420 for instant live status.",
                    "animation": "talk",
                    "liveTrain": None,
                }

            candidates = payload.get("candidates") or []
            if not candidates or "content" not in candidates[0]:
                del history[snapshot_len:]
                return {
                    "reply": "Please repeat your train name or 5-digit train number.",
                    "animation": "talk",
                    "liveTrain": None,
                }

            candidate = candidates[0]["content"]
            history.append(candidate)
            parts = candidate.get("parts", [])
            calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if not calls:
                text = " ".join(p.get("text", "") for p in parts if "text" in p).strip()
                return {
                    "reply": text or "How can I help you with your train enquiry?",
                    "animation": animation,
                    "liveTrain": live_train,
                }

            tool_parts = []
            for call in calls:
                name = call["name"]
                args = call.get("args") or {}

                if name == "search_train":
                    t_s = time.perf_counter()
                    raw_search = await railradar.search_train(args.get("query", ""))
                    print(f"[TIMING] railradar search = {int((time.perf_counter() - t_s) * 1000)} ms")
                    result = _project_search(raw_search)
                elif name == "get_live_train":
                    res = await self._fetch_live_cached(str(args.get("train_number", "")))
                    if res.get("success"):
                        live_train = res["data"]
                        animation = "talkHands"
                        result = _project_live_train(res["data"])
                    else:
                        result = {"error": res.get("error", "LIVE_FETCH_FAILED")}
                elif name == "get_lucknow_board":
                    animation = "talkHands"
                    result = _project_board(board)
                elif name == "trigger_dance":
                    animation = "dance"
                    result = {"status": "dancing"}
                else:
                    result = {"error": "UNKNOWN_TOOL"}

                tool_parts.append(
                    {"functionResponse": {"name": name, "response": {"result": result}}}
                )

            history.append({"role": "user", "parts": tool_parts})

        return {
            "reply": "I could not finish looking up that train right now. Please try again.",
            "animation": "talk",
            "liveTrain": live_train,
        }

    async def close(self):
        await self.client.aclose()


gemini_agent = GeminiAgent()