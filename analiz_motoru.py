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