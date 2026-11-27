
import os
import re
import json
import time
import requests

from datetime import datetime, timedelta, timezone
from pathlib import Path

# =====================================================
# AYARLAR
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
ARCHIVE_FILE = Path("bulten_history.json")

TODAY = datetime.now(timezone.utc).date()

BOOTSTRAP_DAYS = 90
INCREMENTAL_DAYS = 7
FUTURE_DAYS = 14

HISTORY_LIMIT = 12
PAGE_LIMIT = 100

# 5 istek/dakika sınırına uygun.
REQUEST_DELAY = 12.5

# Günlük kotayı tek çalışmada tüketmemek için güvenlik sınırı.
MAX_API_CALLS = 45

last_request_time = 0
api_call_count = 0


# =====================================================
# LİGLER
# =====================================================

LEAGUES = [
    {"code":"l7c","country":"Türkiye","league":"Süper Lig","api_name":"Turkey: Super Lig"},
    {"code":"l79","country":"Türkiye","league":"1. Lig","api_name":"Turkey: 1. Lig"},
    {"code":"l30","country":"İngiltere","league":"Premier League","api_name":"England: Premier League"},
    {"code":"l31","country":"İngiltere","league":"Championship","api_name":"England: Championship"},
    {"code":"l4b","country":"İtalya","league":"Serie A","api_name":"Italy: Serie A"},
    {"code":"l4a","country":"İtalya","league":"Serie B","api_name":"Italy: Serie B"},
    {"code":"l6t","country":"İspanya","league":"LaLiga","api_name":"Spain: LaLiga"},
    {"code":"l6s","country":"İspanya","league":"LaLiga 2","api_name":"Spain: LaLiga2"},
    {"code":"l19","country":"Belçika","league":"Jupiler Pro League","api_name":"Belgium: Jupiler Pro League"},
    {"code":"l5u","country":"Portekiz","league":"Liga Portugal","api_name":"Portugal: Liga Portugal"},
    {"code":"l58","country":"Hollanda","league":"Eredivisie","api_name":"Netherlands: Eredivisie"},
    {"code":"l3d","country":"Fransa","league":"Ligue 1","api_name":"France: Ligue 1"},
    {"code":"l3a","country":"Fransa","league":"Ligue 2","api_name":"France: Ligue 2"},
    {"code":"l3k","country":"Almanya","league":"Bundesliga","api_name":"Germany: Bundesliga"},
    {"code":"l3g","country":"Almanya","league":"2. Bundesliga","api_name":"Germany: 2. Bundesliga"},
    {"code":"l3n","country":"Yunanistan","league":"Super League","api_name":"Greece: Super League"},
    {"code":"l7x","country":"Rusya","league":"Premier League","api_name":"Russia: Premier League"},
    {"code":"l66","country":"Suudi Arabistan","league":"Saudi Professional League","api_name":"Saudi Arabia: Saudi Professional League"},
    {"code":"l67","country":"İskoçya","league":"Premiership","api_name":"Scotland: Premiership"},
    {"code":"l12","country":"Avusturya","league":"Bundesliga","api_name":"Austria: Bundesliga"},
    {"code":"l13","country":"Azerbaycan","league":"Premier League","api_name":"Azerbaijan: Premier League"},
    {"code":"l7k","country":"ABD","league":"MLS","api_name":"USA: Mls"},
    {"code":"l3","country":"Avrupa","league":"Şampiyonlar Ligi","api_name":"Europe: Champions League - League Phase"},
    {"code":"l4","country":"Avrupa","league":"Avrupa Ligi","api_name":"Europe: Europa League - League Phase"},
    {"code":"laz","country":"Avrupa","league":"Konferans Ligi","api_name":"Europe: Conference League - League Phase"}
]


# =====================================================
# YARDIMCI FONKSİYONLAR
# =====================================================

def log(message):
    print(message, flush=True)


def normalize_name(value):
    return re.sub(
        r"\s+", " ",
        str(value or "").strip().casefold()
    )


def team_name(team):
    if not isinstance(team, dict):
        return ""
    return team.get("display_name") or team.get("name") or ""


def referee_name(match):
    value = match.get("referee") or ""

    if isinstance(value, dict):
        return value.get("name") or ""

    return str(value).strip()


