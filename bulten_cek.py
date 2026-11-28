import os
import json
import time
import unicodedata
import requests

from datetime import datetime, timedelta, timezone
from pathlib import Path

# ============================================================
# API-FOOTBALL V3 - 25 LIG BULTEN TOPLAYICI
# GitHub Actions Secret: API_FOOTBALL_KEY
# Season parametresi kullanilmaz; fiksturler tarih araligiyla cekilir.
# ============================================================

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

if not API_KEY:
    raise SystemExit("HATA: API_FOOTBALL_KEY bulunamadi.")

OUTPUT_FILE = Path("bulten.json")
ARCHIVE_FILE = Path("bulten_history.json")

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
SESSION.headers.update({"x-apisports-key": API_KEY})

LEAGUES = [
    {"country": "Turkey", "label_country": "TÃ¼rkiye", "label": "SÃ¼per Lig",
     "names": ["SÃ¼per Lig", "Super Lig"]},
    {"country": "Turkey", "label_country": "TÃ¼rkiye", "label": "1. Lig",
     "names": ["1. Lig", "TFF 1. Lig"]},
    {"country": "England", "label_country": "Ä°ngiltere", "label": "Premier League",
     "names": ["Premier League"]},
    {"country": "England", "label_country": "Ä°ngiltere", "label": "Championship",
     "names": ["Championship"]},
    {"country": "Italy", "label_country": "Ä°talya", "label": "Serie A",
     "names": ["Serie A"]},
    {"country": "Italy", "label_country": "Ä°talya", "label": "Serie B",
     "names": ["Serie B"]},
    {"country": "Spain", "label_country": "Ä°spanya", "label": "LaLiga",
     "names": ["La Liga", "LaLiga"]},
    {"country": "Spain", "label_country": "Ä°spanya", "label": "LaLiga 2",
     "names": ["La Liga 2", "LaLiga 2", "Segunda DivisiÃ³n"]},
    {"country": "Belgium", "label_country": "BelÃ§ika", "label": "Pro Lig",
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
     "label": "Saudi Pro League", "names": ["Pro League", "Saudi Pro League"]},
    {"country": "Scotland", "label_country": "Ä°skoÃ§ya", "label": "Premiership",
     "names": ["Premiership", "Scottish Premiership"]},
    {"country": "Austria", "label_country": "Avusturya", "label": "Bundesliga",
     "names": ["Bundesliga"]},
    {"country": "Azerbaijan", "label_country": "Azerbaycan",
     "label": "Premier League", "names": ["Premier League"]},
    {"country": "USA", "label_country": "ABD", "label": "MLS",
     "names": ["Major League Soccer", "MLS"]},
    {"country": "World", "label_country": "Avrupa",
     "label": "Åampiyonlar Ligi", "names": ["UEFA Champions League"]},
    {"country": "World", "label_country": "Avrupa",
     "label": "Avrupa Ligi", "names": ["UEFA Europa League"]},
    {"country": "World", "label_country": "Avrupa",
     "label": "Konferans Ligi", "names": ["UEFA Conference League"]}
]


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
        raise RuntimeError(f"API istek guvenlik siniri doldu: {MAX_API_CALLS}")

    elapsed = time.time() - last_request_time
    if last_request_time and elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    response = SESSION.get(
        BASE_URL + endpoint,
        params=params or {},
        timeout=45
    )
    last_request_time = time.time()
    api_call_count += 1

    if response.status_code in (401, 403):
        raise RuntimeError(
            f"API anahtari/yetki hatasi: HTTP {response.status_code}"
        )
    if response.status_code == 429:
        raise RuntimeError("API hiz veya gunluk kota sinirina ulasildi.")

    response.raise_for_status()
    data = response.json()

    if data.get("errors"):
        raise RuntimeError("API hata dondurdu: " + str(data["errors"]))

    return data


def find_league(items, config):
    expected_names = {normalize(x) for x in config["names"]}
    expected_country = normalize(config["country"])

    for item in items:
        league = item.get("league") or {}
        country = item.get("country") or {}

        # country parametresi API istegine eklenmez.
        # Ulke ve lig adi eslestirmesi burada, Python tarafinda yapilir.
        if normalize(country.get("name")) != expected_country:
            continue
        if normalize(league.get("name")) in expected_names:
            return item
    return None


def parse_score(home, away):
    if home is None or away is None:
        return ""
    return f"{home}-{away}"


def is_finished(status):
    return str(status or "").upper() in {"FT", "AET", "PEN"}


log("=" * 64)
log("API-FOOTBALL 25 LIG BULTEN TOPLAMA BASLADI")
log("Lig aramasinda yalnizca search parametresi kullanilacak.")
log("Fiksturlerde season parametresi kullanilmayacak.")
log(f"Tarih araligi: {DATE_FROM} - {DATE_TO}")
log("=" * 64)

# 1) Lig ID'lerini bul. HATA DUZELTMESI:
# /leagues isteginde search ve country birlikte gonderilmiyor.
league_map = {}
league_errors = []

