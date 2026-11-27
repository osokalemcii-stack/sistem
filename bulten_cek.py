
import os
import re
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# =========================================================
# SPORTSTATS API
# =========================================================

BASE_URL = "https://api.sportstatsapi.com/api/v1"
API_KEY = os.getenv("SPORTSTATS_API_KEY")

if not API_KEY:
    raise SystemExit("HATA: SPORTSTATS_API_KEY bulunamadi.")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}"
}

OUTPUT_FILE = Path("bulten.json")
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# =========================================================
# 25 HEDEF LIG
# Kodlar, SportStatsAPI lig listesinden dogrulandi.
# api_name: API'nin league_name filtresinde kullanilan
# tam lig adi.
# =========================================================

LEAGUES = [
    {"code": "l7c", "country": "Türkiye", "league": "Süper Lig", "api_name": "Turkey: Super Lig"},
    {"code": "l79", "country": "Türkiye", "league": "1. Lig", "api_name": "Turkey: 1. Lig"},

    {"code": "l30", "country": "İngiltere", "league": "Premier League", "api_name": "England: Premier League"},
    {"code": "l31", "country": "İngiltere", "league": "Championship", "api_name": "England: Championship"},

    {"code": "l4b", "country": "İtalya", "league": "Serie A", "api_name": "Italy: Serie A"},
    {"code": "l4a", "country": "İtalya", "league": "Serie B", "api_name": "Italy: Serie B"},

    {"code": "l6t", "country": "İspanya", "league": "LaLiga", "api_name": "Spain: LaLiga"},
    {"code": "l6s", "country": "İspanya", "league": "LaLiga 2", "api_name": "Spain: LaLiga2"},

    {"code": "l19", "country": "Belçika", "league": "Jupiler Pro League", "api_name": "Belgium: Jupiler Pro League"},
    {"code": "l5u", "country": "Portekiz", "league": "Liga Portugal", "api_name": "Portugal: Liga Portugal"},
    {"code": "l58", "country": "Hollanda", "league": "Eredivisie", "api_name": "Netherlands: Eredivisie"},

    {"code": "l3d", "country": "Fransa", "league": "Ligue 1", "api_name": "France: Ligue 1"},
    {"code": "l3a", "country": "Fransa", "league": "Ligue 2", "api_name": "France: Ligue 2"},

    {"code": "l3k", "country": "Almanya", "league": "Bundesliga", "api_name": "Germany: Bundesliga"},
    {"code": "l3g", "country": "Almanya", "league": "2. Bundesliga", "api_name": "Germany: 2. Bundesliga"},

    {"code": "l3n", "country": "Yunanistan", "league": "Super League", "api_name": "Greece: Super League"},
    {"code": "l7x", "country": "Rusya", "league": "Premier League", "api_name": "Russia: Premier League"},
    {"code": "l66", "country": "Suudi Arabistan", "league": "Saudi Professional League", "api_name": "Saudi Arabia: Saudi Professional League"},
    {"code": "l67", "country": "İskoçya", "league": "Premiership", "api_name": "Scotland: Premiership"},
    {"code": "l12", "country": "Avusturya", "league": "Bundesliga", "api_name": "Austria: Bundesliga"},
    {"code": "l13", "country": "Azerbaycan", "league": "Premier League", "api_name": "Azerbaijan: Premier League"},

    {"code": "l7k", "country": "ABD", "league": "MLS", "api_name": "USA: Mls"},

    {"code": "l3", "country": "Avrupa", "league": "Şampiyonlar Ligi", "api_name": "Europe: Champions League - League Phase"},
    {"code": "l4", "country": "Avrupa", "league": "Avrupa Ligi", "api_name": "Europe: Europa League - League Phase"},
    {"code": "laz", "country": "Avrupa", "league": "Konferans Ligi", "api_name": "Europe: Conference League - League Phase"},
]

# =========================================================
# TARIH ARALIGI
# Son 7 gun + bugun + gelecek 7 gun
# =========================================================

TODAY = datetime.now(timezone.utc).date()
DATE_FROM = (TODAY - timedelta(days=7)).isoformat()
DATE_TO = (TODAY + timedelta(days=7)).isoformat()

# =========================================================
# YARDIMCI FONKSIYONLAR
# =========================================================

def api_get(path, params=None):
    response = SESSION.get(
        BASE_URL + path,
        params=params,
        timeout=45
    )

    if response.status_code == 429:
        wait_time = int(response.headers.get("Retry-After", 60))
        print(f"API hiz siniri. {wait_time} saniye bekleniyor...")
        time.sleep(wait_time)
        response = SESSION.get(
            BASE_URL + path,
            params=params,
            timeout=45
        )

    response.raise_for_status()
    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(f"API basarisiz yanit verdi: {payload}")

    return payload


def team_name(team):
    if not isinstance(team, dict):
        return ""

    return (
        team.get("display_name")
        or team.get("name")
        or ""
    )


def team_key(name):
    return re.sub(r"\s+", " ", str(name).strip().lower())


def parse_score(value):
    if not value:
        return ""

    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value))

    if match:
        return f"{match.group(1)}-{match.group(2)}"

    return ""


def match_score(match):
    score = parse_score(match.get("full_time_score"))

    if score:
        return score

    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    home_score = home.get("score")
    away_score = away.get("score")

    if home_score is not None and away_score is not None:
        return f"{home_score}-{away_score}"

    return ""


