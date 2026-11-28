
import os
import json
import time
import unicodedata
import requests

from datetime import datetime, timedelta, timezone
from pathlib import Path

# ============================================================
# API-FOOTBALL V3 - 25 LIG BULTEN TOPLAYICI
# Ucretsiz plan icin kota kontrollu
# ============================================================

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

if not API_KEY:
    raise SystemExit("HATA: API_FOOTBALL_KEY bulunamadi.")

OUTPUT_FILE = Path("bulten.json")
ARCHIVE_FILE = Path("bulten_history.json")

SEASON = 2026
HISTORY_DAYS = 90
FUTURE_DAYS = 14

MAX_API_CALLS = 90
REQUEST_DELAY = 6.5

api_call_count = 0
last_request_time = 0.0

TODAY = datetime.now(timezone.utc).date()
DATE_FROM = (TODAY - timedelta(days=HISTORY_DAYS)).isoformat()
DATE_TO = (TODAY + timedelta(days=FUTURE_DAYS)).isoformat()

SESSION = requests.Session()
SESSION.headers.update({
    "x-apisports-key": API_KEY
})

# ============================================================
# 25 LIG
# API isimleri farkli olabilecegi icin alternatifler kullanilir.
# ============================================================

LEAGUES = [
    {"country": "Turkey", "label_country": "Türkiye", "label": "Süper Lig",
     "names": ["Süper Lig", "Super Lig"]},

    {"country": "Turkey", "label_country": "Türkiye", "label": "1. Lig",
     "names": ["1. Lig", "TFF 1. Lig"]},

    {"country": "England", "label_country": "İngiltere", "label": "Premier League",
     "names": ["Premier League"]},

    {"country": "England", "label_country": "İngiltere", "label": "Championship",
     "names": ["Championship"]},

    {"country": "Italy", "label_country": "İtalya", "label": "Serie A",
     "names": ["Serie A"]},

    {"country": "Italy", "label_country": "İtalya", "label": "Serie B",
     "names": ["Serie B"]},

    {"country": "Spain", "label_country": "İspanya", "label": "LaLiga",
     "names": ["La Liga", "LaLiga"]},

    {"country": "Spain", "label_country": "İspanya", "label": "LaLiga 2",
     "names": ["La Liga 2", "LaLiga 2", "Segunda División"]},

    {"country": "Belgium", "label_country": "Belçika", "label": "Pro Lig",
     "names": ["Jupiler Pro League", "Belgian Pro League", "First Division A"]},

    {"country": "Portugal", "label_country": "Portekiz", "label": "Liga Portugal",
     "names": ["Primeira Liga", "Liga Portugal"]},

    {"country": "Netherlands", "label_country": "Hollanda", "label": "Eredivisie",
     "names": ["Eredivisie"]},

    {"country": "France", "label_country": "Fransa", "label": "Ligue 1",
     "names": ["Ligue 1"]},

    {"country": "France", "label_country": "Fransa", "label": "Ligue 2",
     "names": ["Ligue 2"]},

    {"country": "Germany", "label_country": "Almanya", "label": "Bundesliga",
     "names": ["Bundesliga"]},

    {"country": "Germany", "label_country": "Almanya", "label": "2. Bundesliga",
     "names": ["2. Bundesliga", "2 Bundesliga"]},

    {"country": "Greece", "label_country": "Yunanistan", "label": "Super League",
     "names": ["Super League 1", "Super League"]},

    {"country": "Russia", "label_country": "Rusya", "label": "Premier League",
     "names": ["Premier League", "Premier Liga"]},

    {"country": "Saudi Arabia", "label_country": "Suudi Arabistan",
     "label": "Saudi Pro League",
     "names": ["Pro League", "Saudi Pro League"]},

    {"country": "Scotland", "label_country": "İskoçya", "label": "Premiership",
     "names": ["Premiership", "Scottish Premiership"]},

    {"country": "Austria", "label_country": "Avusturya", "label": "Bundesliga",
     "names": ["Bundesliga"]},

    {"country": "Azerbaijan", "label_country": "Azerbaycan",
     "label": "Premier League",
     "names": ["Premier League"]},

    {"country": "USA", "label_country": "ABD", "label": "MLS",
     "names": ["Major League Soccer", "MLS"]},

    {"country": "World", "label_country": "Avrupa",
     "label": "Şampiyonlar Ligi",
     "names": ["UEFA Champions League"]},

    {"country": "World", "label_country": "Avrupa",
     "label": "Avrupa Ligi",
     "names": ["UEFA Europa League"]},

    {"country": "World", "label_country": "Avrupa",
     "label": "Konferans Ligi",
     "names": ["UEFA Conference League"]}
]


