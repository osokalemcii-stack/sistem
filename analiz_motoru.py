import json
import re
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

SOURCE = Path("bulten.json")
OUTPUT = Path("analiz.json")

MIN_STREAK = 4
PATTERN_LENGTH = 4
SPECIAL_STREAK = 6
MAX_SEQUENCE_DISPLAY = 10
MAX_SCORE_PICKS = 6
RECENT_FORM_LIMIT = 12
SYSTEM_PREDICTION_GROUPS = 3
SYSTEM_PICKS_PER_GROUP = 4
MIN_SYSTEM_GOAL_SAMPLES = 3
MIN_SYSTEM_SELECTION_SCORE = 50.0


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
        for i in range(1, len(last))
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


def venue_own_values(history, team_name, venue, field):
    """
    Takımın yalnızca kendi belirlenen saha koşulundaki attığı/yediği gol.
    home/away alanları karşılaşmadaki takım adlarıdır.
    """
    values = []

    for item in ordered(history):
        if venue == "home" and item.get("home")
         != team_name:
            continue
        if venue == "away" and item.get("away") != team_name:
            continue

        value = item.get(field)

        if value is not None:
            values.append(parity(value))

    return values


def source_observation(source_name, values, group):
    """
    Seri ve örüntü tüm geçmişten hesaplanır.
    Dağılım ise yakın dönem formu için son 12 maçı kullanır.
    """
    if not values:
        return {
            "source": source_name,
            "group": group,
            "sampleCount": 0,
            "totalSampleCount": 0,
            "expected": None,
            "weight": 0,
            "summary": "Bu kaynak için kullanılabilir geçmiş veri yok."
        }

    recent = values[-RECENT_FORM_LIMIT:]
    odd_count = recent.count("TEK")
    even_count = recent.count("ÇİFT")

    # Seri ve örüntü tüm mevcut geçmiş üzerinden hesaplanır.
    prediction = prediction_for_values(values)

    if prediction:
        expected = prediction["expected"]
        length = prediction["length"]

        if prediction["kind"] == "SERİ":
            summary = (
                f"Son {length} maçın tamamında {prediction['last']} "
                f"sonucu oluştu. Serinin kırılması yönünde "
                f"{expected} beklentisi var."
            )
        else:
            summary = (
                f"Son dört maçta {sequence_text(prediction['sequence'])} "
                f"örüntüsü görüldü. Sonraki sonuç için "
                f"{expected} beklentisi var."
            )

        weight = prediction["weight"]
    else:
        expected = None
        weight = 0
        summary = (
            f"Son {len(recent)} maçta {odd_count} TEK, "
            f"{even_count} ÇİFT sonuç var; yeterli seri veya örüntü yok."
        )

    return {
        "source": source_name,
        "group": group,
        "sampleCount": len(recent),
        "totalSampleCount": len(values),
        "oddCount": odd_count,
        "evenCount": even_count,
        "expected": expected,
        "kind": prediction["kind"] if prediction else None,
        "length": prediction["length"] if prediction else 0,
        "weight": weight,
        "sequence": recent[-MAX_SEQUENCE_DISPLAY:],
        "summary": summary
    }


