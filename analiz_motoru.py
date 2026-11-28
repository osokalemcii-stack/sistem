
import json
import re
import math
from pathlib import Path
from datetime import datetime, timezone

SOURCE = Path("bulten.json")
OUTPUT = Path("analiz.json")

MIN_STREAK = 4
PATTERN_LENGTH = 4
SPECIAL_STREAK = 6
MAX_SEQUENCE_DISPLAY = 10
MAX_SCORE_PICKS = 6
HISTORY_LIMIT = 12


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
    if len(values) < PATTERN_LENGTH:
        return None

    last = values[-PATTERN_LENGTH:]

    valid = all(
        last[i] != last[i - 1]
        for i in range(1, PATTERN_LENGTH)
    )

    if not valid:
        return None

    return {
        "type": "ÖRÜNTÜ",
        "pattern": "DÖNÜŞÜMLÜ",
        "sequence": last,
        "expected": "ÇİFT" if last[-1] == "TEK" else "TEK"
    }


def paired(values):
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
            f"Kırılma senaryosu olarak "
            f"{result['expected']} gösteriliyor."
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
            f"{result['pattern'].lower()} örüntüsü bulundu."
        )
    })


def add_analysis(signals, rule_id, label, values):
    add_streak(signals, rule_id, label, values)
    add_pattern(signals, rule_id, label, values)


# ============================================================
# 6+ OZEL SERILER
# ============================================================

