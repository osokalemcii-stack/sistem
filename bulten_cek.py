import os
import json
import requests

BASE = "https://api.sportstatsapi.com/api/v1"
KEY = os.getenv("SPORTSTATS_API_KEY")

if not KEY:
    raise SystemExit("SPORTSTATS_API_KEY bulunamadi")

s = requests.Session()
s.headers.update({"Authorization": f"Bearer {KEY}"})

countries = [
    "turkey", "türkiye", "england", "italy", "spain",
    "belgium", "portugal", "netherlands", "holland",
    "france", "germany", "greece", "russia",
    "saudi arabia", "scotland", "austria",
    "azerbaijan", "usa", "united states", "europe"
]

targets = [
    "super lig", "super league", "1. lig", "premier league",
    "championship", "serie a", "serie b", "la liga",
    "segunda division", "pro league", "first division a",
    "primeira liga", "liga portugal", "eredivisie",
    "ligue 1", "ligue 2", "bundesliga", "2. liga",
    "2. bundesliga", "super league 1", "premiership",
    "major league soccer", "mls", "champions league",
    "europa league", "conference league"
]

r = s.get(BASE + "/soccer/leagues", timeout=40)
r.raise_for_status()
payload = r.json()

if not payload.get("success"):
    raise SystemExit("API lig listesi basarisiz: " + str(payload))

leagues = payload.get("data", [])
print("TOPLAM LIG:", len(leagues))
print("HEDEF LIG ADAYLARI")
print("=" * 60)

count = 0

for league in leagues:
    name = str(league.get("name") or "")
    official = str(league.get("official_name") or "")
    combined = (name + " " + official).lower()

    country_ok = any(
        name.lower().startswith(country + ":")
        for country in countries
    )

    league_ok = any(word in combined for word in targets)

    if country_ok and league_ok:
        print(json.dumps(league, ensure_ascii=False))
        count += 1

print("=" * 60)
print("BULUNAN ADAY SAYISI:", count)
print("TEST TAMAMLANDI - BULTEN DOSYALARINA DOKUNULMADI")