import os
import json
import time
import unicodedata
import requests

from datetime import datetime, timedelta, timezone, date
from pathlib import Path

# ============================================================
# API-FOOTBALL V3 - 25 LIG BULTEN TOPLAYICI
# API_FOOTBALL_KEY GitHub Actions Secret olarak tanimlanmalidir.
# Lig sezonu /leagues cevabindaki seasons listesinden secilir.
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
WINDOW_START = date.fromisoformat(DATE_FROM)
WINDOW_END = date.fromisoformat(DATE_TO)

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
        raise RuntimeError(
            f"API istek guvenlik siniri doldu ({MAX_API_CALLS})."
        )

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


def parse_api_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def choose_season(seasons):
    """Tarih araligiyla ortusen guncel sezonu tercih et."""
    valid = []
    for season in seasons or []:
        year = season.get("year")
        if not year:
            continue
        start = parse_api_date(season.get("start"))
        end = parse_api_date(season.get("end"))
        current = bool(season.get("current"))
        overlaps = (
            (start is None or start <= WINDOW_END) and
            (end is None or end >= WINDOW_START)
        )
        if overlaps:
            valid.append((current, year, start, end))

    if not valid:
        # API bazen tarihleri bos dondurebilir; current isaretli sezonu kullan.
        for season in seasons or []:
            if season.get("year") and season.get("current"):
                return int(season["year"])
        return None

    valid.sort(
        key=lambda item: (
            item[0],
            item[2] or date.min,
            int(item[1])
        ),
        reverse=True
    )
    return int(valid[0][1])


def find_league(items, config):
    expected_names = {normalize(x) for x in config["names"]}
    expected_country = normalize(config["country"])
    candidates = []

    for item in items:
        league = item.get("league") or {}
        country = item.get("country") or {}
        if normalize(country.get("name")) != expected_country:
            continue
        if normalize(league.get("name")) not in expected_names:
            continue

        seasons = item.get("seasons") or []
        season_year = choose_season(seasons)
        if season_year is not None:
            candidates.append((bool(next(
                (s.get("current") for s in seasons
                 if int(s.get("year") or 0) == season_year),
                False
            )), item, season_year))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def parse_score(home, away):
    if home is None or away is None:
        return ""
    return f"{home}-{away}"


def is_finished(status):
    return str(status or "").upper() in {"FT", "AET", "PEN"}


log("=" * 68)
log("API-FOOTBALL 25 LIG BULTEN TOPLAMA BASLADI")
log("Lig aramasi: search parametresi")
log("Fikstur aramasi: lig ID + o lige ait mevcut sezon + tarih araligi")
log(f"Tarih araligi: {DATE_FROM} - {DATE_TO}")
log("=" * 68)

# 1) Lig ID'si ve ilgili sezon yilini bul.
league_map = {}
league_errors = []

for index, config in enumerate(LEAGUES, start=1):
    log(f"\n[{index}/{len(LEAGUES)}] {config['label_country']} - {config['label']}")
    found = None
    found_season = None

    for search_name in config["names"]:
        try:
            payload = api_get("/leagues", {"search": search_name})
            found, found_season = find_league(
                payload.get("response") or [], config
            )
            if found:
                break
        except Exception as error:
            league_errors.append(f"{config['label']} lig aramasi: {error}")
            log(f"  ARAMA HATASI: {error}")
            break

    if not found:
        league_errors.append(
            f"{config['label']}: uygun lig veya tarih araligina uyan sezon bulunamadi."
        )
        log("  LIG/SEZON BULUNAMADI - atlandi.")
        continue

    league_info = found.get("league") or {}
    league_id = league_info.get("id")
    if league_id is None:
        league_errors.append(f"{config['label']}: lig ID bulunamadi.")
        log("  LIG ID YOK - atlandi.")
        continue

    league_map[int(league_id)] = {
        "config": config,
        "season": int(found_season),
        "api_name": league_info.get("name") or config["label"]
    }
    log(
        f"  BULUNDU: {league_info.get('name')} "
        f"(ID: {league_id}, sezon: {found_season})"
    )

if not league_map:
    raise SystemExit("HICBIR LIG BULUNAMADI. Mevcut bulten korunuyor.")

# 2) Her ligi kendi API sezon yiliyla sorgula.
all_matches = []
league_counts = {}

for index, (league_id, league_data) in enumerate(league_map.items(), start=1):
    config = league_data["config"]
    season_year = league_data["season"]
    log(
        f"\nFikstur [{index}/{len(league_map)}]: {config['label']} "
        f"(sezon {season_year})"
    )

    page = 1
    league_fixture_count = 0

    while True:
        try:
            params = {
                "league": league_id,
                "season": season_year,
                "from": DATE_FROM,
                "to": DATE_TO,
                "timezone": "Europe/Istanbul",
                "page": page
            }
            payload = api_get("/fixtures", params)
        except Exception as error:
            league_errors.append(
                f"{config['label']} ({season_year}) fikstur hatasi: {error}"
            )
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
            all_matches.append({
                "id": str(fixture.get("id")),
                "country": config["label_country"],
                "league": config["label"],
                "leagueCode": str(league_id),
                "season": season_year,
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
            })
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

# 3) Tekrar eden maclari temizle ve tarihe gore sirala.
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

# 4) Her mac icin yalnizca daha once oynanmis maclari history alanina ekle.
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

# 5) Veri geldiyse JSON dosyalarini kaydet.
with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

archive_data = {
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "source": "API-FOOTBALL",
    "dateFrom": DATE_FROM,
    "dateTo": DATE_TO,
    "leagueCount": len(league_map),
    "fixtureLeagueCount": len(league_counts),
    "matches": output
}
with ARCHIVE_FILE.open("w", encoding="utf-8") as file:
    json.dump(archive_data, file, ensure_ascii=False, indent=2)

finished_count = sum(1 for m in output if is_finished(m.get("statusCode")))
upcoming_count = sum(1 for m in output if not is_finished(m.get("statusCode")))

log("\n" + "=" * 68)
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
log("=" * 68)
