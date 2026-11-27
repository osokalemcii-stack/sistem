
import json
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

API_URL = "https://api.sportstatsapi.com/api/v1"
API_KEY = os.getenv("SPORTSTATS_API_KEY")
TZ = ZoneInfo("Europe/Istanbul")

if not API_KEY:
    raise SystemExit("SPORTSTATS_API_KEY bulunamadi!")

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {API_KEY}"
})

# Uygulamanin mevcut 25 lig listesi
LEAGUES = [
    ("Türkiye", "Türkiye: Süper Lig", ["super lig", "super league"]),
    ("Türkiye", "Türkiye: 1.Lig", ["1. lig", "1. league", "tff 1"]),
    ("İngiltere", "İngiltere: Premier Lig", ["premier league"]),
    ("İngiltere", "İngiltere: Championship", ["championship"]),
    ("İtalya", "İtalya: Serie A", ["serie a"]),
    ("İtalya", "İtalya: Serie B", ["serie b"]),
    ("İspanya", "İspanya: La Liga", ["la liga", "primera division"]),
    ("İspanya", "İspanya: La Liga 2", ["segunda division", "la liga 2"]),
    ("Belçika", "Belçika: Pro Lig", ["pro league", "first division a"]),
    ("Portekiz", "Portekiz: Liga Portugal", ["primeira liga", "liga portugal"]),
    ("Hollanda", "Hollanda: Eredivisie", ["eredivisie"]),
    ("Fransa", "Fransa: Ligue 1", ["ligue 1"]),
    ("Fransa", "Fransa: Ligue 2", ["ligue 2"]),
    ("Almanya", "Almanya: Bundesliga", ["bundesliga"]),
    ("Almanya", "Almanya: Bundesliga 2", ["2. bundesliga", "bundesliga 2"]),
    ("Yunanistan", "Yunanistan: Super Lig", ["super league greece", "super league 1"]),
    ("Rusya", "Rusya: Premier Lig", ["premier league russia", "russian premier"]),
    ("Suudi Arabistan", "Suudi Arabistan: Pro Lig", ["pro league saudi", "saudi pro"]),
    ("İskoçya", "İskoçya: Premier Ship", ["scottish premiership", "premiership"]),
    ("Avusturya", "Avusturya: Bundesliga", ["austrian bundesliga"]),
    ("Azerbaycan", "Azerbaycan: Premier Lig", ["premier league azerbaijan"]),
    ("ABD", "ABD: MLS", ["major league soccer", "mls"]),
    ("AVRUPA", "AVRUPA: Uefa Şampiyonlar Ligi", ["champions league"]),
    ("AVRUPA", "AVRUPA: Uefa Avrupa Ligi", ["europa league"]),
    ("AVRUPA", "AVRUPA: Uefa Konferans Ligi", ["conference league"]),
]

HISTORY_FILE = "bulten_history.json"
OUTPUT_FILE = "bulten.json"


def api_get(params):
    response = session.get(
        f"{API_URL}/soccer/matches",
        params=params,
        timeout=40
    )

    if response.status_code == 429:
        raise RuntimeError("Gunluk API istegi sinirina ulasildi.")

    response.raise_for_status()
    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(f"API hatasi: {payload}")

    return payload.get("data", []), payload.get("meta", {})


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def identify_league(name):
    value = normalize(name)

    # Daha spesifik ligleri once kontrol et
    for country, label, aliases in sorted(
        LEAGUES,
        key=lambda item: max(map(len, item[2])),
        reverse=True
    ):
        if any(alias in value for alias in aliases):
            return country, label

    return None


def parse_score(value):
    if not value:
        return None

    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value))

    if not match:
        return None

    return int(match.group(1)), int(match.group(2))


def score_token(match):
    half = parse_score(match.get("half_time_score"))
    full = parse_score(match.get("full_time_score"))

    if not half or not full:
        return None

    return f"{half[0]}-{half[1]} ({full[0]}-{full[1]})"


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_history(history):
    temp = HISTORY_FILE + ".tmp"

    with open(temp, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)

    os.replace(temp, HISTORY_FILE)


def add_history(history, match):
    if match.get("status_code") != "finished":
        return

    token = score_token(match)

    if not token:
        return

    home = match.get("home_team", {})
    away = match.get("away_team", {})

    for team in (home, away):
        team_id = str(team.get("id", ""))

        if not team_id:
            continue

        key = "team_" + team_id
        history.setdefault(key, [])

        entry = {
            "date": match.get("start_at", ""),
            "score": token
        }

        if not any(
            item.get("date") == entry["date"]
            for item in history[key]
        ):
            history[key].append(entry)

        history[key].sort(key=lambda x: x.get("date", ""))
        history[key] = history[key][-5:]


def team_history(history, team):
    team_id = str(team.get("id", ""))

    if not team_id:
        return []

    entries = history.get("team_" + team_id, [])
    return [item["score"] for item in entries[-5:]]


def main():
    now = datetime.now(TZ)
    start = now.date()
    end = (now + timedelta(days=2)).date()

    print("SportStatsAPI baglantisi kuruluyor...")

    matches, meta = api_get({
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "limit": 100,
        "order": "asc"
    })

    if meta.get("has_more"):
        print("UYARI: API 100 mac sinirina ulasti.")
        print("Bu calistirmada ilk 100 mac islenecek.")

    print(f"API'den gelen mac sayisi: {len(matches)}")

    history = load_history()

    for match in matches:
        add_history(history, match)

    bulletin = []

    for match in matches:
        league = identify_league(match.get("league_name"))

        if not league:
            continue

        country, league_label = league

        home = match.get("home_team") or {}
        away = match.get("away_team") or {}

        start_at = match.get("start_at") or ""

        try:
            local_date = datetime.fromisoformat(
                start_at.replace("Z", "+00:00")
            ).astimezone(TZ)

            date_text = local_date.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            date_text = str(match.get("start_date") or "")

        finished = match.get("status_code") == "finished"

        final_score = ""
        full = parse_score(match.get("full_time_score"))

        if finished and full:
            final_score = f"{full[0]}-{full[1]}"

        referee = match.get("referee") or "Bilinmiyor"

        bulletin.append({
            "id": f"ssa-{match.get('id')}",
            "country": country,
            "league": league_label,
            "date": date_text,
            "home": home.get("display_name") or home.get("name") or "Bilinmiyor",
            "away": away.get("display_name") or away.get("name") or "Bilinmiyor",
            "referee": referee,
            "status": "finished" if finished else "upcoming",
            "finalScore": final_score,
            "homeMatches": team_history(history, home),
            "awayMatches": team_history(history, away),
            "refMatches": []
        })

    save_history(history)

    temporary = OUTPUT_FILE + ".tmp"

    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(bulletin, file, ensure_ascii=False, indent=2)

    os.replace(temporary, OUTPUT_FILE)

    print("--------------------------------")
    print(f"Toplam mac: {len(bulletin)}")
    print(f"Takim gecmisi: {len(history)} kayit")
    print("bulten.json guncellendi.")

    found = {item["league"] for item in bulletin}
    print("Veri gelen ligler:")
    for item in sorted(found):
        print("-", item)

    print("--------------------------------")


if __name__ == "__main__":
    main()
