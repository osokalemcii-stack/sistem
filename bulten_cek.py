
import os
import re
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# =====================================================
# SPORTSTATS API AYARLARI
# =====================================================

BASE_URL = "https://api.sportstatsapi.com/api/v1"
API_KEY = os.getenv("SPORTSTATS_API_KEY")

if not API_KEY:
    raise SystemExit("HATA: SPORTSTATS_API_KEY bulunamadi.")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

OUTPUT_FILE = Path("bulten.json")

# 60 gun gecmis + 14 gun gelecek
TODAY = datetime.now(timezone.utc).date()
DATE_FROM = (TODAY - timedelta(days=60)).isoformat()
DATE_TO = (TODAY + timedelta(days=14)).isoformat()

# Ucretsiz planin hiz sinirina uygun
REQUEST_DELAY = 12.5
last_request_time = 0


# =====================================================
# 25 HEDEF LIG
# =====================================================

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


# =====================================================
# API ISTEK FONKSIYONU
# =====================================================

def api_get(path, params):
    global last_request_time

    elapsed = time.time() - last_request_time
    if last_request_time and elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    response = SESSION.get(
        BASE_URL + path,
        params=params,
        timeout=50
    )
    last_request_time = time.time()

    if response.status_code == 429:
        wait = int(response.headers.get("Retry-After", 60))
        print(f"API hiz siniri. {wait} saniye bekleniyor...")
        time.sleep(wait)

        response = SESSION.get(
            BASE_URL + path,
            params=params,
            timeout=50
        )
        last_request_time = time.time()

    response.raise_for_status()
    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(f"API hatasi: {payload}")

    return payload


# =====================================================
# VERI YARDIMCILARI
# =====================================================

def get_team_name(team):
    if not isinstance(team, dict):
        return ""
    return team.get("display_name") or team.get("name") or ""


def normalize_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def get_referee(match):
    referee = match.get("referee") or ""

    if isinstance(referee, dict):
        return referee.get("name") or ""

    return str(referee).strip()


def parse_score(value):
    if not value:
        return ""

    found = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value))
    if found:
        return f"{found.group(1)}-{found.group(2)}"

    return ""


def get_score(match):
    score = parse_score(match.get("full_time_score"))
    if score:
        return score

    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    h_score = home.get("score")
    a_score = away.get("score")

    if h_score is not None and a_score is not None:
        return f"{h_score}-{a_score}"

    return ""


def is_finished(match):
    code = str(match.get("status_code") or "").lower()
    status = str(match.get("status") or "").upper()

    return (
        code in {
            "final", "finished",
            "after_extra_time", "after_penalties"
        }
        or status in {"FT", "AET", "PEN", "FINISHED"}
    )


def get_sort_date(match):
    value = (
        match.get("start_at")
        or match.get("start_date")
        or ""
    )

    return str(value)


def make_history_item(match):
    return {
        "date": match.get("start_at") or match.get("start_date") or "",
        "home": match["home"],
        "away": match["away"],
        "score": match["finalScore"],
        "status": match["status"],
        "league": match["league"]
    }


# =====================================================
# MACLARI CEK
# =====================================================

print("=" * 55)
print("25 LIG MAC VE GECMIS VERI CEKIMI")
print(f"Tarih araligi: {DATE_FROM} - {DATE_TO}")
print("=" * 55)

all_matches = []
seen_ids = set()

for index, league in enumerate(LEAGUES, start=1):
    print(
        f"\n[{index}/{len(LEAGUES)}] "
        f"{league['country']} - {league['league']}"
    )

    offset = 0
    limit = 100
    league_added = 0

    while True:
        params = {
            "league_name": league["api_name"],
            "date_from": DATE_FROM,
            "date_to": DATE_TO,
            "limit": limit,
            "offset": offset,
            "order": "asc"
        }

        payload = api_get("/soccer/matches", params)
        matches = payload.get("data", [])

        for match in matches:
            api_code = str(match.get("league_code") or "")

            if api_code and api_code != league["code"]:
                continue

            home = get_team_name(match.get("home_team"))
            away = get_team_name(match.get("away_team"))

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

            if match_id in seen_ids:
                continue

            seen_ids.add(match_id)

            item = {
                "id": match_id,
                "country": league["country"],
                "league": league["league"],
                "date": match.get("start_at") or match.get("start_date") or "",
                "home": home,
                "away": away,
                "referee": get_referee(match),
                "status": match.get("status") or "",
                "finalScore": get_score(match),

                "homeMatches": [],
                "awayMatches": [],
                "refMatches": [],

                "_home_key": normalize_name(home),
                "_away_key": normalize_name(away),
                "_ref_key": normalize_name(get_referee(match)),
                "_finished": is_finished(match),
                "_sort": get_sort_date(match)
            }

            all_matches.append(item)
            league_added += 1

        print(
            f"  Sayfa {offset // limit + 1}: "
            f"{len(matches)} kayit"
        )

        meta = payload.get("meta") or {}
        total = meta.get("total")

        if total is not None:
            if offset + len(matches) >= int(total):
                break
        elif len(matches) < limit:
            break

        if not matches:
            break

        offset += limit

    print(f"  Bu ligden eklenen: {league_added}")


# =====================================================
# TAKIM VE HAKEM GECMISI OLUSTUR
# =====================================================

print("\nTakim ve hakem gecmisleri olusturuluyor...")

all_matches.sort(key=lambda x: x["_sort"])

team_history = {}
referee_history = {}

for match in all_matches:
    home_key = match["_home_key"]
    away_key = match["_away_key"]
    referee_key = match["_ref_key"]

    home_previous = team_history.get(home_key, [])
    away_previous = team_history.get(away_key, [])
    referee_previous = referee_history.get(referee_key, [])

    match["homeMatches"] = home_previous[-5:][::-1]
    match["awayMatches"] = away_previous[-5:][::-1]
    match["refMatches"] = referee_previous[-5:][::-1]

    if match["_finished"] and match["finalScore"]:
        history = make_history_item(match)

        team_history.setdefault(home_key, []).append(history)
        team_history.setdefault(away_key, []).append(history)

        if referee_key:
            referee_history.setdefault(referee_key, []).append(history)


# =====================================================
# SON KONTROLLER
# =====================================================

if not all_matches:
    raise SystemExit(
        "HATA: Hic mac bulunamadi. "
        "Mevcut bulten.json korunuyor."
    )

finished_count = sum(1 for m in all_matches if m["_finished"])
upcoming_count = len(all_matches) - finished_count

team_history_count = sum(
    1 for m in all_matches
    if m["homeMatches"] or m["awayMatches"]
)

ref_history_count = sum(
    1 for m in all_matches if m["refMatches"]
)

league_count = len(set(m["league"] for m in all_matches))

# Yardimci alanlari JSON'a yazma.
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


# =====================================================
# GUVENLI DOSYA KAYDI
# =====================================================

temp_file = OUTPUT_FILE.with_suffix(".tmp")

with temp_file.open("w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

temp_file.replace(OUTPUT_FILE)


# =====================================================
# RAPOR
# =====================================================

print("\n" + "=" * 55)
print("BULTEN GUNCELLEME TAMAMLANDI")
print(f"Toplam mac: {len(output)}")
print(f"Eslesen lig: {league_count}/25")
print(f"Tamamlanan mac: {finished_count}")
print(f"Gelecek veya devam eden mac: {upcoming_count}")
print(f"Takim gecmisi bulunan mac: {team_history_count}")
print(f"Hakem gecmisi bulunan mac: {ref_history_count}")
print("bulten.json basariyla kaydedildi.")
print("=" * 55)
