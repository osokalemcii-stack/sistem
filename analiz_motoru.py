
import json
import re
from pathlib import Path
from datetime import datetime, timezone

SOURCE = Path("bulten.json")
OUTPUT = Path("analiz.json")

MIN_STREAK = 4
SPECIAL_STREAK = 6


def score(value):
    if not value:
        return None
    found = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value))
    return (int(found.group(1)), int(found.group(2))) if found else None


def parity(value):
    if value is None:
        return None
    return "ÇİFT" if value % 2 == 0 else "TEK"


def ordered(history):
    # Veri toplayıcı geçmişleri en yeni maçtan eskiye sıralıyor.
    return list(reversed(history or []))


def total_values(history, field):
    values = []
    for item in ordered(history):
        s = score(item.get(field))
        if s:
            values.append(parity(sum(s)))
    return values


def own_values(history, field):
    return [
        parity(item.get(field))
        for item in ordered(history)
        if item.get(field) is not None
    ]


def side_values(history, field, side):
    values = []
    for item in ordered(history):
        s = score(item.get(field))
        if s:
            values.append(parity(s[0] if side == "home" else s[1]))
    return values


def streak(values):
    if not values:
        return None

    last = values[-1]
    length = 0

    for value in reversed(values):
        if value != last:
            break
        length += 1

    if length < MIN_STREAK:
        return None

    return {
        "type": "SERİ",
        "length": length,
        "last": last,
        "expected": "ÇİFT" if last == "TEK" else "TEK",
        "sequence": values[-min(length, 10):]
    }


def alternating(values):
    if len(values) < 4:
        return None

    last = values[-4:]

    if all(last[i] != last[i - 1] for i in range(1, 4)):
        return {
            "type": "ÖRÜNTÜ",
            "pattern": "DÖNÜŞÜMLÜ",
            "sequence": last,
            "expected": "ÇİFT" if last[-1] == "TEK" else "TEK"
        }

    return None


def paired(values):
    if len(values) < 4:
        return None

    last = values[-4:]

    if (
        last[0] == last[1]
        and last[2] == last[3]
        and last[0] != last[2]
    ):
        return {
            "type": "ÖRÜNTÜ",
            "pattern": "İKİLİ BLOK",
            "sequence": last,
            "expected": last[0]
        }

    return None


def add_streak(signals, label, values):
    result = streak(values)

    if result:
        signals.append({
            "rule": label,
            "kind": "SERİ",
            "length": result["length"],
            "sequence": result["sequence"],
            "last": result["last"],
            "expected": result["expected"],
            "explanation": (
                f"Son {result['length']} maçta {result['last']} "
                f"görüldü. Seri kırılma senaryosu {result['expected']}."
            )
        })


def add_pattern(signals, label, values, pair=False):
    result = paired(values) if pair else alternating(values)

    if result:
        signals.append({
            "rule": label,
            "kind": "ÖRÜNTÜ",
            "length": 4,
            "pattern": result["pattern"],
            "sequence": result["sequence"],
            "expected": result["expected"],
            "explanation": (
                "Son dört kayıt: "
                + " - ".join(result["sequence"])
            )
        })


def add_analysis(signals, label, values, pair=False):
    add_streak(signals, label, values)
    add_pattern(signals, label, values)

    if pair:
        add_pattern(signals, label + " İKİLİ BLOK", values, pair=True)


def special_run(history, kind):
    run = 0

    for item in ordered(history)[::-1]:
        s = score(item.get("finalScore"))

        if not s:
            break

        home, away = s
        total = home + away

        if kind == "KG YOK":
            matched = home == 0 or away == 0
        elif kind == "MS 0":
            matched = home == away
        elif kind == "2-3 GOL YOK":
            matched = total not in (2, 3)
        else:
            matched = False

        if not matched:
            break

        run += 1

    return run


def is_finished(match):
    code = str(match.get("statusCode") or "").lower()
    status = str(match.get("status") or "").lower()

    finished_codes = {
        "final", "finished", "after_extra_time",
        "after_penalties", "ft", "aet", "pen", "completed"
    }

    return code in finished_codes or status in {
        "ft", "aet", "pen", "finished", "final"
    }


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None