def parse_score(value):
    if not value:
        return None

    found = re.search(
        r"(\d+)\s*[-:]\s*(\d+)",
        str(value)
    )

    if not found:
        return None

    return {
        "home": int(found.group(1)),
        "away": int(found.group(2))
    }


def get_full_score(match):
    result = parse_score(match.get("full_time_score"))

    if result:
        return result

    home = match.get("home_team") or {}
    away = match.get("away_team") or {}

    h = home.get("score")
    a = away.get("score")

    if h is not None and a is not None:
        return {
            "home": int(h),
            "away": int(a)
        }

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
            "after_extra_time", "after_penalties",
            "ft", "aet", "pen", "completed"
        }
        or status in {
            "FT", "AET", "PEN", "FINISHED", "FINAL"
        }
    )


def match_date(match):
    return (
        match.get("start_at")
        or match.get("start_date")
        or match.get("date")
        or ""
    )


def match_id(match, league, home, away, date):
    value = (
        match.get("match_id")
        or match.get("id")
        or match.get("code")
    )

    if value:
        return str(value)

    return (
        f"{league['code']}-"
        f"{date}-{normalize_name(home)}-{normalize_name(away)}"
    )


def safe_json_load(path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as error:
        log(f"UYARI: {path} okunamadi: {error}")
        return default


def save_json(path, data):
    temp = path.with_suffix(".tmp")

    with temp.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    temp.replace(path)


# =====================================================
# API İSTEĞİ
# =====================================================

class DailyQuotaReached(Exception):
    pass


def api_get(path, params):
    global last_request_time
    global api_call_count

    if api_call_count >= MAX_API_CALLS:
        raise DailyQuotaReached(
            f"Guvenlik siniri: {MAX_API_CALLS} API istegi."
        )

    elapsed = time.time() - last_request_time

    if last_request_time and elapsed < REQUEST_DELAY:
        wait = REQUEST_DELAY - elapsed
        log(f"API hiz siniri: {wait:.1f} saniye bekleniyor.")
        time.sleep(wait)

    response = SESSION.get(
        BASE_URL + path,
        params=params,
        timeout=(10, 35)
    )

    last_request_time = time.time()
    api_call_count += 1

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "")

        try:
            wait = int(retry_after)
        except (ValueError, TypeError):
            wait = 0

        if wait > 120:
            raise DailyQuotaReached(
                f"API kota siniri. Retry-After: {wait} saniye. "
                "Uzun bekleme yapilmadi."
            )

        raise DailyQuotaReached(
            "API 429 yaniti verdi. Kota veya hiz siniri."
        )

    response.raise_for_status()

    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(
            f"API basarisiz yanit verdi: {payload}"
        )

    return payload


# =====================================================
# ARŞİVİ YÜKLE
# =====================================================

archive_data = safe_json_load(ARCHIVE_FILE, {})

if isinstance(archive_data, dict):
    archived_matches = archive_data.get("matches", [])
else:
    archived_matches = []

# Eski bulten.json dosyasından da kayıt kurtarmayı dene.
old_bulletin = safe_json_load(OUTPUT_FILE, [])

if not archived_matches and isinstance(old_bulletin, list):
    archived_matches = old_bulletin

archive = {}

for item in archived_matches:
    if not isinstance(item, dict):
        continue

    item_id = item.get("id")

    if item_id:
        archive[str(item_id)] = item


# =====================================================
# İLK YÜKLEME / GÜNLÜK GÜNCELLEME
# =====================================================

bootstrap = len(archive) == 0

if bootstrap:
    date_from = (
        TODAY - timedelta(days=BOOTSTRAP_DAYS)
    ).isoformat()

    mode = "ILK VERI YUKLEMESI"

else:
    date_from = (
        TODAY - timedelta(days=INCREMENTAL_DAYS)
    ).isoformat()

    mode = "ARTIMSAL GUNCELLEME"


date_to = (
    TODAY + timedelta(days=FUTURE_DAYS)
).isoformat()

log("=" * 60)
log("GERCEK FUTBOL VERISI TOPLANIYOR")
log(f"Mod: {mode}")
log(f"Tarih araligi: {date_from} - {date_to}")
log(f"Arsivdeki mevcut mac: {len(archive)}")
log("=" * 60)


# =====================================================
# LİGLERDEN VERİ AL
# =====================================================

league_errors = []
successful_leagues = 0
new_count = 0
quota_error = None

