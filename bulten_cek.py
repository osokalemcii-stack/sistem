
import os
import requests

BASE = "https://api.sportstatsapi.com/api/v1"
KEY = os.getenv("SPORTSTATS_API_KEY")

if not KEY:
    raise SystemExit("SPORTSTATS_API_KEY bulunamadi")

headers = {"Authorization": f"Bearer {KEY}"}

r = requests.get(BASE + "/soccer/leagues", headers=headers, timeout=40)
r.raise_for_status()
payload = r.json()

if not payload.get("success"):
    raise SystemExit(str(payload))

countries = [
    "turkey", "england", "italy", "spain", "belgium",
    "portugal", "netherlands", "holland", "france",
    "germany", "greece", "russia", "saudi arabia",
    "scotland", "austria", "azerbaijan", "usa",
    "united states", "europe"
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

print("=== HEDEF LIGLER VE KODLARI ===")

count = 0

for league in payload.get("data", []):
    name = str(league.get("name") or "")
    official = str(league.get("official_name") or "")
    divisions = league.get("divisions") or []

    combined = (name + " " + official + " " + " ".join(divisions)).lower()

    country_ok = any(
        name.lower().startswith(country + ":")
        for country in countries
    )

    league_ok = any(word in combined for word in targets)

    if country_ok and league_ok:
        print(f"KOD: {league.get('code')}")
        print(f"AD: {name}")
        print(f"RESMI AD: {official}")
        if divisions:
            print("ALT LIGLER: " + " / ".join(divisions))
        print("---")
        count += 1

print(f"TOPLAM ADAY: {count}")
print("TEST TAMAMLANDI - BULTEN DOSYALARINA DOKUNULMADI")