def main():
    if not SOURCE.exists():
        raise SystemExit("HATA: bulten.json bulunamadi.")

    with SOURCE.open("r", encoding="utf-8") as f:
        matches = json.load(f)

    if not isinstance(matches, list):
        raise SystemExit("HATA: bulten.json liste formatinda degil.")

    now = datetime.now(timezone.utc)
    results = []
    upcoming_count = 0

    for match in matches:

        if is_finished(match):
            continue

        match_date = parse_date(match.get("date"))

        if match_date:
            if match_date.tzinfo is None:
                match_date = match_date.replace(tzinfo=timezone.utc)
            if match_date < now:
                continue

        upcoming_count += 1

        home_history = match.get("homeMatches") or []
        away_history = match.get("awayMatches") or []
        ref_history = match.get("refMatches") or []

        signals = []

        # A1 - İlk yarı toplam gol örüntüsü
        for side, history in (
            ("EV", home_history),
            ("DEP", away_history)
        ):
            values = total_values(history, "halfTimeScore")
            add_pattern(signals, f"İY TOPLAM ÖRÜNTÜ ({side})", values)

        # A2 - Takımın kendi ilk yarı golü
        for side, history in (
            ("EV", home_history),
            ("DEP", away_history)
        ):
            values = own_values(history, "teamGoalsHT")
            add_analysis(signals, f"İY TAKIM GOLÜ ({side})", values)

        # A3 - İlk yarı toplam gol serisi
        for side, history in (
            ("EV", home_history),
            ("DEP", away_history)
        ):
            values = total_values(history, "halfTimeScore")
            add_streak(signals, f"İY TOPLAM SERİ ({side})", values)

        # B1 - Maç sonu toplam gol örüntüsü
        for side, history in (
            ("EV", home_history),
            ("DEP", away_history)
        ):
            values = total_values(history, "finalScore")
            add_pattern(signals, f"MS TOPLAM ÖRÜNTÜ ({side})", values)

        # B2 - Takımın kendi maç sonu golü
        for side, history in (
            ("EV", home_history),
            ("DEP", away_history)
        ):
            values = own_values(history, "teamGoalsFT")
            add_analysis(signals, f"MS TAKIM GOLÜ ({side})", values)

        # C1 - Hakem ilk yarı toplam gol
        ref_ht = total_values(ref_history, "halfTimeScore")
        add_analysis(signals, "HAKEM İY TOPLAM", ref_ht)

        # C2 - Hakem maç sonu toplam gol
        ref_ft = total_values(ref_history, "finalScore")
        add_analysis(signals, "HAKEM MS TOPLAM", ref_ft)

        # C3 - Hakemin yönettiği maçlarda ev sahibinin İY golü
        add_analysis(
            signals,
            "HAKEM EV SAHİBİ İY GOL",
            side_values(ref_history, "halfTimeScore", "home")
        )

        # C4 - Hakemin yönettiği maçlarda ev sahibinin MS golü
        add_analysis(
            signals,
            "HAKEM EV SAHİBİ MS GOL",
            side_values(ref_history, "finalScore", "home")
        )

        # C5 - Hakemin yönettiği maçlarda deplasmanın İY golü
        add_analysis(
            signals,
            "HAKEM DEPLASMAN İY GOL",
            side_values(ref_history, "halfTimeScore", "away")
        )

        # C6 - Hakemin yönettiği maçlarda deplasmanın MS golü
        add_analysis(
            signals,
            "HAKEM DEPLASMAN MS GOL",
            side_values(ref_history, "finalScore", "away")
        )

        # C7 - Hakemin İY toplam golünde TEK-TEK-ÇİFT-ÇİFT örüntüsü
        add_pattern(
            signals,
            "HAKEM İY İKİLİ BLOK",
            ref_ht,
            pair=True
        )

        # Her pazar kendi geçmişinden değerlendirilir.
        expectations = {
            "İY": "DEĞİŞKEN",
            "İY EV": "DEĞİŞKEN",
            "İY DEP": "DEĞİŞKEN",
            "MS": "DEĞİŞKEN",
            "MS EV": "DEĞİŞKEN",
            "MS DEP": "DEĞİŞKEN"
        }

        ht_candidates = []
        ft_candidates = []

        for history in (home_history, away_history):
            h = streak(total_values(history, "halfTimeScore"))
            f = streak(total_values(history, "finalScore"))

            if h:
                ht_candidates.append(h["expected"])
            if f:
                ft_candidates.append(f["expected"])

        if ht_candidates and len(set(ht_candidates)) == 1:
            expectations["İY"] = ht_candidates[0]

        if ft_candidates and len(set(ft_candidates)) == 1:
            expectations["MS"] = ft_candidates[0]

        for key, history, field in (
            ("İY EV", home_history, "teamGoalsHT"),
            ("İY DEP", away_history, "teamGoalsHT"),
            ("MS EV", home_history, "teamGoalsFT"),
            ("MS DEP", away_history, "teamGoalsFT")
        ):
            result = streak(own_values(history, field))
            if result:
                expectations[key] = result["expected"]

        # 6+ özel seriler
        special = []

        for side, history in (
            ("EV", home_history),
            ("DEP", away_history)
        ):
            for kind in ("KG YOK", "MS 0", "2-3 GOL YOK"):
                length = special_run(history, kind)

                if length >= SPECIAL_STREAK:
                    special.append({
                        "side": side,
                        "name": kind,
                        "length": length
                    })

        if not signals and not special:
            continue

        results.append({
            "id": match.get("id"),
            "date": match.get("date"),
            "country": match.get("country"),
            "league": match.get("league"),
            "home": match.get("home"),
            "away": match.get("away"),
            "referee": match.get("referee"),
            "halfTimeScore": match.get("halfTimeScore"),
            "finalScore": match.get("finalScore"),
            "expectations": expectations,
            "signals": signals,
            "specialSeries": special,
            "signalCount": len(signals) + len(special),
            "dataQuality": {
                "homeHistory": len(home_history),
                "awayHistory": len(away_history),
                "refereeHistory": len(ref_history)
            }
        })

    results.sort(
        key=lambda x: (x["signalCount"], x.get("date") or ""),
        reverse=True
    )

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "SportStatsAPI",
        "method": {
            "minimumStreak": MIN_STREAK,
            "minimumSpecialStreak": SPECIAL_STREAK,
            "note": (
                "Seri kirilma beklentisi kesin tahmin degildir. "
                "Yeterli veri yoksa DEĞİŞKEN kullanilir."
            )
        },
        "summary": {
            "sourceMatches": len(matches),
            "upcomingMatches": upcoming_count,
            "matchesWithSignals": len(results)
        },
        "matches": results
    }

    temp = OUTPUT.with_suffix(".tmp")

    with temp.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    temp.replace(OUTPUT)

    print("=" * 55)
    print("ANALİZ MOTORU TAMAMLANDI")
    print(f"Kaynak maç: {len(matches)}")
    print(f"Gelecek maç: {upcoming_count}")
    print(f"Sinyal bulunan maç: {len(results)}")
    print("analiz.json kaydedildi.")
    print("=" * 55)


if __name__ == "__main__":
    main()