for index, league in enumerate(LEAGUES, start=1):

    log(
        f"\n[{index}/{len(LEAGUES)}] "
        f"{league['country']} - {league['league']}"
    )

    offset = 0
    league_added = 0

    try:
        while True:

            params = {
                "league_name": league["api_name"],
                "date_from": date_from,
                "date_to": date_to,
                "limit": PAGE_LIMIT,
                "offset": offset,
                "order": "asc"
            }

            payload = api_get(
                "/soccer/matches",
                params
            )

            page = payload.get("data") or []

            for raw in page:

                api_code = str(raw.get("league_code") or "")

                if api_code and api_code != league["code"]:
                    continue

                home = team_name(raw.get("home_team"))
                away = team_name(raw.get("away_team"))

                if not home or not away:
                    continue

                date = match_date(raw)

                item_id = match_id(
                    raw, league, home, away, date
                )

                full = get_full_score(raw)
                half = get_half_score(raw)

                item = {
                    "id": item_id,
                    "country": league["country"],
                    "league": league["league"],
                    "leagueCode": league["code"],
                    "date": date,
                    "home": home,
                    "away": away,
                    "referee": referee_name(raw),
                    "status": raw.get("status") or "",
                    "statusCode": get_status_code(raw),
                    "finalScore": (
                        f"{full['home']}-{full['away']}"
                        if full else ""
                    ),
                    "halfTimeScore": (
                        f"{half['home']}-{half['away']}"
                        if half else ""
                    )
                }

                if item_id not in archive:
                    new_count += 1

                archive[item_id] = item
                league_added += 1

            log(
                f"  Sayfa {offset // PAGE_LIMIT + 1}: "
                f"{len(page)} mac"
            )

            meta = payload.get("meta") or {}
            total = meta.get("total")

            if not page:
                break

            if total is not None:
                if offset + len(page) >= int(total):
                    break
            elif len(page) < PAGE_LIMIT:
                break

            offset += PAGE_LIMIT

            # Her lig için en fazla 3 sayfa.
            if offset >= PAGE_LIMIT * 3:
                log("  Sayfa guvenlik sinirina ulasildi.")
                break

    except DailyQuotaReached as error:
        quota_error = str(error)
        log(f"API KOTA DURDURMASI: {quota_error}")
        break

    except Exception as error:
        league_errors.append(
            f"{league['league']}: {error}"
        )
        log(f"  LIG HATASI: {error}")
        continue

    successful_leagues += 1

    log(f"  Bu ligden eklenen/guncellenen: {league_added}")


# =====================================================
# KOTA VE HATA KONTROLÜ
# =====================================================

if quota_error:
    raise SystemExit(
        "\nVERI TOPLAMA DURDURULDU.\n"
        f"Neden: {quota_error}\n"
        "Mevcut arsiv ve bulten dosyalari korunuyor."
    )

if successful_leagues == 0:
    raise SystemExit(
        "HATA: Hicbir ligden veri alinamadi. "
        "Mevcut dosyalar korunuyor."
    )


# =====================================================
# ARŞİVİ TEMİZLE
# =====================================================

# 180 günden eski kayıtları arşivden çıkar.
archive_cutoff = TODAY - timedelta(days=180)

clean_archive = {}

for item_id, item in archive.items():

    raw_date = item.get("date") or ""

    try:
        parsed = datetime.fromisoformat(
            raw_date.replace("Z", "+00:00")
        ).date()
    except Exception:
        continue

    if parsed >= archive_cutoff:
        clean_archive[item_id] = item

archive = clean_archive


# =====================================================
# TARİHE GÖRE SIRALA
# =====================================================

all_matches = list(archive.values())

all_matches.sort(
    key=lambda x: x.get("date") or ""
)


# =====================================================
# TAKIM VE HAKEM GEÇMİŞLERİ
# =====================================================

team_history = {}
referee_history = {}

