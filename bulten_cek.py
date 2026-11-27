
import os
import re
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# =====================================================
# SPORTSTATS API
# =====================================================

BASE_URL = "https://api.sportstatsapi.com/api/v1"
API_KEY = os.getenv("SPORTSTATS_API_KEY")

if not API_KEY:
    raise SystemExit("HATA: SPORTSTATS_API_KEY bulunamadi.")

SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
})

OUTPUT_FILE = Path("bulten.json")

# Son 90 gün + gelecek 14 gün
TODAY = datetime.now(timezone.utc).date()
DATE_FROM = (TODAY - timedelta(days=90)).isoformat()
DATE_TO = (TODAY + timedelta(days=14)).isoformat()

# Ücretsiz plan: dakikada 5 istek
REQUEST_DELAY = 12.5
HISTORY_LIMIT = 12
last_request_time = 0


# =====================================================
# 25 LİG
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
# API İSTEKLERİ
# =====================================================

def api_get(path, params):
    global last_request_time

    elapsed = time.time() - last_request_time
    if last_request_time and elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    for attempt in range(4):
        response = SESSION.get(
            BASE_URL + path,
            params=params,
            timeout=50
        )
        last_request_time = time.time()

        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 60))
            print(f"API limitine ulaşıldı. {wait} saniye bekleniyor...")
            time.sleep(wait)
            continue

        response.raise_for_status()
        payload = response.json()

        if not payload.get("success"):
            raise RuntimeError(f"API başarısız yanıt verdi: {payload}")

        return payload

    raise RuntimeError("API isteği dört denemede tamamlanamadı.")


# =====================================================
# VERİ YARDIMCILARI
# =====================================================

def normalize_name(value):
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def get_team_name(team):
    if not isinstance(team, dict):
        return ""
    return team.get("display_name") or team.get("name") or ""


def get_referee(match):
    value = match.get("referee") or ""

    if isinstance(value, dict):
        return value.get("name") or ""

    return str(value).strip()


def parse_score(value):
    if not value:
        return None

    found = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value))
    if not found:
        return None

    return {
        "home": int(found.group(1)),
        "away": int(found.group(2))
    }


def get_full_score(match):
    score = parse_score(match.get("full_time_score"))

    if score:
        return score

    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    h = home.get("score")
    a = away.get("score")

    if h is not None and a is not None:
        return {"home": int(h), "away": int(a)}

    return None


def get_half_score(match):
    return parse_score(match.get("half_time_score"))


def get_status_code(match):
    return str(match.get("status_code") or "").strip().lower()


def is_finished(match):
    code = get_status_code(match)
    status = str(match.get("status") or "").strip().upper()

    return (
        code in {
            "final", "finished",
            "after_extra_time", "after_penalties"
        }
        or status in {"FT", "AET", "PEN", "FINISHED"}
    )


def get_match_date(match):
    return (
        match.get("start_at")
        or match.get("start_date")
        or ""
    )


def get_match_id(match, league, home, away):
    value = (
        match.get("match_id")
        or match.get("id")
        or match.get("code")
    )

    if value:
        return str(value)

    return f"{league['code']}-{get_match_date(match)}-{home}-{away}"


# =====================================================
# MAÇ GEÇMİŞİ KAYDI
# =====================================================

def make_history_item(match, team_key=None):
    ht = match.get("_half_score")
    ft = match.get("_full_score")

    if not ht or not ft:
        return None

    home_key = match["_home_key"]
    away_key = match["_away_key"]

    # Takımın kendi açısından attığı ve yediği goller
    if team_key == home_key:
        goals_for_ht = ht["home"]
        goals_against_ht = ht["away"]
        goals_for_ft = ft["home"]
        goals_against_ft = ft["away"]

    elif team_key == away_key:
        goals_for_ht = ht["away"]
        goals_against_ht = ht["home"]
        goals_for_ft = ft["away"]
        goals_against_ft = ft["home"]

    else:
        goals_for_ht = None
        goals_against_ht = None
        goals_for_ft = None
        goals_against_ft = None

    return {
        "date": match["date"],
        "home": match["home"],
        "away": match["away"],
        "halfTimeScore": f"{ht['home']}-{ht['away']}",
        "finalScore": f"{ft['home']}-{ft['away']}",
        "teamGoalsHT": goals_for_ht,
        "opponentGoalsHT": goals_against_ht,
        "teamGoalsFT": goals_for_ft,
        "opponentGoalsFT": goals_against_ft,
        "league": match["league"],
        "referee": match["referee"]
    }


# =====================================================
# MAÇLARI TOPLA
# =====================================================

print("=" * 60)
print("GERÇEK FUTBOL VERİSİ TOPLANIYOR")
print(f"Tarih aralığı: {DATE_FROM} - {DATE_TO}")
print(f"Geçmiş kayıt hedefi: Son {HISTORY_LIMIT} tamamlanmış maç")
print("=" * 60)

all_matches = []
seen_ids = set()
league_errors = []