def build_expectations(
    home_history,
    away_history,
    ref_history,
    home_team_name,
    away_team_name
):
    """
    Takımların oynadığı maçlardaki ev sahibi/deplasman gol yönlerini,
    takımların kendi saha performanslarını ve hakem geçmişini inceler.

    Aynı takımın ilişkili kaynakları ayrı gösterilir; oy ağırlığı takım
    grubu başına sınırlandırılır, böylece aynı maçlar mükerrer oy olmaz.
    """
    markets = {
        "İY": [
            ("EV TAKIMIN MAÇLARINDA TOPLAM İY GOL", "EV TAKIMI",
             total_values(home_history, "halfTimeScore")),
            ("DEP TAKIMIN MAÇLARINDA TOPLAM İY GOL", "DEP TAKIMI",
             total_values(away_history, "halfTimeScore")),
            ("HAKEMİN MAÇLARINDA TOPLAM İY GOL", "HAKEM",
             total_values(ref_history, "halfTimeScore"))
        ],
        "İY EV": [
            ("EV TAKIMIN MAÇLARINDA EV SAHİBİ İY GOLLERİ", "EV TAKIMI",
             side_values(home_history, "halfTimeScore", "home")),
            ("EV TAKIMIN KENDİ SAHASINDA ATTIĞI İY GOLLER", "EV TAKIMI",
             venue_own_values(home_history, home_team_name, "home", "teamGoalsHT")),
            ("DEP TAKIMIN MAÇLARINDA EV SAHİBİ İY GOLLERİ", "DEP TAKIMI",
             side_values(away_history, "halfTimeScore", "home")),
            ("DEP TAKIMIN DEPLASMANDA YEDİĞİ İY GOLLER", "DEP TAKIMI",
             venue_own_values(away_history, away_team_name, "away", "opponentGoalsHT")),
            ("HAKEMİN MAÇLARINDA EV SAHİBİ İY GOLLERİ", "HAKEM",
             side_values(ref_history, "halfTimeScore", "home"))
        ],
        "İY DEP": [
            ("EV TAKIMIN MAÇLARINDA DEPLASMAN İY GOLLERİ", "EV TAKIMI",
             side_values(home_history, "halfTimeScore", "away")),
            ("EV TAKIMIN KENDİ SAHASINDA YEDİĞİ İY GOLLER", "EV TAKIMI",
             venue_own_values(home_history, home_team_name, "home", "opponentGoalsHT")),
            ("DEP TAKIMIN MAÇLARINDA DEPLASMAN İY GOLLERİ", "DEP TAKIMI",
             side_values(away_history, "halfTimeScore", "away")),
            ("DEP TAKIMIN DEPLASMANDA ATTIĞI İY GOLLER", "DEP TAKIMI",
             venue_own_values(away_history, away_team_name, "away", "teamGoalsHT")),
            ("HAKEMİN MAÇLARINDA DEPLASMAN İY GOLLERİ", "HAKEM",
             side_values(ref_history, "halfTimeScore", "away"))
        ],
        "MS": [
            ("EV TAKIMIN MAÇLARINDA TOPLAM MS GOL", "EV TAKIMI",
             total_values(home_history, "finalScore")),
            ("DEP TAKIMIN MAÇLARINDA TOPLAM MS GOL", "DEP TAKIMI",
             total_values(away_history, "finalScore")),
            ("HAKEMİN MAÇLARINDA TOPLAM MS GOL", "HAKEM",
             total_values(ref_history, "finalScore"))
        ],
        "MS EV": [
            ("EV TAKIMIN MAÇLARINDA EV SAHİBİ MS GOLLERİ", "EV TAKIMI",
             side_values(home_history, "finalScore", "home")),
            ("EV TAKIMIN KENDİ SAHASINDA ATTIĞI MS GOLLER", "EV TAKIMI",
             venue_own_values(home_history, home_team_name, "home", "teamGoalsFT")),
            ("DEP TAKIMIN MAÇLARINDA EV SAHİBİ MS GOLLERİ", "DEP TAKIMI",
             side_values(away_history, "finalScore", "home")),
            ("DEP TAKIMIN DEPLASMANDA YEDİĞİ MS GOLLER", "DEP TAKIMI",
             venue_own_values(away_history, away_team_name, "away", "opponentGoalsFT")),
            ("HAKEMİN MAÇLARINDA EV SAHİBİ MS GOLLERİ", "HAKEM",
             side_values(ref_history, "finalScore", "home"))
        ],
        "MS DEP": [
            ("EV TAKIMIN MAÇLARINDA DEPLASMAN MS GOLLERİ", "EV TAKIMI",
             side_values(home_history, "finalScore", "away")),
            ("EV TAKIMIN KENDİ SAHASINDA YEDİĞİ MS GOLLER", "EV TAKIMI",
             venue_own_values(home_history, home_team_name, "home", "opponentGoalsFT")),
            ("DEP TAKIMIN MAÇLARINDA DEPLASMAN MS GOLLERİ", "DEP TAKIMI",
             side_values(away_history, "finalScore", "away")),
            ("DEP TAKIMIN DEPLASMANDA ATTIĞI MS GOLLER", "DEP TAKIMI",
             venue_own_values(away_history, away_team_name, "away", "teamGoalsFT")),
            ("HAKEMİN MAÇLARINDA DEPLASMAN MS GOLLERİ", "HAKEM",
             side_values(ref_history, "finalScore", "away"))
        ]
    }

    expectations = {}
    details = {}

    for market, sources in markets.items():
        group_votes = {
            "EV TAKIMI": {"TEK": 0, "ÇİFT": 0},
            "DEP TAKIMI": {"TEK": 0, "ÇİFT": 0},
            "HAKEM": {"TEK": 0, "ÇİFT": 0}
        }
        source_details = []

        for source_name, group, values in sources:
            observation = source_observation(source_name, values, group)
            source_details.append(observation)

            expected = observation["expected"]
            weight = observation["weight"]

            if expected and weight > group_votes[group][expected]:
                group_votes[group][expected] = weight

        votes = {"TEK": 0, "ÇİFT": 0}

        for group_vote in group_votes.values():
            votes["TEK"] += group_vote["TEK"]
            votes["ÇİFT"] += group_vote["ÇİFT"]

        if votes["TEK"] > votes["ÇİFT"]:
            decision = "TEK"
        elif votes["ÇİFT"] > votes["TEK"]:
            decision = "ÇİFT"
        else:
            decision = "DEĞİŞKEN"

        support_count = 0

        if decision != "DEĞİŞKEN":
            opposite = "ÇİFT" if decision == "TEK" else "TEK"
            support_count = sum(
                1 for group_vote in group_votes.values()
                if group_vote[decision] > group_vote[opposite]
                and group_vote[decision] > 0
            )

        expectations[market] = decision
        details[market] = {
            "decision": decision,
            "votes": votes,
            "groupVotes": group_votes,
            "sources": source_details,
            "supportCount": support_count,
            "conflict": votes["TEK"] > 0 and votes["ÇİFT"] > 0
        }

    return expectations, details


# ============================================================
# SKOR KOSULLARI
# ============================================================

def score_matches_expectations(ht_home, ht_away, ft_home, ft_away, expectations):
    values = {
        "İY": ht_home + ht_away,