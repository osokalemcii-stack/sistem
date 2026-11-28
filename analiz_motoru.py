
import json
import re
from pathlib import Path
from datetime import datetime, timezone

SOURCE = Path("bulten.json")
OUTPUT = Path("analiz.json")

MIN_STREAK = 4
PATTERN_LENGTH = 4
SPECIAL_STREAK = 6
MAX_SEQUENCE_DISPLAY = 10


# ============================================================
# TEMEL VERI ISLEMLERI
# ============================================================

def score(value):
    if not value:
        return None

    found = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value))

    if not found:
        return None

    return int(found.group(1)), int(found.group(2))


def parity(value):
    if value is None:
        return None

    return "ÇİFT" if value % 2 == 0 else "TEK"


def ordered(history):
    """
    Veri toplayici gecmisi en yeniden eskiye dogru kaydediyor.
    Analiz icin en eskiden en yeniye ceviriyoruz.
    """
    return list(reversed(history or []))


def total_values(history, field):
    values = []

    for item in ordered(history):
        result = score(item.get(field))

        if result:
            values.append(parity(sum(result)))

    return values


def own_values(history, field):
    values = []

    for item in ordered(history):
        value = item.get(field)

        if value is not None:
            values.append(parity(value))

    return values


def side_values(history, field, side):
    values = []

    for item in ordered(history):
        result = score(item.get(field))

        if not result:
            continue

        goals = result[0] if side == "home" else result[1]
        values.append(parity(goals))

    return values


def sequence_text(values):
    return " - ".join(values)


# ============================================================
# SERI VE ORUNTU MOTORU
# ============================================================

def streak(values):
    """
    Son maclardan geriye dogru ayni tek/cift sonucunun
    kac kez tekrarlandigini bulur.
    """

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
        "sequence": values[-min(length, MAX_SEQUENCE_DISPLAY):]
    }


def alternating(values):
    """
    Son dort kayitta TEK-CIFT-TEK-CIFT
    veya CIFT-TEK-CIFT-TEK arar.
    """

    if len(values) < PATTERN_LENGTH:
        return None

    last = values[-PATTERN_LENGTH:]

    alternating_result = all(
        last[i] != last[i - 1]
        for i in range(1, PATTERN_LENGTH)
    )

    if not alternating_result:
        return None

    return {
        "type": "ÖRÜNTÜ",
        "pattern": "DÖNÜŞÜMLÜ",
        "sequence": last,
        "expected": "ÇİFT" if last[-1] == "TEK" else "TEK"
    }


def paired(values):
    """
    Son dort kayitta TEK-TEK-CIFT-CIFT
    veya CIFT-CIFT-TEK-TEK arar.
    """

    if len(values) < PATTERN_LENGTH:
        return None

    last = values[-PATTERN_LENGTH:]

    valid = (
        last[0] == last[1]
        and last[2] == last[3]
        and last[0] != last[2]
    )

    if not valid:
        return None

    return {
        "type": "ÖRÜNTÜ",
        "pattern": "İKİLİ BLOK",
        "sequence": last,
        "expected": last[0]
    }


# ============================================================
# SINYAL OLUSTURMA
# ============================================================

def add_streak(signals, rule_id, label, values):

    result = streak(values)

    if not result:
        return

    signals.append({
        "ruleId": rule_id,
        "rule": label,
        "kind": "SERİ",
        "length": result["length"],
        "last": result["last"],
        "sequence": result["sequence"],
        "expected": result["expected"],
        "explanation": (
            f"Son {result['length']} maçta aralıksız "
            f"{result['last']} sonucu oluştu. "
            f"Serinin devamı değil, kırılma senaryosu "
            f"olarak {result['expected']} gösteriliyor."
        )
    })


def add_pattern(signals, rule_id, label, values, pair=False):

    result = paired(values) if pair else alternating(values)

    if not result:
        return

    signals.append({
        "ruleId": rule_id,
        "rule": label,
        "kind": "ÖRÜNTÜ",
        "length": PATTERN_LENGTH,
        "pattern": result["pattern"],
        "sequence": result["sequence"],
        "expected": result["expected"],
        "explanation": (
            f"Son dört kayıt: {sequence_text(result['sequence'])}. "
            f"Belirlenen {result['pattern'].lower()} örüntüsü bulundu."
        )
    })


def add_analysis(signals, rule_id, label, values):

    add_streak(
        signals,
        rule_id,
        label,
        values
    )

    add_pattern(
        signals,
        rule_id,
        label,
        values
    )


# ============================================================
# 6+ OZEL SERILER
# ============================================================

def special_run(history, kind):
    """
    En son oynanan mactan geriye dogru kontrol eder.
    Skoru bulunmayan mac seriyi keser.
    """

    run = 0

    for item in reversed(ordered(history)):

        result = score(item.get("finalScore"))

        if not result:
            break

        home, away = result
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


