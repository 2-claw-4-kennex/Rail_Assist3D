import re

HINGLISH_MARKERS = (
    "kahan", "kaha", "kab", "kitna", "kitni", "batao", "bata", "hai", "hain",
    "aayegi", "jayegi", "chali", "late", "kripya", "namaste", "kaise", "konsa",
)

TRAIN_ALIASES = {
    "shatabdi": "12003",
    "gorakhdham": "12556",
    "lucknow mail": "12229",
    "pushpak": "12533",
    "gomti": "12419",
    "vande bharat": "22426",
    "garib rath": "22541",
    "malwa": "12919",
}


def is_hinglish(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in HINGLISH_MARKERS)


def extract_intent(user_text: str, board_trains: list[dict]) -> dict:
    lower = user_text.lower().strip()

    if any(w in lower for w in ("dance", "naach", "nach")):
        return {"intent": "dance", "train_number": None, "animation": "dance"}

    digit_match = re.search(r"\b(\d{5})\b", lower)
    if digit_match:
        return {"intent": "train_status", "train_number": digit_match.group(1), "animation": "talkHands"}

    compact_digits = re.sub(r"\s+", "", lower)
    spaced_match = re.search(r"(\d{5})", compact_digits)
    if spaced_match:
        return {"intent": "train_status", "train_number": spaced_match.group(1), "animation": "talkHands"}

    for t in board_trains:
        if t["name"].lower() in lower:
            return {"intent": "train_status", "train_number": t["number"], "animation": "talkHands"}

    for alias, number in TRAIN_ALIASES.items():
        if alias in lower:
            return {"intent": "train_status", "train_number": number, "animation": "talkHands"}

    if any(w in lower for w in ("board", "arrival", "departure", "lucknow", "station", "all trains")):
        return {"intent": "board_info", "train_number": None, "animation": "talkHands"}

    if any(w in lower for w in ("hello", "hi", "hey", "namaste")):
        return {"intent": "greeting", "train_number": None, "animation": "talk"}

    return {"intent": "unknown", "train_number": None, "animation": "talk"}


def format_live_reply(user_text: str, data: dict) -> str:
    hinglish = is_hinglish(user_text)
    num = data.get("trainNumber") or ""
    name = data.get("trainName") or ""
    title = f"Train {num} {name}".strip()

    delay = data.get("delayMinutes")
    loc = data.get("currentLocation") or {}
    nxt = data.get("nextStation") or {}
    station = (
        loc.get("stationName")
        or loc.get("name")
        or loc.get("stationCode")
        or nxt.get("stationName")
        or nxt.get("name")
        or ""
    )
    platform = data.get("platform") or nxt.get("platform")
    status = data.get("status") or ""

    if hinglish:
        parts = [f"{title} ka live status:"]
        if station:
            parts.append(f"abhi {station} ke paas hai")
        elif status:
            parts.append(status)
        if delay is not None and int(delay) > 0:
            parts.append(f"aur {delay} minute late chal rahi hai.")
        else:
            parts.append("aur time par chal rahi hai.")
        if platform:
            parts.append(f"Expected platform {platform} hai.")
        return " ".join(parts)

    parts = [f"{title}"]
    if station:
        parts.append(f"is currently near {station}")
    elif status:
        parts.append(f"status is {status}")
    else:
        parts.append("is currently running")

    if delay is not None and int(delay) > 0:
        parts.append(f"and is delayed by {delay} minutes.")
    else:
        parts.append("and is running on time.")

    if platform:
        parts.append(f"Expected platform is {platform}.")
    return " ".join(parts)
