import os
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE = "https://api.sportstatsapi.com/api/v1"
KEY = os.getenv("SPORTSTATS_API_KEY")
TZ = ZoneInfo("Europe/Istanbul")

if not KEY:
    raise SystemExit("HATA: SPORTSTATS_API_KEY bulunamadi.")

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {KEY}",
    "Accept": "application/json"
})


def inspect_endpoint(path, params=None):
    url = BASE + path
    print("\n" + "=" * 55)
    print("ISTEK:", path)
    print("PARAMETRE:", params or {})

    try:
        response = session.get(url, params=params or {}, timeout=40)
        print("HTTP DURUMU:", response.status_code)

        if response.status_code != 200:
            print("HATA CEVABI:", response.text[:1500])
            return None

        payload = response.json()
        print("UST SEVIYE ALANLARI:", list(payload.keys()))
        print("SUCCESS:", payload.get("success"))

        data = payload.get("data")
        print("DATA TIPI:", type(data).__name__)

        if isinstance(data, list):
            print("KAYIT SAYISI:", len(data))
            print("META:", json.dumps(
                payload.get("meta", {}),
                ensure_ascii=False
            ))

            if data:
                print("ILK KAYIT:")
                print(json.dumps(
                    data[0],
                    ensure_ascii=False,
                    indent=2
                )[:3500])

        elif isinstance(data, dict):
            print("DATA ALANLARI:", list(data.keys()))
            print(json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            )[:3500])
        else:
            print("DATA:", str(data)[:1500])

        return payload

    except Exception as error:
        print("ISTEK HATASI:", repr(error))
        return None


def main():
    print("SPORTSTATSAPI TANI TESTI")
    print("TARIH:", datetime.now(TZ).isoformat())

    # 1. Gerçek lig listesini incele
    result = inspect_endpoint("/soccer/leagues")

    if result:
        leagues = result.get("data", [])

        if isinstance(leagues, list):
            print("\nTOPLAM LIG:", len(leagues))
            print("\nHEDEF LIGLERLE ILGILI ADAYLAR:")

            keywords = [
                "super", "premier", "championship",
                "serie", "liga", "bundesliga",
                "eredivisie", "ligue", "champions",
                "europa", "conference", "mls",
                "turkey", "türkiye", "england",
                "germany", "spain", "italy"
            ]

            shown = 0

            for league in leagues:
                text = json.dumps(
                    league,
                    ensure_ascii=False
                ).lower()

                if any(word in text for word in keywords):
                    print(json.dumps(
                        league,
                        ensure_ascii=False
                    ))
                    shown += 1

                    if shown >= 100:
                        print("Ilk 100 aday gosterildi.")
                        break

    # 2. Bugün ve sonraki iki günün maçlarını incele
    today = datetime.now(TZ).date()

    for offset in range(3):
        day = (today + timedelta(days=offset)).isoformat()

        inspect_endpoint(
            "/soccer/matches",
            {
                "date": day,
                "limit": 5,
                "offset": 0
            }
        )

    # 3. Tarih filtresi olmadan örnek maç sorgusu
    inspect_endpoint(
        "/soccer/matches",
        {
            "limit": 5,
            "offset": 0
        }
    )

    print("\n" + "=" * 55)
    print("TANI TESTI TAMAMLANDI.")
    print("Mevcut bulten.json dosyasina dokunulmadi.")


if __name__ == "__main__":
    main()