def collect_special_series(home_history, away_history):

    special = []

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):

        for kind in (
            "KG YOK",
            "MS 0",
            "2-3 GOL YOK"
        ):

            length = special_run(history, kind)

            if length >= SPECIAL_STREAK:

                special.append({
                    "side": side,
                    "name": kind,
                    "length": length,
                    "explanation": (
                        f"{side} takımının geçmişindeki son "
                        f"{length} maçta {kind} koşulu gerçekleşti."
                    )
                })

    return special


# ============================================================
# MAC DURUMU VE TARIH
# ============================================================

def is_finished(match):

    code = str(match.get("statusCode") or "").strip().lower()
    status = str(match.get("status") or "").strip().lower()

    finished_values = {
        "final",
        "finished",
        "after_extra_time",
        "after_penalties",
        "ft",
        "aet",
        "pen",
        "completed"
    }

    return code in finished_values or status in finished_values


def parse_date(value):

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    except (ValueError, TypeError):
        return None


def is_upcoming(match, now):

    if is_finished(match):
        return False

    match_date = parse_date(match.get("date"))

    if not match_date:
        return True

    if match_date.tzinfo is None:
        match_date = match_date.replace(tzinfo=timezone.utc)

    return match_date >= now


# ============================================================
# BEKLENTI MOTORU
# ============================================================

def build_expectations(home_history, away_history):

    expectations = {
        "İY": "DEĞİŞKEN",
        "İY EV": "DEĞİŞKEN",
        "İY DEP": "DEĞİŞKEN",
        "MS": "DEĞİŞKEN",
        "MS EV": "DEĞİŞKEN",
        "MS DEP": "DEĞİŞKEN"
    }

    # İY toplam tek/cift beklentisi
    ht_candidates = []

    # MS toplam tek/cift beklentisi
    ft_candidates = []

    for history in (home_history, away_history):

        ht_result = streak(
            total_values(history, "halfTimeScore")
        )

        ft_result = streak(
            total_values(history, "finalScore")
        )

        if ht_result:
            ht_candidates.append(ht_result["expected"])

        if ft_result:
            ft_candidates.append(ft_result["expected"])

    if ht_candidates and len(set(ht_candidates)) == 1:
        expectations["İY"] = ht_candidates[0]

    if ft_candidates and len(set(ft_candidates)) == 1:
        expectations["MS"] = ft_candidates[0]

    # Takimlarin kendi gol beklentileri
    for key, history, field in (
        ("İY EV", home_history, "teamGoalsHT"),
        ("İY DEP", away_history, "teamGoalsHT"),
        ("MS EV", home_history, "teamGoalsFT"),
        ("MS DEP", away_history, "teamGoalsFT")
    ):

        result = streak(
            own_values(history, field)
        )

        if result:
            expectations[key] = result["expected"]

    return expectations


# ============================================================
# KURAL TARAMASI
# ============================================================

def analyze_match(match):

    home_history = match.get("homeMatches") or []
    away_history = match.get("awayMatches") or []
    ref_history = match.get("refMatches") or []

    signals = []

    # --------------------------------------------------------
    # A1 - IY TOPLAM GOL ORUNTUSU
    # --------------------------------------------------------

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):

        values = total_values(
            history,
            "halfTimeScore"
        )

        add_pattern(
            signals,
            f"A1_{side}",
            f"İY TOPLAM ÖRÜNTÜ ({side})",
            values
        )

    # --------------------------------------------------------
    # A2 - TAKIMIN KENDI IY GOLU
    # --------------------------------------------------------

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):

        values = own_values(
            history,
            "teamGoalsHT"
        )

        add_analysis(
            signals,
            f"A2_{side}",
            f"İY TAKIM GOLÜ ({side})",
            values
        )

    # --------------------------------------------------------
    # A3 - IY TOPLAM GOL SERISI
    # --------------------------------------------------------

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):

        values = total_values(
            history,
            "halfTimeScore"
        )

        add_streak(
            signals,
            f"A3_{side}",
            f"İY TOPLAM SERİ ({side})",
            values
        )

    # --------------------------------------------------------
    # B1 - MS TOPLAM GOL ORUNTUSU
    # --------------------------------------------------------

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):

        values = total_values(
            history,
            "finalScore"
        )

        add_pattern(
            signals,
            f"B1_{side}",
            f"MS TOPLAM ÖRÜNTÜ ({side})",
            values
        )

    # --------------------------------------------------------
    # B2 - TAKIMIN KENDI MS GOLU
    # --------------------------------------------------------

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):

        values = own_values(
            history,
            "teamGoalsFT"
        )

        add_analysis(
            signals,
            f"B2_{side}",
            f"MS TAKIM GOLÜ ({side})",
            values
        )

    # --------------------------------------------------------
    # C1 - HAKEM IY TOPLAM GOL
    # --------------------------------------------------------

    ref_ht = total_values(
        ref_history,
        "halfTimeScore"
    )

    add_analysis(
        signals,
        "C1",
        "HAKEM İY TOPLAM",
        ref_ht
    )

    # --------------------------------------------------------
    # C2 - HAKEM MS TOPLAM GOL
    # --------------------------------------------------------

    ref_ft = total_values(
        ref_history,
        "finalScore"
    )

    add_analysis(
        signals,
        "C2",
        "HAKEM MS TOPLAM",
        ref_ft
    )

    # --------------------------------------------------------
    # C3 - HAKEM EV SAHIBI IY GOL
    # --------------------------------------------------------

    add_analysis(
        signals,
        "C3",
        "HAKEM EV SAHİBİ İY GOL",
        side_values(
            ref_history,
            "halfTimeScore",
            "home"
        )
    )

    # --------------------------------------------------------
    # C4 - HAKEM EV SAHIBI MS GOL
    # --------------------------------------------------------

    add_analysis(
        signals,
        "C4",
        "HAKEM EV SAHİBİ MS GOL",
        side_values(
            ref_history,
            "finalScore",
            "home"
        )
    )

    # --------------------------------------------------------
    # C5 - HAKEM DEPLASMAN IY GOL
    # --------------------------------------------------------

    add_analysis(
        signals,
        "C5",
        "HAKEM DEPLASMAN İY GOL",
        side_values(
            ref_history,
            "halfTimeScore",
            "away"
        )
    )

    # --------------------------------------------------------
    # C6 - HAKEM DEPLASMAN MS GOL
    # --------------------------------------------------------

    add_analysis(
        signals,
        "C6",
        "HAKEM DEPLASMAN MS GOL",
        side_values(
            ref_history,
            "finalScore",
            "away"
        )
    )

    # --------------------------------------------------------
    # C7 - HAKEM IY IKILI BLOK ORUNTUSU
    # --------------------------------------------------------

    add_pattern(
        signals,
        "C7",
        "HAKEM İY İKİLİ BLOK",
        ref_ht,
        pair=True
    )

    # --------------------------------------------------------
    # BEKLENTILER VE OZEL SERILER
    # --------------------------------------------------------

    expectations = build_expectations(
        home_history,
        away_history
    )

    special = collect_special_series(
        home_history,
        away_history
    )

    return {
        "signals": signals,
        "expectations": expectations,
        "specialSeries": special,
        "dataQuality": {
            "homeHistory": len(home_history),
            "awayHistory": len(away_history),
            "refereeHistory": len(ref_history)
        }
    }


