
import os
import requests

url = "https://api.sportstatsapi.com/api/v1/soccer/leagues"
headers = {
    "Authorization": f"Bearer {os.getenv('SPORTSTATS_API_KEY')}"
}

r = requests.get(url, headers=headers, timeout=40)
r.raise_for_status()

for league in r.json().get("data", []):
    name = str(league.get("name") or "")
    official = str(league.get("official_name") or "")
    divisions = league.get("divisions") or []

    combined = (name + " " + official + " " + " ".join(divisions)).lower()

    if any(x in combined for x in [
        "spain", "la liga", "segunda",
        "saudi arabia", "pro league",
        "usa: mls"
    ]):
        print({
            "code": league.get("code"),
            "name": name,
            "official_name": official,
            "divisions": divisions
        })

print("KONTROL TAMAMLANDI")