def is_finished(match):
    status_code = str(match.get("status_code") or "").lower()
    status = str(match.get("status") or "").upper()

    return (
        status_code in ["final", "finished", "after_extra_time", "after_penalties"]
        or status in ["FT", "AET", "PEN", "FINISHED"]
    )


def match_datetime(match):
    date = str(match.get("start_date") or "")
    clock = str(match.get("start_time") or "")
    return f"{date} {clock}".strip()


def history_item(match):
    home = team_name(match.get("home_team"))
    away = team_name(match.get("away_team"))

    return {
        "date": match.get("start_date") or "",
        "home": home,
        "away": away,
        "score": match_score(match),
        "status": match.get("status") or "",
        "league": match.get("league_name") or ""
    }


# =========================================================
# MACLARI CEK
# =========================================================

all_matches = []
seen_matches = set()

print("BULTEN GUNCELLEME BASLADI")
print(f"Tarih araligi: {DATE_FROM} - {DATE_TO}")
print(f"Hedef lig sayisi: {len(LEAGUES)}")

for index, league in enumerate(LEAGUES, start=1):
    print(
        f"[{index}/{len(LEAGUES)}] "
        f"{league['country']} - {league['league']}"
    )

    params = {
        "league_name": league["api_name"],
        "date_from": DATE_FROM,
        "date_to": DATE_TO,
        "limit": 100,
        "order": "asc"
    }

    try:
        payload = api_get("/soccer/matches", params)
        matches = payload.get("data", [])

        added = 0

        for match in matches:
            api_league_code = str(match.get("league_code") or "")

            # Yanlis lig eslesmesini engelle.
            if api_league_code and api_league_code != league["code"]:
                continue

            home = team_name(match.get("home_team"))
            away = team_name(match.get("away_team"))

            if not home or not away:
                continue

            match_id = (
                match.get("code")
                or match.get("match_id")
                or match.get("id")
            )

            if not match_id:
                match_id = (
                    f"{league['code']}-"
                    f"{match.get('start_date')}-"
                    f"{home}-{away}"
                )

            match_id = str(match_id)

            if match_id in seen_matches:
                continue

            seen_matches.add(match_id)

            item = {
                "_id": match_id,
                "_team_home": team_key(home),
                "_team_away": team_key(away),
                "_referee": str(match.get("referee") or "").strip(),
                "_finished": is_finished(match),
                "_sort": match_datetime(match),

                "id": match_id,
                "country": league["country"],
                "league": league["league"],
                "date": match.get("start_at") or match.get("start_date") or "",
                "home": home,
                "away": away,
                "referee": match.get("referee") or "",
                "status": match.get("status") or "",
                "finalScore": match_score(match),
                "homeMatches": [],
                "awayMatches": [],
                "refMatches": []
            }

            all_matches.append(item)
            added += 1

        print(f"  Bulunan mac: {len(matches)} | Eklenen: {added}")

    except Exception as error:
        print(f"  HATA: {error}")
        raise

    # Ucretsiz API: dakikada 5 istek sinirina uy.
    if index < len(LEAGUES):
        time.sleep(12.5)


# =========================================================
# TAKIM VE HAKEM GECMISI
# Yalnizca cekilen gercek maclardan olusturulur.
# =========================================================

print("Takim ve hakem gecmisleri hazirlaniyor...")

all_matches.sort(key=lambda x: x["_sort"])

for current in all_matches:
    current_date = current["_sort"]

    home_key = current["_team_home"]
    away_key = current["_team_away"]
    referee_key = current["_referee"].lower()

    home_history = []
    away_history = []
    referee_history = []

    for previous in all_matches:
        if previous["_sort"] >= current_date:
            break

        if not previous["_finished"]:
            continue

        previous_item = history_item(previous)

        if home_key in (
            previous["_team_home"],
            previous["_team_away"]
        ):
            home_history.append(previous_item)

        if away_key in (
            previous["_team_home"],
            previous["_team_away"]
        ):
            away_history.append(previous_item)

        if (
            referee_key
            and previous["_referee"].lower() == referee_key
        ):
            referee_history.append(previous_item)

    current["homeMatches"] = home_history[-5:][::-1]
    current["awayMatches"] = away_history[-5:][::-1]
    current["refMatches"] = referee_history[-5:][::-1]


# =========================================================
# JSON OLUSTUR VE KAYDET
# =========================================================

if not all_matches:
    raise SystemExit(
        "HATA: Hic mac bulunamadi. "
        "Mevcut bulten.json korunuyor."
    )

# Uygulamanin bekledigi alanlari birak.
output = []

for match in all_matches:
    output.append({
        "id": match["id"],
        "country": match["country"],
        "league": match["league"],
        "date": match["date"],
        "home": match["home"],
        "away": match["away"],
        "referee": match["referee"],
        "status": match["status"],
        "finalScore": match["finalScore"],
        "homeMatches": match["homeMatches"],
        "awayMatches": match["awayMatches"],
        "refMatches": match["refMatches"]
    })

temporary_file = OUTPUT_FILE.with_suffix(".tmp")

with temporary_file.open("w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

temporary_file.replace(OUTPUT_FILE)

print("=" * 50)
print(f"TOPLAM MAC: {len(output)}")
print(f"ESLESTIRILEN LIG: {len(set(m['league'] for m in output))}")
print("BULTEN.JSON BASARIYLA GUNCELLENDI.")
