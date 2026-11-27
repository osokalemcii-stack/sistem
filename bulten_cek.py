
import json
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BASE = "https://api.sportstatsapi.com/api/v1"
KEY = os.getenv("SPORTSTATS_API_KEY")
TZ = ZoneInfo("Europe/Istanbul")
HISTORY_FILE = "bulten_history.json"
OUTPUT_FILE = "bulten.json"

if not KEY:
    raise SystemExit("SPORTSTATS_API_KEY bulunamadi.")

S = requests.Session()
S.headers.update({"Authorization": f"Bearer {KEY}"})

# Uygulamadaki 25 lig. Ülke ve lig adı birlikte eşleştirilir.
TARGETS = [
    ("Türkiye", ["turkey", "türkiye"], ["super lig", "super league"]),
    ("Türkiye: 1.Lig", ["turkey", "türkiye"], ["1. lig", "1. league", "tff 1"]),
    ("İngiltere: Premier Lig", ["england"], ["premier league"]),
    ("İngiltere: Championship", ["england"], ["championship"]),
    ("İtalya: Serie A", ["italy"], ["serie a"]),
    ("İtalya: Serie B", ["italy"], ["serie b"]),
    ("İspanya: La Liga", ["spain"], ["la liga", "primera division"]),
    ("İspanya: La Liga 2", ["spain"], ["segunda division", "la liga 2"]),
    ("Belçika: Pro Lig", ["belgium"], ["pro league", "first division a"]),
    ("Portekiz: Liga Portugal", ["portugal"], ["primeira liga", "liga portugal"]),
    ("Hollanda: Eredivisie", ["netherlands", "holland"], ["eredivisie"]),
    ("Fransa: Ligue 1", ["france"], ["ligue 1"]),
    ("Fransa: Ligue 2", ["france"], ["ligue 2"]),
    ("Almanya: Bundesliga", ["germany"], ["bundesliga"]),
    ("Almanya: Bundesliga 2", ["germany"], ["2. bundesliga", "bundesliga 2"]),
    ("Yunanistan: Super Lig", ["greece"], ["super league", "super league 1"]),
    ("Rusya: Premier Lig", ["russia"], ["premier league"]),
    ("Suudi Arabistan: Pro Lig", ["saudi arabia"], ["pro league"]),
    ("İskoçya: Premier Ship", ["scotland"], ["premiership"]),
    ("Avusturya: Bundesliga", ["austria"], ["bundesliga"]),
    ("Azerbaycan: Premier Lig", ["azerbaijan"], ["premier league"]),
    ("ABD: MLS", ["usa", "united states"], ["major league soccer", "mls"]),
    ("AVRUPA: Uefa Şampiyonlar Ligi", ["europe"], ["champions league"]),
    ("AVRUPA: Uefa Avrupa Ligi", ["europe"], ["europa league"]),
    ("AVRUPA: Uefa Konferans Ligi", ["europe"], ["conference league"]),
]


def norm(value):
    value = str(value or "").lower()
    value = value.replace("ı", "i").replace("ü", "u")
    value = value.replace("ş", "s").replace("ğ", "g")
    value = value.replace("ö", "o").replace("ç", "c")
    return re.sub(r"\s+", " ", value).strip()


def get(path, params=None):
    r = S.get(BASE + path, params=params or {}, timeout=40)

    if r.status_code == 429:
        raise RuntimeError("SportStatsAPI gunluk istek siniri doldu.")

    r.raise_for_status()
    payload = r.json()

    if not payload.get("success"):
        raise RuntimeError(str(payload.get("error") or payload))

    return payload.get("data", []), payload.get("meta", {})


def league_target(league):
    name = norm(league.get("name"))
    official = norm(league.get("official_name"))
    combined = name + " " + official

    for label, countries, aliases in TARGETS:
        country_ok = any(country in combined for country in countries)
        league_ok = any(alias in combined for alias in aliases)

        # Almanya 2. Bundesliga, Bundesliga ile karışmasın.
        if label == "Almanya: Bundesliga":
            if "2. bundesliga" in combined:
                continue

        if label == "AVRUPA: Uefa Konferans Ligi":
            if "champions" in combined or "europa" in combined:
                continue

        if country_ok and league_ok:
            return label

    return None