def history_item(match, team_key=None):

    ht = parse_score(match.get("halfTimeScore"))
    ft = parse_score(match.get("finalScore"))

    if not ht or not ft:
        return None

    home_key = normalize_name(match.get("home"))
    away_key = normalize_name(match.get("away"))

    if team_key == home_key:
        for_ht, against_ht = ht["home"], ht["away"]
        for_ft, against_ft = ft["home"], ft["away"]

    elif team_key == away_key:
        for_ht, against_ht = ht["away"], ht["home"]
        for_ft, against_ft = ft["away"], ft["home"]

    else:
        for_ht = against_ht = None
        for_ft = against_ft = None

    return {
        "date": match.get("date"),
        "home": match.get("home"),
        "away": match.get("away"),
        "halfTimeScore": (
            f"{ht['home']}-{ht['away']}"
        ),
        "finalScore": (
            f"{ft['home']}-{ft['away']}"
        ),
        "teamGoalsHT": for_ht,
        "opponentGoalsHT": against_ht,
        "teamGoalsFT": for_ft,
        "opponentGoalsFT": against_ft,
        "league": match.get("league"),
        "referee": match.get("referee")
    }


for match in all_matches:

    home_key = normalize_name(match.get("home"))
    away_key = normalize_name(match.get("away"))
    ref_key = normalize_name(match.get("referee"))

    match["homeMatches"] = (
        team_history.get(home_key, [])[-HISTORY_LIMIT:][::-1]
    )

    match["awayMatches"] = (
        team_history.get(away_key, [])[-HISTORY_LIMIT:][::-1]
    )

    match["refMatches"] = (
        referee_history.get(ref_key, [])[-HISTORY_LIMIT:][::-1]
    )

    if not is_finished(match):
        continue

    if not match.get("finalScore") or not match.get("halfTimeScore"):
        continue

    home_item = history_item(match, home_key)
    away_item = history_item(match, away_key)
    ref_item = history_item(match)

    if home_item:
        team_history.setdefault(home_key, []).append(home_item)

    if away_item:
        team_history.setdefault(away_key, []).append(away_item)

    if ref_key and ref_item:
        referee_history.setdefault(ref_key, []).append(ref_item)


# =====================================================
# BÜLTEN VE ARŞİV DOSYALARI
# =====================================================

# Geçmiş maçlar ve gelecek fikstürler birlikte tutulur.
output = []

for match in all_matches:

    output.append({
        "id": match.get("id"),
        "country": match.get("country"),
        "league": match.get("league"),
        "date": match.get("date"),
        "home": match.get("home"),
        "away": match.get("away"),
        "referee": match.get("referee"),
        "status": match.get("status"),
        "statusCode": match.get("statusCode"),
        "finalScore": match.get("finalScore"),
        "halfTimeScore": match.get("halfTimeScore"),
        "homeMatches": match.get("homeMatches", []),
        "awayMatches": match.get("awayMatches", []),
        "refMatches": match.get("refMatches", [])
    })


if not output:
    raise SystemExit(
        "HATA: Bulten bos. Onceki dosyalar korunuyor."
    )


# Önce geçici dosyalara yaz, sonra güvenli değiştir.
save_json(
    ARCHIVE_FILE,
    {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "matches": all_matches
    }
)

save_json(OUTPUT_FILE, output)


# =====================================================
# RAPOR
# =====================================================

finished_count = sum(
    1 for m in all_matches if is_finished(m)
)

ht_count = sum(
    1 for m in all_matches if m.get("halfTimeScore")
)

ft_count = sum(
    1 for m in all_matches if m.get("finalScore")
)

ref_count = sum(
    1 for m in all_matches if m.get("referee")
)

team_history_count = sum(
    1 for m in output
    if m["homeMatches"] or m["awayMatches"]
)

ref_history_count = sum(
    1 for m in output if m["refMatches"]
)

league_count = len(
    set(m.get("league") for m in all_matches)
)

log("\n" + "=" * 60)
log("BULTEN TOPLAMA TAMAMLANDI")
log(f"Mod: {mode}")
log(f"API istegi: {api_call_count}")
log(f"Basarili lig: {successful_leagues}/25")
log(f"Toplam arsiv maci: {len(all_matches)}")
log(f"Yeni mac kaydi: {new_count}")
log(f"Eslesen lig: {league_count}/25")
log(f"Tamamlanan mac: {finished_count}")
log(f"IY skoru bulunan: {ht_count}")
log(f"MS skoru bulunan: {ft_count}")
log(f"Hakem bilgisi bulunan: {ref_count}")
log(f"Takim gecmisi bulunan: {team_history_count}")
log(f"Hakem gecmisi bulunan: {ref_history_count}")

if league_errors:
    log("\nHATA ALINAN LIGLER:")
    for error in league_errors:
        log(" - " + error)

log("\nbulten.json ve bulten_history.json kaydedildi.")
log("=" * 60)
