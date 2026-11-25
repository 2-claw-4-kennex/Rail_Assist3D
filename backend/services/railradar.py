import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.railradar.in/v1"


def _compact_payload(train_no: str, raw: dict) -> dict:
    data = raw.get("data") or {}
    train = data.get("train") or {}
    loc = data.get("currentLocation") or data.get("current_location") or {}
    next_stop = data.get("nextStation") or data.get("nextStop") or data.get("next_station") or {}
    route = data.get("route") or data.get("stops") or []
    exceptions = data.get("exceptions") or []

    compact_route = []
    for stop in route[:30]:
        if isinstance(stop, dict):
            compact_route.append(
                {
                    "code": stop.get("stationCode") or stop.get("code"),
                    "name": stop.get("stationName") or stop.get("name"),
                    "platform": stop.get("platform"),
                    "eta": stop.get("expectedArrival") or stop.get("scheduledArrival") or stop.get("eta"),
                    "etd": stop.get("expectedDeparture") or stop.get("scheduledDeparture") or stop.get("etd"),
                    "delayMinutes": stop.get("delayMinutes") or stop.get("arrivalDelay") or stop.get("delay"),
                    "status": stop.get("status"),
                }
            )

    return {
        "trainNumber": data.get("trainNumber") or train.get("number") or train_no,
        "trainName": data.get("trainName") or train.get("name") or "",
        "status": data.get("status") or data.get("runningStatus") or "",
        "delayMinutes": data.get("delayMinutes") if data.get("delayMinutes") is not None else data.get("delay"),
        "currentLocation": loc,
        "nextStation": next_stop,
        "platform": data.get("platform") or next_stop.get("platform"),
        "exceptions": exceptions,
        "routeSummary": compact_route,
    }


class RailRadarClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=15.0)

    async def get_live_train(self, train_no: str, authoritative: bool = False) -> dict:
        load_dotenv(override=True)
        api_key = os.getenv("RAILRADAR_API_KEY", "").strip()
        if not api_key or api_key == "rg_paste_your_api_key_here":
            return {"success": False, "error": "MISSING_API_KEY"}

        clean = train_no.strip().upper()
        try:
            resp = await self.client.get(
                f"/trains/{clean}/live",
                headers={"Authorization": f"Bearer {api_key}"},
                params={
                    "haltsOnly": "true",
                    "lang": "en",
                    "authoritative": str(authoritative).lower(),
                },
            )
        except httpx.TimeoutException:
            return {"success": False, "error": "UPSTREAM_TIMEOUT"}
        except httpx.HTTPError as exc:
            return {"success": False, "error": f"NETWORK_ERROR: {exc}"}

        if resp.status_code == 404:
            return {"success": False, "error": "TRAIN_NOT_FOUND"}
        if resp.status_code == 422:
            return {"success": False, "error": "TRAIN_NOT_RUNNING"}
        if resp.status_code == 429:
            return {"success": False, "error": "RATE_LIMITED"}
        if resp.status_code == 401:
            return {"success": False, "error": "INVALID_API_KEY"}
        if resp.status_code >= 400:
            return {"success": False, "error": f"HTTP_{resp.status_code}"}

        payload = resp.json()
        if not payload.get("success", True):
            return {"success": False, "error": str(payload.get("error") or "UPSTREAM_ERROR")}

        return {
            "success": True,
            "data": _compact_payload(clean, payload),
            "quotaRemaining": resp.headers.get("X-RateLimit-Remaining-Month"),
        }

    async def search_train(self, query: str, limit: int = 5) -> dict:
        load_dotenv(override=True)
        api_key = os.getenv("RAILRADAR_API_KEY", "").strip()
        if not api_key or api_key == "rg_paste_your_api_key_here":
            return {"success": False, "error": "MISSING_API_KEY"}
        try:
            resp = await self.client.get(
                "/lookup/search/trains",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"q": query.strip(), "limit": limit, "lang": "en"},
            )
            if resp.status_code >= 400:
                return {"success": False, "error": f"HTTP_{resp.status_code}"}
            return resp.json()
        except httpx.HTTPError as exc:
            return {"success": False, "error": f"NETWORK_ERROR: {exc}"}

    async def close(self):
        await self.client.aclose()


railradar = RailRadarClient()