# ============================================================
# YARDIMCILAR
# ============================================================

def log(message):
    print(message, flush=True)


def normalize(value):
    value = str(value or "").casefold().strip()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(value.split())


def api_get(endpoint, params=None):
    global api_call_count, last_request_time

    if api_call_count >= MAX_API_CALLS:
        raise RuntimeError(
            f"Güvenlik kotası doldu: {MAX_API_CALLS} istek."
        )

    elapsed = time.time() - last_request_time

    if last_request_time and elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    response = SESSION.get(
        BASE_URL + endpoint,
        params=params or {},
        timeout=35
    )

    last_request_time = time.time()
    api_call_count += 1

    if response.status_code in (401, 403):
        raise RuntimeError(
            f"API anahtarı/yetki hatası: HTTP {response.status_code}"
        )

    if response.status_code == 429:
        raise RuntimeError("API hız veya günlük kota sınırına ulaşıldı.")

    response.raise_for_status()

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            "API hata döndürdü: " + str(data["errors"])
        )

    return data


def parse_score(home, away):
    if home is None or away is None:
        return ""
    return f"{home}-{away}"


def is_finished(status):
    return str(status or "").upper() in {
        "FT", "AET", "PEN"
    }


# ============================================================
# LIG LISTESINI BUL
# ============================================================

def find_league(all_leagues, config):
    expected_names = {
        normalize(x) for x in config["names"]
    }
    expected_country = normalize(config["country"])

    candidates = []

    for item in all_leagues:
        league = item.get("league") or {}
        country = item.get("country") or {}

        if normalize(country.get("name")) != expected_country:
            continue

        name = normalize(league.get("name"))

        if name in expected_names:
            candidates.append(item)

    if not candidates:
        return None

    # Önce 2026 sezonu bulunan kaydı seç.
    for item in candidates:
        seasons = item.get("seasons") or []
        for season in seasons:
            if int(season.get("year") or 0) == SEASON:
                return item

    return candidates[0]


log("=" * 60)
log("API-FOOTBALL BULTEN TOPLAMA BASLADI")
log(f"Sezon: {SEASON}")
log(f"Tarih araligi: {DATE_FROM} - {DATE_TO}")
log("=" * 60)

# Tek istekle 2026 sezonunun lig listesini al.
league_payload = api_get(
    "/leagues",
    {"season": SEASON}
)

all_leagues = league_payload.get("response") or []

if not all_leagues:
    raise SystemExit("API lig listesi bos dondu.")


# ============================================================
# HER LIG ICIN MACLARI CEK
# ============================================================

all_matches = []
league_errors = []
successful_leagues = 0

for index, config in enumerate(LEAGUES, start=1):
    label = config["label"]

    log(f"\n[{index}/{len(LEAGUES)}] {config['label_country']} - {label}")

    league_item = find_league(all_leagues, config)

    # Sezon listesinde bulunamazsa arama ile tekrar dene.
    if not league_item:
        search_name = config["names"][0]

        try:
            search_payload = api_get(
                "/leagues",
                {
                    "search": search_name,
                    "country": config["country"]
                }
            )

            league_item = find_league(
                search_payload.get("response") or [],
                config
            )

        except Exception as error:
            league_errors.append(f"{label}: {error}")
            log(f"  LIG ARAMA HATASI: {error}")
            continue

    if not league_item:
        league_errors.append(f"{label}: API lig listesinde bulunamadi.")
        log("  LIG BULUNAMADI - atlandi.")
        continue

    league_info = league_item.get("league") or {}
    league_id = league_info.get("id")

    seasons = league_item.get("seasons") or []
    season_years = [
        int(s.get("year"))
        for s in seasons
        if s.get("year") is not None
    ]

    selected_season = (
        SEASON if SEASON in season_years
        else max(season_years) if season_years
        else SEASON
    )

    try:
        payload = api_get(
            "/fixtures",
            {
                "league": league_id,
                "season": selected_season,
                "from": DATE_FROM,
                "to": DATE_TO,
                "timezone": "Europe/Istanbul"
            }
        )

        fixtures = payload.get("response") or []

        for raw in fixtures:
            fixture = raw.get("fixture") or {}
            teams = raw.get("teams") or {}
            goals = raw.get("goals") or {}
            score = raw.get("score") or {}
            halftime = score.get("halftime") or {}

            home = teams.get("home") or {}
            away = teams.get("away") or {}

            home_name = home.get("name") or ""
            away_name = away.get("name") or ""

            if not home_name or not away_name:
                continue

            status = fixture.get("status") or {}
            referee = fixture.get("referee") or ""

            item = {
                "id": str(fixture.get("id")),
                "country": config["label_country"],
                "league": label,
                "leagueCode": str(league_id),
                "date": fixture.get("date") or "",
                "home": home_name,
                "away": away_name,
                "referee": referee,
                "status": status.get("long") or "",
                "statusCode": status.get("short") or "",
                "finalScore": parse_score(
                    goals.get("home"),
                    goals.get("away")
                ),
                "halfTimeScore": parse_score(
                    halftime.get("home"),
                    halftime.get("away")
                )
            }

            all_matches.append(item)

        successful_leagues += 1
        log(f"  API ligi: {league_info.get('name')}")
        log(f"  Mac sayisi: {len(fixtures)}")

    except Exception as error:
        league_errors.append(f"{label}: {error}")
        log(f"  MAC CEKME HATASI: {error}")


