import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

API_URL = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY")
if not API_KEY:
    raise SystemExit("API_FOOTBALL_KEY Actions secret bulunamadi.")

HEADERS = {"x-apisports-key": API_KEY}
TZ = ZoneInfo("Europe/Istanbul")

# API-Football league IDs; labels match the React app.
LEAGUES = {
    203: ("Türkiye", "Türkiye: Süper Lig"),
    204: ("Türkiye", "Türkiye: 1.Lig"),
    39: ("İngiltere", "İngiltere: Premier Lig"),
    40: ("İngiltere", "İngiltere: Championship"),
    135: ("İtalya", "İtalya: Serie A"),
    136: ("İtalya", "İtalya: Serie B"),
    140: ("İspanya", "İspanya: La Liga"),
    141: ("İspanya", "İspanya: La Liga 2"),
    144: ("Belçika", "Belçika: Pro Lig"),
    94: ("Portekiz", "Portekiz: Liga Portugal"),
    88: ("Hollanda", "Hollanda: Eredivisie"),
    61: ("Fransa", "Fransa: Ligue 1"),
    62: ("Fransa", "Fransa: Ligue 2"),
    78: ("Almanya", "Almanya: Bundesliga"),
    79: ("Almanya", "Almanya: Bundesliga 2"),
    197: ("Yunanistan", "Yunanistan: Super Lig"),
    235: ("Rusya", "Rusya: Premier Lig"),
    307: ("Suudi Arabistan", "Suudi Arabistan: Pro Lig"),
    179: ("İskoçya", "İskoçya: Premier Ship"),
    218: ("Avusturya", "Avusturya: Bundesliga"),
    419: ("Azerbaycan", "Azerbaycan: Premier Lig"),
    253: ("ABD", "ABD: MLS"),
    2: ("AVRUPA", "AVRUPA: Uefa Şampiyonlar Ligi"),
    3: ("AVRUPA", "AVRUPA: Uefa Avrupa Ligi"),
    848: ("AVRUPA", "AVRUPA: Uefa Konferans Ligi"),
}

session = requests.Session()
session.headers.update(HEADERS)
history_cache = {}

def api_get(path, params):
    response = session.get(f"{API_URL}/{path}", params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"API-Football hata: {payload['errors']}")
    return payload.get("response", [])

def score_token(item):
    score = item.get("score", {})
    ht = score.get("halftime") or {}
    ft = score.get("fulltime") or {}
    values = (ht.get("home"), ht.get("away"), ft.get("home"), ft.get("away"))
    if any(value is None for value in values):
        return None
    return f"{values[0]}-{values[1]} ({values[2]}-{values[3]})"

def last_team_matches(team_id):
    key = ("team", team_id)
    if key not in history_cache:
        rows = api_get("fixtures", {"team": team_id, "last": 5})
        rows.sort(key=lambda row: row.get("fixture", {}).get("date", ""))
        history_cache[key] = [token for row in rows if (token := score_token(row))]
        time.sleep(0.15)
    return history_cache[key]

def last_referee_matches(referee):
    if not referee or referee == "Bilinmiyor":
        return []
    key = ("referee", referee)
    if key not in history_cache:
        try:
            rows = api_get("fixtures", {"referee": referee, "last": 5})
            rows.sort(key=lambda row: row.get("fixture", {}).get("date", ""))
            history_cache[key] = [token for row in rows if (token := score_token(row))]
        except Exception as exc:
            print(f"Hakem geçmişi alınamadı ({referee}): {exc}")
            history_cache[key] = []
        time.sleep(0.15)
    return history_cache[key]

def main():
    now = datetime.now(TZ)
    start = now.date()
    end = (now + timedelta(days=2)).date()

    # One date-range request finds fixtures across all competitions.
    fixtures = api_get("fixtures", {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "timezone": "Europe/Istanbul",
    })

    selected = [
        item for item in fixtures
        if item.get("league", {}).get("id") in LEAGUES
    ]
    selected.sort(key=lambda item: item.get("fixture", {}).get("date", ""))
    selected = selected[:25]

    bulletin = []
    for item in selected:
        league_id = item["league"]["id"]
        country, league_name = LEAGUES[league_id]
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        home = teams.get("home", {})
        away = teams.get("away", {})
        referee = fixture.get("referee") or "Bilinmiyor"
        status_short = fixture.get("status", {}).get("short", "")
        finished = status_short in {"FT", "AET", "PEN"}

        fulltime = (item.get("score", {}).get("fulltime") or {})
        final_score = ""
        if finished and fulltime.get("home") is not None and fulltime.get("away") is not None:
            final_score = f'{fulltime["home"]}-{fulltime["away"]}'

        date_text = fixture.get("date", "")
        try:
            local_date = datetime.fromisoformat(date_text.replace("Z", "+00:00")).astimezone(TZ)
            date_text = local_date.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

        home_id, away_id = home.get("id"), away.get("id")
        bulletin.append({
            "id": f'api-{fixture.get("id")}',
            "country": country,
            "league": league_name,
            "date": date_text,
            "home": home.get("name", "Bilinmiyor"),
            "away": away.get("name", "Bilinmiyor"),
            "referee": referee,
            "status": "finished" if finished else "upcoming",
            "finalScore": final_score,
            "homeMatches": last_team_matches(home_id) if home_id else [],
            "awayMatches": last_team_matches(away_id) if away_id else [],
            "refMatches": last_referee_matches(referee),
        })

    # Replace the old file only after every required request succeeds.
    temporary = "bulten.json.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(bulletin, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, "bulten.json")

    print(f"API-Football: {len(bulletin)} fikstür yazıldı.")
    print(f"Takım/hakem geçmişi için yapılan benzersiz sorgu: {len(history_cache)}")
    if not bulletin:
        print("Seçili 25 ligde önümüzdeki 48 saatte fikstür bulunamadı.")

if __name__ == "__main__":
    main()