# ============================================================
# ANA PROGRAM
# ============================================================

def main():

    if not SOURCE.exists():
        raise SystemExit(
            "HATA: bulten.json bulunamadi."
        )

    try:
        with SOURCE.open("r", encoding="utf-8") as file:
            matches = json.load(file)

    except json.JSONDecodeError as error:
        raise SystemExit(
            f"HATA: bulten.json JSON formati gecersiz: {error}"
        )

    if not isinstance(matches, list):
        raise SystemExit(
            "HATA: bulten.json liste formatinda degil."
        )

    now = datetime.now(timezone.utc)

    results = []
    upcoming_count = 0
    finished_count = 0

    for match in matches:

        if not isinstance(match, dict):
            continue

        if is_finished(match):
            finished_count += 1
            continue

        if not is_upcoming(match, now):
            continue

        upcoming_count += 1

        analysis = analyze_match(match)

        signals = analysis["signals"]
        special = analysis["specialSeries"]

        # Sinyal veya ozel seri bulunmayan maci analiz listesine alma.
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
            "expectations": analysis["expectations"],
            "signals": signals,
            "specialSeries": special,
            "signalCount": len(signals) + len(special),
            "dataQuality": analysis["dataQuality"]
        })

    # Once daha fazla sinyal, sonra daha yakin mac.
    results.sort(
        key=lambda item: (
            item["signalCount"],
            item.get("date") or ""
        ),
        reverse=True
    )

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "SportStatsAPI",

        "method": {
            "minimumStreak": MIN_STREAK,
            "patternLength": PATTERN_LENGTH,
            "minimumSpecialStreak": SPECIAL_STREAK,
            "ruleCount": 12,
            "note": (
                "Seri kirilma beklentisi kesin tahmin degildir. "
                "Oruntu, gecmis kayitlarda gozlenen siralamadir. "
                "Yeterli veri yoksa beklenti DEĞİŞKEN kalir. "
                "Bu cikti garanti veya bahis tavsiyesi degildir."
            )
        },

        "summary": {
            "sourceMatches": len(matches),
            "finishedMatches": finished_count,
            "upcomingMatches": upcoming_count,
            "matchesWithSignals": len(results),
            "totalSignals": sum(
                item["signalCount"] for item in results
            )
        },

        "matches": results
    }

    temp = OUTPUT.with_suffix(".tmp")

    with temp.open("w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    temp.replace(OUTPUT)

    print("=" * 60)
    print("ANALIZ MOTORU TAMAMLANDI")
    print(f"Kaynak mac: {len(matches)}")
    print(f"Tamamlanan mac: {finished_count}")
    print(f"Gelecek mac: {upcoming_count}")
    print(f"Sinyal bulunan mac: {len(results)}")
    print(
        "Toplam sinyal: "
        f"{output['summary']['totalSignals']}"
    )
    print("analiz.json kaydedildi.")
    print("=" * 60)


if __name__ == "__main__":
    main()