for index, config in enumerate(LEAGUES, start=1):
    log(f"\n[{index}/{len(LEAGUES)}] {config['label_country']} - {config['label']}")
    found = None

    for search_name in config["names"]:
        try:
            payload = api_get("/leagues", {"search": search_name})
            found = find_league(payload.get("response") or [], config)
            if found:
                break
        except Exception as error:
            league_errors.append(f"{config['label']} lig aramasi: {error}")
            log(f"  ARAMA HATASI: {error}")
            break

    if not found:
        league_errors.append(f"{config['label']}: lig bulunamadi.")
        log("  LIG BULUNAMADI - atlandi.")
        continue

    info = found.get("league") or {}
    league_id = info.get("id")
    if league_id is None:
        league_errors.append(f"{config['label']}: lig ID bulunamadi.")
        log("  LIG ID YOK - atlandi.")
        continue

    league_map[int(league_id)] = config
    log(f"  BULUNDU: {info.get('name')} (ID: {league_id})")

if not league_map:
    raise SystemExit("HICBIR LIG BULUNAMADI. Mevcut bulten korunuyor.")

# 2) Her ligin fiksturunu ayri cek.
# Boylece tum dunyanin maclarini tek istekte cekip sayfalama sorunu yasamayiz.
all_matches = []
league_counts = {}

for index, (league_id, config) in enumerate(league_map.items(), start=1):
    log(f"\nFikstur [{index}/{len(league_map)}]: {config['label']}")
    page = 1
    league_fixture_count = 0

    while True:
        try:
            params = {
                "league": league_id,
                "from": DATE_FROM,
                "to": DATE_TO,
                "timezone": "Europe/Istanbul",
                "page": page
            }
            payload = api_get("/fixtures", params)
        except Exception as error:
            league_errors.append(f"{config['label']} fikstur hatasi: {error}")
            log(f"  FIKSTUR HATASI: {error}")
            break

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
            item = {
                "id": str(fixture.get("id")),
                "country": config["label_country"],
                "league": config["label"],
                "leagueCode": str(league_id),
                "date": fixture.get("date") or "",
                "home": home_name,
                "away": away_name,
                "referee": fixture.get("referee") or "",
                "status": status.get("long") or "",
                "statusCode": status.get("short") or "",
                "finalScore": parse_score(goals.get("home"), goals.get("away")),
                "halfTimeScore": parse_score(
                    halftime.get("home"), halftime.get("away")
                )
            }
            all_matches.append(item)
            league_fixture_count += 1

        paging = payload.get("paging") or {}
        total_pages = int(paging.get("total") or 1)
        log(f"  Sayfa {page}/{total_pages}: {len(fixtures)} mac")

        if page >= total_pages or not fixtures:
            break
        page += 1

    if league_fixture_count:
        league_counts[config["label"]] = league_fixture_count
    log(f"  Toplam: {league_fixture_count} mac")

# 3) Tekrar eden maclari temizle.
unique = {}
for match in all_matches:
    match_id = match.get("id")
    if match_id and match_id != "None":
        unique[match_id] = match

all_matches = list(unique.values())
all_matches.sort(key=lambda x: x.get("date") or "")

if not all_matches:
    raise SystemExit(
        "Hedef liglerde tarih araliginda mac bulunamadi. "
        "Mevcut JSON dosyalari korunuyor."
    )

# 4) Takim ve hakem gecmislerini olustur.
team_history = {}
referee_history = {}
output = []

for match in all_matches:
    home_name = match["home"]
    away_name = match["away"]
    home_key = normalize(home_name)
    away_key = normalize(away_name)
    referee_key = normalize(match.get("referee"))

    match["homeMatches"] = list(reversed(team_history.get(home_key, [])))
    match["awayMatches"] = list(reversed(team_history.get(away_key, [])))
    match["refMatches"] = (
        list(reversed(referee_history.get(referee_key, []))
             if referee_key else [])
    )
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
        referee_history.setdefault(referee_key, []).append(common)

# 5) JSON dosyalarini kaydet.
with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

archive_data = {
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "source": "API-FOOTBALL",
    "dateFrom": DATE_FROM,
    "dateTo": DATE_TO,
    "leagueCount": len(league_map),
    "matches": output
}
with ARCHIVE_FILE.open("w", encoding="utf-8") as file:
    json.dump(archive_data, file, ensure_ascii=False, indent=2)

finished_count = sum(1 for m in output if is_finished(m.get("statusCode")))
upcoming_count = sum(1 for m in output if not is_finished(m.get("statusCode")))

log("\n" + "=" * 64)
log("BULTEN TOPLAMA RAPORU")
log(f"Bulunan lig: {len(league_map)}/{len(LEAGUES)}")
log(f"Mac bulunan lig: {len(league_counts)}")
for name, count in sorted(league_counts.items()):
    log(f"  - {name}: {count} mac")
log(f"Toplam mac: {len(output)}")
log(f"Tamamlanan mac: {finished_count}")
log(f"Gelecek/canli mac: {upcoming_count}")
log(f"API istegi: {api_call_count}/{MAX_API_CALLS}")
if league_errors:
    log("\nUYARILAR:")
    for error in league_errors:
        log(" - " + error)
log("bulten.json ve bulten_history.json kaydedildi.")
log("=" * 64)