def parse_score(value):
    if not value:
        return None
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value))
    return (int(m.group(1)), int(m.group(2))) if m else None


def score_token(match):
    half = parse_score(match.get("half_time_score"))
    full = parse_score(match.get("full_time_score"))

    if half is None or full is None:
        return None

    return f"{half[0]}-{half[1]} ({full[0]}-{full[1]})"


def is_finished(match):
    status = norm(match.get("status_code") or match.get("status"))
    return status in {
        "ft", "aet", "pen", "finished", "final",
        "after extra time", "after penalties"
    }


def read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, data):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp, path)


def main():
    print("Lig listesi aliniyor...")
    leagues, _ = get("/soccer/leagues")

    league_map = {}
    for league in leagues:
        label = league_target(league)
        if label:
            league_map[str(league.get("id"))] = label

    print("Eslestirilen lig sayisi:", len(set(league_map.values())))

    now = datetime.now(TZ)
    history = read_json(HISTORY_FILE, {})
    matches_all = []

    for day_offset in range(3):
        day = (now.date() + timedelta(days=day_offset)).isoformat()
        print("Maclar aliniyor:", day)

        offset = 0
        while True:
            rows, meta = get("/soccer/matches", {
                "date": day,
                "limit": 100,
                "offset": offset,
                "order": "asc"
            })

            matches_all.extend(rows)

            if len(rows) < 100 or not meta.get("has_more"):
                break

            offset += len(rows)

    # Tekrar gelen maçları ID üzerinden birleştir.
    unique = {}
    for match in matches_all:
        mid = match.get("match_id")
        if mid is not None:
            unique[str(mid)] = match

    bulletin = []

    for match in unique.values():
        league_id = str(match.get("league_id", ""))
        label = league_map.get(league_id)

        # Bilinmeyen ligleri kesinlikle yanlış etiketleme.
        if not label:
            continue

        home = match.get("home_team") or {}
        away = match.get("away_team") or {}
        mid = match.get("match_id")

        if not home.get("name") or not away.get("name"):
            continue

        finished = is_finished(match)
        token = score_token(match)

        # Bitmiş maçları takım geçmişine ekle.
        if finished and token:
            for team in (home, away):
                tid = team.get("id")
                if tid is None:
                    continue

                key = "team_" + str(tid)
                history.setdefault(key, [])

                entry = {
                    "match_id": str(mid),
                    "date": match.get("start_at") or match.get("start_date", ""),
                    "score": token
                }

                if not any(x.get("match_id") == str(mid) for x in history[key]):
                    history[key].append(entry)

                history[key].sort(key=lambda x: x.get("date", ""))
                history[key] = history[key][-5:]

        start_at = match.get("start_at")
        date_text = ""

        if start_at:
            try:
                dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                date_text = dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                date_text = str(start_at)
        else:
            date_text = str(match.get("start_date", ""))

        def team_history(team):
            tid = team.get("id")
            if tid is None:
                return []
            entries = history.get("team_" + str(tid), [])
            return [x["score"] for x in entries[-5:]]

        full = parse_score(match.get("full_time_score"))
        final_score = f"{full[0]}-{full[1]}" if finished and full else ""

        bulletin.append({
            "id": f"ssa-{mid}",
            "country": label.split(":")[0],
            "league": label,
            "date": date_text,
            "home": home["name"],
            "away": away["name"],
            "referee": match.get("referee") or "Bilinmiyor",
            "status": "finished" if finished else "upcoming",
            "finalScore": final_score,
            "homeMatches": team_history(home),
            "awayMatches": team_history(away),
            "refMatches": []
        })

    bulletin.sort(key=lambda x: x["date"])

    write_json(HISTORY_FILE, history)
    write_json(OUTPUT_FILE, bulletin)

    print("--------------------------------")
    print("API'den gelen mac:", len(unique))
    print("Bultene yazilan mac:", len(bulletin))
    print("Eslestirilen lig:", len(set(x["league"] for x in bulletin)))
    print("Bulten ve takim arsivi kaydedildi.")
    print("--------------------------------")


if __name__ == "__main__":
    main()