# ============================================================
# VERI KONTROLU
# ============================================================

if successful_leagues == 0:
    raise SystemExit(
        "HICBIR LIG CEKILEMEDI. Mevcut bulten korunuyor."
    )

# Aynı maçın iki kez yazılmasını engelle.
unique = {}

for match in all_matches:
    if match.get("id") and match["id"] != "None":
        unique[match["id"]] = match

all_matches = list(unique.values())

all_matches.sort(
    key=lambda x: x.get("date") or ""
)


# ============================================================
# TAKIM VE HAKEM GECMISLERINI OLUSTUR
# ============================================================

team_history = {}
referee_history = {}

output = []

for match in all_matches:
    home_name = match["home"]
    away_name = match["away"]

    home_key = normalize(home_name)
    away_key = normalize(away_name)
    referee_key = normalize(match.get("referee"))

    # Analiz motoru en yeniden eskiye sıralı geçmiş bekliyor.
    match["homeMatches"] = list(
        reversed(team_history.get(home_key, []))
    )
    match["awayMatches"] = list(
        reversed(team_history.get(away_key, []))
    )
    match["refMatches"] = list(
        reversed(referee_history.get(referee_key, []))
    ) if referee_key else []

    output.append(match)

    if not is_finished(match.get("statusCode")):
        continue

    final_score = match.get("finalScore")
    half_score = match.get("halfTimeScore")

    if not final_score or not half_score:
        continue

    try:
        fh, fa = [int(x) for x in final_score.split("-")]
        hh, ha = [int(x) for x in half_score.split("-")]
    except (ValueError, TypeError):
        continue

    common = {
        "date": match.get("date"),
        "home": home_name,
        "away": away_name,
        "halfTimeScore": half_score,
        "finalScore": final_score,
        "league": match.get("league"),
        "referee": match.get("referee")
    }

    home_item = {
        **common,
        "teamGoalsHT": hh,
        "opponentGoalsHT": ha,
        "teamGoalsFT": fh,
        "opponentGoalsFT": fa
    }

    away_item = {
        **common,
        "teamGoalsHT": ha,
        "opponentGoalsHT": hh,
        "teamGoalsFT": fa,
        "opponentGoalsFT": fh
    }

    team_history.setdefault(home_key, []).append(home_item)
    team_history.setdefault(away_key, []).append(away_item)

    if referee_key:
        referee_history.setdefault(
            referee_key, []
        ).append(common)


# ============================================================
# DOSYALARI KAYDET
# ============================================================

with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

archive_data = {
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "source": "API-FOOTBALL",
    "season": SEASON,
    "matches": output
}

with ARCHIVE_FILE.open("w", encoding="utf-8") as file:
    json.dump(archive_data, file, ensure_ascii=False, indent=2)


# ============================================================
# RAPOR
# ============================================================

finished_count = sum(
    1 for m in output if is_finished(m.get("statusCode"))
)

upcoming_count = sum(
    1 for m in output
    if not is_finished(m.get("statusCode"))
)

ht_count = sum(1 for m in output if m.get("halfTimeScore"))
ft_count = sum(1 for m in output if m.get("finalScore"))

log("\n" + "=" * 60)
log("BULTEN TOPLAMA RAPORU")
log(f"Basarili lig: {successful_leagues}/{len(LEAGUES)}")
log(f"Toplam mac: {len(output)}")
log(f"Tamamlanan mac: {finished_count}")
log(f"Gelecek/canli mac: {upcoming_count}")
log(f"IY skoru bulunan: {ht_count}")
log(f"MS skoru bulunan: {ft_count}")
log(f"API istegi: {api_call_count}/{MAX_API_CALLS}")

if league_errors:
    log("\nUYARILAR:")
    for error in league_errors:
        log(" - " + error)

log("bulten.json kaydedildi.")
log("bulten_history.json kaydedildi.")
log("=" * 60)