for index, league in enumerate(LEAGUES, start=1):
    print(f"\n[{index}/{len(LEAGUES)}] {league['country']} - {league['league']}")

    offset = 0
    limit = 100
    league_added = 0

    try:
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
            page = payload.get("data") or []

            for raw in page:
                api_code = str(raw.get("league_code") or "")

                if api_code and api_code != league["code"]:
                    continue

                home = get_team_name(raw.get("home_team"))
                away = get_team_name(raw.get("away_team"))

                if not home or not away:
                    continue

                match_id = get_match_id(raw, league, home, away)

                if match_id in seen_ids:
                    continue

                seen_ids.add(match_id)

                full_score = get_full_score(raw)
                half_score = get_half_score(raw)
                referee = get_referee(raw)

                item = {
                    "id": match_id,
                    "country": league["country"],
                    "league": league["league"],
                    "date": get_match_date(raw),
                    "home": home,
                    "away": away,
                    "referee": referee,
                    "status": raw.get("status") or "",
                    "statusCode": get_status_code(raw),
                    "finalScore": (
                        f"{full_score['home']}-{full_score['away']}"
                        if full_score else ""
                    ),
                    "halfTimeScore": (
                        f"{half_score['home']}-{half_score['away']}"
                        if half_score else ""
                    ),
                    "homeMatches": [],
                    "awayMatches": [],
                    "refMatches": [],
                    "_home_key": normalize_name(home),
                    "_away_key": normalize_name(away),
                    "_ref_key": normalize_name(referee),
                    "_finished": is_finished(raw),
                    "_full_score": full_score,
                    "_half_score": half_score
                }

                all_matches.append(item)
                league_added += 1

            print(f"  Sayfa {offset // limit + 1}: {len(page)} maç")

            meta = payload.get("meta") or {}
            total = meta.get("total")

            if not page:
                break

            if total is not None and offset + len(page) >= int(total):
                break

            if total is None and len(page) < limit:
                break

            offset += limit

    except Exception as error:
        league_errors.append(f"{league['league']}: {error}")
        print(f"  LİG HATASI: {error}")

    print(f"  Eklenen maç: {league_added}")


# =====================================================
# TARİHE GÖRE SIRALA
# =====================================================

all_matches.sort(key=lambda x: x["date"])


# =====================================================
# TAKIM VE HAKEM GEÇMİŞLERİNİ OLUŞTUR
# =====================================================

print("\nTakım ve hakem geçmişleri hesaplanıyor...")

team_history = {}
referee_history = {}

for match in all_matches:
    home_key = match["_home_key"]
    away_key = match["_away_key"]
    referee_key = match["_ref_key"]

    # Maçtan önceki geçmiş kayıtları
    home_previous = team_history.get(home_key, [])
    away_previous = team_history.get(away_key, [])
    referee_previous = referee_history.get(referee_key, [])

    match["homeMatches"] = home_previous[-HISTORY_LIMIT:][::-1]
    match["awayMatches"] = away_previous[-HISTORY_LIMIT:][::-1]
    match["refMatches"] = referee_previous[-HISTORY_LIMIT:][::-1]

    # Sadece tamamlanmış ve iki skor bilgisi de bulunan maçlar geçmişe girer.
    if not match["_finished"]:
        continue

    if not match["_full_score"] or not match["_half_score"]:
        continue

    home_item = make_history_item(match, home_key)
    away_item = make_history_item(match, away_key)
    referee_item = make_history_item(match)

    if home_item:
        team_history.setdefault(home_key, []).append(home_item)

    if away_item:
        team_history.setdefault(away_key, []).append(away_item)

    if referee_key and referee_item:
        referee_history.setdefault(referee_key, []).append(referee_item)


# =====================================================
# JSON ÇIKTISI
# =====================================================

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
        "statusCode": match["statusCode"],
        "finalScore": match["finalScore"],
        "halfTimeScore": match["halfTimeScore"],
        "homeMatches": match["homeMatches"],
        "awayMatches": match["awayMatches"],
        "refMatches": match["refMatches"]
    })


# =====================================================
# GÜVENLİ KAYIT
# =====================================================

if not output:
    raise SystemExit(
        "HATA: Hiç maç alınamadı. Eski bulten.json korunuyor."
    )

temp_file = OUTPUT_FILE.with_suffix(".tmp")

with temp_file.open("w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

temp_file.replace(OUTPUT_FILE)


# =====================================================
# RAPOR
# =====================================================

finished_count = sum(1 for m in all_matches if m["_finished"])
with_half_time = sum(1 for m in all_matches if m["_half_score"])
with_full_time = sum(1 for m in all_matches if m["_full_score"])
with_referee = sum(1 for m in all_matches if m["referee"])

team_history_count = sum(
    1 for m in output if m["homeMatches"] or m["awayMatches"]
)
ref_history_count = sum(
    1 for m in output if m["refMatches"]
)

league_count = len(set(m["league"] for m in output))

print("\n" + "=" * 60)
print("BÜLTEN TOPLAMA TAMAMLANDI")
print(f"Toplam maç: {len(output)}")
print(f"Eslesen lig: {league_count}/25")
print(f"Tamamlanan maç: {finished_count}")
print(f"İY skoru bulunan maç: {with_half_time}")
print(f"MS skoru bulunan maç: {with_full_time}")
print(f"Hakem bilgisi bulunan maç: {with_referee}")
print(f"Takım geçmişi bulunan maç: {team_history_count}")
print(f"Hakem geçmişi bulunan maç: {ref_history_count}")

if league_errors:
    print("\nHATA ALINAN LİGLER:")
    for error in league_errors:
        print(" - " + error)

print("\nbulten.json kaydedildi.")
print("=" * 60)