def special_run(history, kind):
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
        for kind in ("KG YOK", "MS 0", "2-3 GOL YOK"):
            length = special_run(history, kind)

            if length >= SPECIAL_STREAK:
                special.append({
                    "side": side,
                    "name": kind,
                    "length": length,
                    "explanation": (
                        f"{side} takımının son {length} maçında "
                        f"{kind} koşulu gerçekleşti."
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
        "final", "finished", "after_extra_time",
        "after_penalties", "ft", "aet", "pen", "completed"
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

def prediction_for_values(values):
    run = streak(values)

    if run:
        return {
            "expected": run["expected"],
            "kind": "SERİ",
            "length": run["length"],
            "last": run["last"],
            "sequence": run["sequence"],
            "weight": run["length"]
        }

    pattern = alternating(values)

    if pattern:
        return {
            "expected": pattern["expected"],
            "kind": "ÖRÜNTÜ",
            "length": PATTERN_LENGTH,
            "last": values[-1],
            "sequence": pattern["sequence"],
            "pattern": pattern["pattern"],
            "weight": PATTERN_LENGTH
        }

    pattern = paired(values)

    if pattern:
        return {
            "expected": pattern["expected"],
            "kind": "ÖRÜNTÜ",
            "length": PATTERN_LENGTH,
            "last": values[-1],
            "sequence": pattern["sequence"],
            "pattern": pattern["pattern"],
            "weight": PATTERN_LENGTH
        }

    return None


def build_expectations(home_history, away_history, ref_history):
    markets = {
        "İY": [
            ("EV TAKIM GEÇMİŞİ", total_values(home_history, "halfTimeScore")),
            ("DEP TAKIM GEÇMİŞİ", total_values(away_history, "halfTimeScore")),
            ("HAKEM GEÇMİŞİ", total_values(ref_history, "halfTimeScore"))
        ],
        "İY EV": [
            ("EVİN ATTIĞI İY GOL", own_values(home_history, "teamGoalsHT")),
            ("DEP'İN YEDİRDİĞİ İY GOL", own_values(away_history, "opponentGoalsHT")),
            ("HAKEM EV İY GOL", side_values(ref_history, "halfTimeScore", "home"))
        ],
        "İY DEP": [
            ("DEP'İN ATTIĞI İY GOL", own_values(away_history, "teamGoalsHT")),
            ("EVİN YEDİRDİĞİ İY GOL", own_values(home_history, "opponentGoalsHT")),
            ("HAKEM DEP İY GOL", side_values(ref_history, "halfTimeScore", "away"))
        ],
        "MS": [
            ("EV TAKIM GEÇMİŞİ", total_values(home_history, "finalScore")),
            ("DEP TAKIM GEÇMİŞİ", total_values(away_history, "finalScore")),
            ("HAKEM GEÇMİŞİ", total_values(ref_history, "finalScore"))
        ],
        "MS EV": [
            ("EVİN ATTIĞI MS GOL", own_values(home_history, "teamGoalsFT")),
            ("DEP'İN YEDİRDİĞİ MS GOL", own_values(away_history, "opponentGoalsFT")),
            ("HAKEM EV MS GOL", side_values(ref_history, "finalScore", "home"))
        ],
        "MS DEP": [
            ("DEP'İN ATTIĞI MS GOL", own_values(away_history, "teamGoalsFT")),
            ("EVİN YEDİRDİĞİ MS GOL", own_values(home_history, "opponentGoalsFT")),
            ("HAKEM DEP MS GOL", side_values(ref_history, "finalScore", "away"))
        ]
    }

    expectations = {}
    details = {}

    for market, sources in markets.items():
        votes = {"TEK": 0, "ÇİFT": 0}
        source_details = []

        for source_name, values in sources:
            prediction = prediction_for_values(values)

            if not prediction:
                continue

            expected = prediction["expected"]
            weight = prediction["weight"]
            votes[expected] += weight

            source_details.append({
                "source": source_name,
                "expected": expected,
                "kind": prediction["kind"],
                "length": prediction["length"],
                "weight": weight,
                "last": prediction.get("last"),
                "sequence": prediction.get("sequence", []),
                "pattern": prediction.get("pattern")
            })

        if votes["TEK"] > votes["ÇİFT"]:
            decision = "TEK"
        elif votes["ÇİFT"] > votes["TEK"]:
            decision = "ÇİFT"
        else:
            decision = "DEĞİŞKEN"

        expectations[market] = decision
        details[market] = {
            "decision": decision,
            "votes": votes,
            "sources": source_details,
            "supportCount": sum(
                1 for item in source_details
                if item["expected"] == decision
            ) if decision != "DEĞİŞKEN" else 0,
            "conflict": votes["TEK"] > 0 and votes["ÇİFT"] > 0
        }

    return expectations, details


# ============================================================
# SKOR KOSULLARI
# ============================================================

def score_matches_expectations(ht_home, ht_away, ft_home, ft_away, expectations):
    values = {
        "İY": ht_home + ht_away,
        "İY EV": ht_home,
        "İY DEP": ht_away,
        "MS": ft_home + ft_away,
        "MS EV": ft_home,
        "MS DEP": ft_away
    }

    for market, expected in expectations.items():
        if expected in ("TEK", "ÇİFT"):
            if parity(values[market]) != expected:
                return False

    return True


def generate_main_score_scenarios(expectations, limit=60):
    """
    Ana sistemin altı pazar beklentisine uyan skor çiftlerini üretir.
    Burada favori veya alternatif analiz puanı kullanılmaz.
    """
    scenarios = []

    for ht_home in range(5):
        for ht_away in range(5):
            for ft_home in range(ht_home, 7):
                for ft_away in range(ht_away, 7):
                    if not score_matches_expectations(
                        ht_home, ht_away, ft_home, ft_away, expectations
                    ):
                        continue

                    scenarios.append({
                        "halfTimeScore": f"{ht_home}-{ht_away}",
                        "finalScore": f"{ft_home}-{ft_away}",
                        "source": "ANA SİSTEM"
                    })

    scenarios.sort(
        key=lambda item: (
            sum(int(x) for x in item["finalScore"].split("-")),
            sum(int(x) for x in item["halfTimeScore"].split("-"))
        )
    )

    return scenarios[:limit]


# ============================================================
# TAKIM GOL VERISI VE ALTERNATIF ANALIZ
# ============================================================

def average(values):
    clean = [float(value) for value in values if value is not None]

    if not clean:
        return None

    return sum(clean) / len(clean)


def team_goal_samples(history, side, field):
    """
    Geçmiş takım kayıtlarında takımın kendi attığı/yediği golü döndürür.
    Ev/deplasman ayrımı kayıtların home/away alanından yapılır.
    """
    values = []

    for item in ordered(history)[-HISTORY_LIMIT:]:
        if side == "home" and item.get("home") is False:
            continue
        if side == "away" and item.get("away") is False:
            continue

        value = item.get(field)

        if value is not None:
            try:
                values.append(float(value))
            except (ValueError, TypeError):
                continue

    return values


def team_profile(history, venue):
    """
    Takımın attığı ve yediği gol ortalamalarını hesaplar.
    Önce istenen saha türünü, veri yoksa genel geçmişi kullanır.
    """
    scored_field = "teamGoalsFT"
    conceded_field = "opponentGoalsFT"

    scored = team_goal_samples(history, venue, scored_field)
    conceded = team_goal_samples(history, venue, conceded_field)

    if len(scored) < 3:
        scored = team_goal_samples(history, "all", scored_field)

    if len(conceded) < 3:
        conceded = team_goal_samples(history, "all", conceded_field)

    return {
        "scored": average(scored),
        "conceded": average(conceded),
        "sampleScored": len(scored),
        "sampleConceded": len(conceded)
    }


def expected_goals(home_history, away_history):
    """
    Ev sahibi gol beklentisi:
    ev sahibinin gol üretimi ve deplasmanın gol yeme verisi.

    Deplasman gol beklentisi:
    deplasmanın gol üretimi ve ev sahibinin gol yeme verisi.
    """
    home = team_profile(home_history, "home")
    away = team_profile(away_history, "away")

    home_inputs = [
        home["scored"],
        away["conceded"]
    ]
    away_inputs = [
        away["scored"],
        home["conceded"]
    ]

    home_inputs = [value for value in home_inputs if value is not None]
    away_inputs = [value for value in away_inputs if value is not None]

    home_expected = average(home_inputs)
    away_expected = average(away_inputs)

    # Saha ayrımında yeterli veri yoksa genel takım ortalamasına
    # düşülür; yine veri yoksa skor tahmini yapılmaz.
    return home_expected, away_expected, home, away


def poisson_probability(goals, expected):
    if expected is None or expected < 0:
        return 0.0

    expected = max(0.05, min(expected, 5.0))

    return (
        math.exp(-expected)
        * (expected ** goals)
        / math.factorial(goals)
    )


def score_data_strength(ht_home, ht_away, ft_home, ft_away,
                        expected_home, expected_away):
    """
    Skorun takım gol ortalamalarına göre göreli model desteği.
    Gerçekleşme olasılığı değildir.
    """
    if expected_home is None or expected_away is None:
        return 0.0

    ft_probability = (
        poisson_probability(ft_home, expected_home)
        * poisson_probability(ft_away, expected_away)
    )

    # İlk yarı skorunun, maç sonu skorundan daha düşük kalması
    # doğal olarak kontrol edilir; yarı gol beklentisi yaklaşık
    # maç sonu gol beklentisinin %45'i kabul edilir.
    ht_probability = (
        poisson_probability(ht_home, expected_home * 0.45)
        * poisson_probability(ht_away, expected_away * 0.45)
    )

    return ft_probability * ht_probability


def generate_alternative_scores(
    expectations,
    home_history,
    away_history,
    excluded,
    limit=60
):
    """
    Ana sistem altı skor üretemediğinde kalan yerleri doldurur.
    Ana sistemin net verdiği tek/çift kararları burada da zorunludur.
    """
    expected_home, expected_away, home_profile, away_profile = (
        expected_goals(home_history, away_history)
    )

    if expected_home is None or expected_away is None:
        return [], {
            "available": False,
            "reason": "Gol ortalamalarını hesaplamak için yeterli takım verisi yok.",
            "homeExpectedGoals": expected_home,
            "awayExpectedGoals": expected_away
        }

    candidates = []

    for ht_home in range(5):
        for ht_away in range(5):
            for ft_home in range(ht_home, 7):
                for ft_away in range(ht_away, 7):
                    if not score_matches_expectations(
                        ht_home, ht_away, ft_home, ft_away, expectations
                    ):
                        continue

                    key = (
                        f"{ht_home}-{ht_away}",
                        f"{ft_home}-{ft_away}"
                    )

                    if key in excluded:
                        continue

                    strength = score_data_strength(
                        ht_home,
                        ht_away,
                        ft_home,
                        ft_away,
                        expected_home,
                        expected_away
                    )

                    if strength <= 0:
                        continue

                    candidates.append({
                        "halfTimeScore": key[0],
                        "finalScore": key[1],
                        "source": "ALTERNATİF ANALİZ",
                        "rawStrength": strength
                    })

    candidates.sort(
        key=lambda item: item["rawStrength"],
        reverse=True
    )

    return candidates[:limit], {
        "available": True,
        "reason": None,
        "homeExpectedGoals": round(expected_home, 2),
        "awayExpectedGoals": round(expected_away, 2),
        "homeSamples": min(
            home_profile["sampleScored"],
            home_profile["sampleConceded"]
        ),
        "awaySamples": min(
            away_profile["sampleScored"],
            away_profile["sampleConceded"]
        )
    }


# ============================================================
# ALTI SKORU BIRLESTIR VE SIRALA
# ============================================================

def build_six_score_picks(
    expectations,
    home_history,
    away_history
):
    """
    Ana sistem skorları önceliklidir.
    Altı skor tamamlanmazsa alternatif analiz kalan yerleri doldurur.
    """
    main_scores = generate_main_score_scenarios(
        expectations,
        limit=60
    )

    expected_home, expected_away, _, _ = expected_goals(
        home_history,
        away_history
    )

    # Ana sistem skorlarının kendi iç sıralaması da takım gol
    # verileriyle yapılır. Ana sistemin ürettiği skorlar korunur.
    if expected_home is not None and expected_away is not None:
        for item in main_scores:
            ht_home, ht_away = map(
                int, item["halfTimeScore"].split("-")
            )
            ft_home, ft_away = map(
                int, item["finalScore"].split("-")
            )

            item["rawStrength"] = score_data_strength(
                ht_home, ht_away, ft_home, ft_away,
                expected_home, expected_away
            )

        main_scores.sort(
            key=lambda item: item.get("rawStrength", 0),
            reverse=True
        )

    selected = main_scores[:MAX_SCORE_PICKS]
    used = {
        (item["halfTimeScore"], item["finalScore"])
        for item in selected
    }

    alternative_meta = {
        "available": False,
        "reason": "Ana sistem altı skor üretti; alternatif analize ihtiyaç yok."
    }

    if len(selected) < MAX_SCORE_PICKS:
        alternatives, alternative_meta = generate_alternative_scores(
            expectations,
            home_history,
            away_history,
            used,
            limit=MAX_SCORE_PICKS - len(selected)
        )

        selected.extend(alternatives)

    # Skorların göreli veri destek puanı.
    raw_values = [
        max(0.0, float(item.get("rawStrength", 0.0)))
        for item in selected
    ]
    total_strength = sum(raw_values)

    for index, item in enumerate(selected):
        if total_strength > 0:
            support = raw_values[index] / total_strength * 100
        else:
            support = 0.0

        item["rank"] = index + 1
        item["supportScore"] = round(support, 1)
        item.pop("rawStrength", None)

    return selected, alternative_meta


# ============================================================
# KURAL TARAMASI
# ============================================================

def analyze_match(match):
    home_history = match.get("homeMatches") or []
    away_history = match.get("awayMatches") or []
    ref_history = match.get("refMatches") or []

    signals = []

    # A1 - IY TOPLAM GOL ORUNTUSU
    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        values = total_values(history, "halfTimeScore")
        add_pattern(
            signals,
            f"A1_{side}",
            f"İY TOPLAM ÖRÜNTÜ ({side})",
            values
        )

    # A2 - TAKIMIN KENDI IY GOLU
    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        values = own_values(history, "teamGoalsHT")
        add_analysis(
            signals,
            f"A2_{side}",
            f"İY TAKIM GOLÜ ({side})",
            values
        )

    # A3 - IY TOPLAM GOL SERISI
    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        values = total_values(history, "halfTimeScore")
        add_streak(
            signals,
            f"A3_{side}",
            f"İY TOPLAM SERİ ({side})",
            values
        )

    # B1 - MS TOPLAM GOL ORUNTUSU
    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        values = total_values(history, "finalScore")
        add_pattern(
            signals,
            f"B1_{side}",
            f"MS TOPLAM ÖRÜNTÜ ({side})",
            values
        )

    # B2 - TAKIMIN KENDI MS GOLU
    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        values = own_values(history, "teamGoalsFT")
        add_analysis(
            signals,
            f"B2_{side}",
            f"MS TAKIM GOLÜ ({side})",
            values
        )

    # C1 - HAKEM IY TOPLAM
    ref_ht = total_values(ref_history, "halfTimeScore")
    add_analysis(signals, "C1", "HAKEM İY TOPLAM", ref_ht)

    # C2 - HAKEM MS TOPLAM
    ref_ft = total_values(ref_history, "finalScore")
    add_analysis(signals, "C2", "HAKEM MS TOPLAM", ref_ft)

    # C3 - HAKEM EV SAHIBI IY GOL
    add_analysis(
        signals,
        "C3",
        "HAKEM EV SAHİBİ İY GOL",
        side_values(ref_history, "halfTimeScore", "home")
    )

    # C4 - HAKEM EV SAHIBI MS GOL
    add_analysis(
        signals,
        "C4",
        "HAKEM EV SAHİBİ MS GOL",
        side_values(ref_history, "finalScore", "home")
    )

    # C5 - HAKEM DEPLASMAN IY GOL
    add_analysis(
        signals,
        "C5",
        "HAKEM DEPLASMAN İY GOL",
        side_values(ref_history, "halfTimeScore", "away")
    )

    # C6 - HAKEM DEPLASMAN MS GOL
    add_analysis(
        signals,
        "C6",
        "HAKEM DEPLASMAN MS GOL",
        side_values(ref_history, "finalScore", "away")
    )

    # C7 - HAKEM IY IKILI BLOK
    add_pattern(
        signals,
        "C7",
        "HAKEM İY İKİLİ BLOK",
        ref_ht,
        pair=True
    )

    expectations, expectation_details = build_expectations(
        home_history,
        away_history,
        ref_history
    )

    score_picks, alternative_meta = build_six_score_picks(
        expectations,
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
        "expectationDetails": expectation_details,
        "scoreScenarios": score_picks,
        "alternativeAnalysis": alternative_meta,
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
        raise SystemExit("HATA: bulten.json bulunamadi.")

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

        has_expectation = any(
            value != "DEĞİŞKEN"
            for value in analysis["expectations"].values()
        )

        has_scores = bool(analysis["scoreScenarios"])

        if not signals and not special and not has_expectation and not has_scores:
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
            "expectationDetails": analysis["expectationDetails"],
            "scoreScenarios": analysis["scoreScenarios"],
            "alternativeAnalysis": analysis["alternativeAnalysis"],
            "signals": signals,
            "specialSeries": special,
            "signalCount": len(signals) + len(special),
            "dataQuality": analysis["dataQuality"]
        })

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
            "scorePickCount": MAX_SCORE_PICKS,
            "note": (
                "Ana sistemin TEK/CIFT beklentileri önceliklidir. "
                "Altı skor tamamlanmazsa alternatif gol verisi analizi "
                "eksik skorları doldurur. Alternatif skorlar ana sistemin "
                "net pazar kararlarıyla çelişemez. Destek puanı gerçek "
                "olasılık değildir; seçilen skorlar arasındaki göreli "
                "model desteğini gösterir. Yeterli veri yoksa alternatif "
                "tahmin üretilmez. Bu çıktı garanti veya bahis tavsiyesi değildir."
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
