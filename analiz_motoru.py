
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

# Sistem tahminleri: 3 grup x 3 maç
SYSTEM_PREDICTION_GROUPS = 3
SYSTEM_PICKS_PER_GROUP = 3

MIN_SYSTEM_GOAL_SAMPLES = 3
MIN_SYSTEM_SELECTION_SCORE = 50.0


# ============================================================
# TEMEL VERI ISLEMLERI
# ============================================================

def score(value):
    if value is None or value == "":
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
            try:
                values.append(parity(int(value)))
            except (ValueError, TypeError):
                continue
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
    return " - ".join(str(value) for value in values)


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


def periodic_suffix_length(values, period):
    if len(values) < period:
        return 0

    template = values[-period:]
    length = 0

    for offset in range(1, len(values) + 1):
        template_index = (period - (offset % period)) % period

        if values[-offset] != template[template_index]:
            break

        length += 1

    return length


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

    length = periodic_suffix_length(values, 2)

    return {
        "type": "ÖRÜNTÜ",
        "pattern": "DÖNÜŞÜMLÜ",
        "length": length,
        "sequence": values[-min(length, MAX_SEQUENCE_DISPLAY):],
        "expected": last[-1]
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

    length = periodic_suffix_length(values, 4)

    return {
        "type": "ÖRÜNTÜ",
        "pattern": "İKİLİ BLOK",
        "length": length,
        "sequence": values[-min(length, MAX_SEQUENCE_DISPLAY):],
        "expected": last[-1]
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
            f"Son {result['length']} maçta aralıksız {result['last']} "
            f"oluştu. Serinin bozulma senaryosu {result['expected']}."
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
        "length": result["length"],
        "pattern": result["pattern"],
        "sequence": result["sequence"],
        "expected": result["expected"],
        "explanation": (
            f"{result['length']} maçtır devam eden "
            f"{result['pattern'].lower()} örüntüsü: "
            f"{sequence_text(result['sequence'])}. "
            f"Bozulma senaryosu {result['expected']}."
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
        return False

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
            "length": pattern["length"],
            "last": values[-1],
            "sequence": pattern["sequence"],
            "pattern": pattern["pattern"],
            "weight": pattern["length"]
        }

    pattern = paired(values)

    if pattern:
        return {
            "expected": pattern["expected"],
            "kind": "ÖRÜNTÜ",
            "length": pattern["length"],
            "last": values[-1],
            "sequence": pattern["sequence"],
            "pattern": pattern["pattern"],
            "weight": pattern["length"]
        }

    return None


def venue_own_values(history, team_name, venue, field):
    values = []

    for item in ordered(history):
        if venue == "home" and item.get("home") != team_name:
            continue

        if venue == "away" and item.get("away") != team_name:
            continue

        value = item.get(field)

        if value is not None:
            try:
                values.append(parity(int(value)))
            except (ValueError, TypeError):
                continue

    return values


def source_observation(source_name, values, group):
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
    prediction = prediction_for_values(values)

    if prediction:
        expected = prediction["expected"]
        length = prediction["length"]

        if prediction["kind"] == "SERİ":
            summary = (
                f"Son {length} maçta {prediction['last']} sonucu "
                f"aralıksız oluştu. Serinin kırılma senaryosu {expected}."
            )
        else:
            summary = (
                f"{length} maçtır süren "
                f"{prediction['pattern'].lower()} örüntüsünün "
                f"bozulma senaryosu {expected}."
            )

        weight = prediction["weight"]

    else:
        expected = None
        weight = 0
        length = 0

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
        "length": length,
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
    markets = {
        "İY": [
            (
                "EV TAKIMIN MAÇLARINDA TOPLAM İY GOL",
                "EV TAKIMI",
                total_values(home_history, "halfTimeScore")
            ),
            (
                "DEP TAKIMIN MAÇLARINDA TOPLAM İY GOL",
                "DEP TAKIMI",
                total_values(away_history, "halfTimeScore")
            ),
            (
                "HAKEMİN MAÇLARINDA TOPLAM İY GOL",
                "HAKEM",
                total_values(ref_history, "halfTimeScore")
            )
        ],
        "İY EV": [
            (
                "EV TAKIMIN MAÇLARINDA EV SAHİBİ İY GOLLERİ",
                "EV TAKIMI",
                side_values(home_history, "halfTimeScore", "home")
            ),
            (
                "EV TAKIMIN KENDİ SAHASINDA ATTIĞI İY GOLLER",
                "EV TAKIMI",
                venue_own_values(
                    home_history, home_team_name, "home", "teamGoalsHT"
                )
            ),
            (
                "DEP TAKIMIN MAÇLARINDA EV SAHİBİ İY GOLLERİ",
                "DEP TAKIMI",
                side_values(away_history, "halfTimeScore", "home")
            ),
            (
                "DEP TAKIMIN DEPLASMANDA YEDİĞİ İY GOLLER",
                "DEP TAKIMI",
                venue_own_values(
                    away_history, away_team_name, "away", "opponentGoalsHT"
                )
            ),
            (
                "HAKEMİN MAÇLARINDA EV SAHİBİ İY GOLLERİ",
                "HAKEM",
                side_values(ref_history, "halfTimeScore", "home")
            )
        ],
        "İY DEP": [
            (
                "EV TAKIMIN MAÇLARINDA DEPLASMAN İY GOLLERİ",
                "EV TAKIMI",
                side_values(home_history, "halfTimeScore", "away")
            ),
            (
                "EV TAKIMIN KENDİ SAHASINDA YEDİĞİ İY GOLLER",
                "EV TAKIMI",
                venue_own_values(
                    home_history, home_team_name, "home", "opponentGoalsHT"
                )
            ),
            (
                "DEP TAKIMIN MAÇLARINDA DEPLASMAN İY GOLLERİ",
                "DEP TAKIMI",
                side_values(away_history, "halfTimeScore", "away")
            ),
            (
                "DEP TAKIMIN DEPLASMANDA ATTIĞI İY GOLLER",
                "DEP TAKIMI",
                venue_own_values(
                    away_history, away_team_name, "away", "teamGoalsHT"
                )
            ),
            (
                "HAKEMİN MAÇLARINDA DEPLASMAN İY GOLLERİ",
                "HAKEM",
                side_values(ref_history, "halfTimeScore", "away")
            )
        ],
        "MS": [
            (
                "EV TAKIMIN MAÇLARINDA TOPLAM MS GOL",
                "EV TAKIMI",
                total_values(home_history, "finalScore")
            ),
            (
                "DEP TAKIMIN MAÇLARINDA TOPLAM MS GOL",
                "DEP TAKIMI",
                total_values(away_history, "finalScore")
            ),
            (
                "HAKEMİN MAÇLARINDA TOPLAM MS GOL",
                "HAKEM",
                total_values(ref_history, "finalScore")
            )
        ],
        "MS EV": [
            (
                "EV TAKIMIN MAÇLARINDA EV SAHİBİ MS GOLLERİ",
                "EV TAKIMI",
                side_values(home_history, "finalScore", "home")
            ),
            (
                "EV TAKIMIN KENDİ SAHASINDA ATTIĞI MS GOLLER",
                "EV TAKIMI",
                venue_own_values(
                    home_history, home_team_name, "home", "teamGoalsFT"
                )
            ),
            (
                "DEP TAKIMIN MAÇLARINDA EV SAHİBİ MS GOLLERİ",
                "DEP TAKIMI",
                side_values(away_history, "finalScore", "home")
            ),
            (
                "DEP TAKIMIN DEPLASMANDA YEDİĞİ MS GOLLER",
                "DEP TAKIMI",
                venue_own_values(
                    away_history, away_team_name, "away", "opponentGoalsFT"
                )
            ),
            (
                "HAKEMİN MAÇLARINDA EV SAHİBİ MS GOLLERİ",
                "HAKEM",
                side_values(ref_history, "finalScore", "home")
            )
        ],
        "MS DEP": [
            (
                "EV TAKIMIN MAÇLARINDA DEPLASMAN MS GOLLERİ",
                "EV TAKIMI",
                side_values(home_history, "finalScore", "away")
            ),
            (
                "EV TAKIMIN KENDİ SAHASINDA YEDİĞİ MS GOLLER",
                "EV TAKIMI",
                venue_own_values(
                    home_history, home_team_name, "home", "opponentGoalsFT"
                )
            ),
            (
                "DEP TAKIMIN MAÇLARINDA DEPLASMAN MS GOLLERİ",
                "DEP TAKIMI",
                side_values(away_history, "finalScore", "away")
            ),
            (
                "DEP TAKIMIN DEPLASMANDA ATTIĞI MS GOLLER",
                "DEP TAKIMI",
                venue_own_values(
                    away_history, away_team_name, "away", "teamGoalsFT"
                )
            ),
            (
                "HAKEMİN MAÇLARINDA DEPLASMAN MS GOLLERİ",
                "HAKEM",
                side_values(ref_history, "finalScore", "away")
            )
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
            observation = source_observation(
                source_name, values, group
            )

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
# SKOR MOTORU
# ============================================================

def score_markets(ht_home, ht_away, ft_home, ft_away):
    return {
        "İY": ht_home + ht_away,
        "İY EV": ht_home,
        "İY DEP": ht_away,
        "MS": ft_home + ft_away,
        "MS EV": ft_home,
        "MS DEP": ft_away
    }


def score_matches_expectations(
    ht_home,
    ht_away,
    ft_home,
    ft_away,
    expectations
):
    values = score_markets(
        ht_home, ht_away, ft_home, ft_away
    )

    for market, expected in expectations.items():
        if (
            expected in ("TEK", "ÇİFT")
            and parity(values[market]) != expected
        ):
            return False

    return True


def poisson_probability(goals, expected):
    if expected is None or expected < 0:
        return 0.0

    expected = max(0.05, min(float(expected), 5.0))

    return (
        math.exp(-expected)
        * (expected ** goals)
        / math.factorial(goals)
    )


def average(values):
    clean = []

    for value in values:
        if value is None:
            continue

        try:
            clean.append(float(value))
        except (ValueError, TypeError):
            continue

    return sum(clean) / len(clean) if clean else None


def expected_goals_from_profiles(home_profile, away_profile):
    home_inputs = [
        home_profile.get("scored"),
        away_profile.get("conceded")
    ]

    away_inputs = [
        away_profile.get("scored"),
        home_profile.get("conceded")
    ]

    home_inputs = [v for v in home_inputs if v is not None]
    away_inputs = [v for v in away_inputs if v is not None]

    return average(home_inputs), average(away_inputs)


def score_data_strength(
    ht_home,
    ht_away,
    ft_home,
    ft_away,
    expected_home,
    expected_away
):
    if expected_home is None or expected_away is None:
        return 0.0

    ft = (
        poisson_probability(ft_home, expected_home)
        * poisson_probability(ft_away, expected_away)
    )

    ht = (
        poisson_probability(ht_home, expected_home * 0.45)
        * poisson_probability(ht_away, expected_away * 0.45)
    )

    return ft * ht


def team_goal_samples(history, team_name, venue, field):
    values = []

    for item in ordered(history)[-RECENT_FORM_LIMIT:]:
        if venue == "home" and item.get("home") != team_name:
            continue

        if venue == "away" and item.get("away") != team_name:
            continue

        value = item.get(field)

        if value is not None:
            try:
                values.append(float(value))
            except (ValueError, TypeError):
                continue

    return values


def team_profile(history, team_name, venue):
    scored = team_goal_samples(
        history, team_name, venue, "teamGoalsFT"
    )

    conceded = team_goal_samples(
        history, team_name, venue, "opponentGoalsFT"
    )

    if len(scored) < 3:
        scored = team_goal_samples(
            history, team_name, "all", "teamGoalsFT"
        )

    if len(conceded) < 3:
        conceded = team_goal_samples(
            history, team_name, "all", "opponentGoalsFT"
        )

    return {
        "scored": average(scored),
        "conceded": average(conceded),
        "sampleScored": len(scored),
        "sampleConceded": len(conceded)
    }


def expected_goals(
    home_history,
    away_history,
    home_team_name,
    away_team_name
):
    home = team_profile(
        home_history, home_team_name, "home"
    )

    away = team_profile(
        away_history, away_team_name, "away"
    )

    home_expected, away_expected = expected_goals_from_profiles(
        home, away
    )

    return home_expected, away_expected, home, away


def generate_score_candidates(
    expectations,
    expected_home,
    expected_away,
    limit=120
):
    candidates = []
    weights = {}

    for market, decision in expectations.items():
        if decision not in ("TEK", "ÇİFT"):
            continue

        weights[market] = 1.0

    for hh in range(5):
        for ha in range(5):
            for fh in range(hh, 7):
                for fa in range(ha, 7):

                    values = score_markets(hh, ha, fh, fa)

                    mismatches = [
                        market
                        for market, decision in expectations.items()
                        if (
                            decision in ("TEK", "ÇİFT")
                            and parity(values[market]) != decision
                        )
                    ]

                    is_main = not mismatches

                    strength = score_data_strength(
                        hh,
                        ha,
                        fh,
                        fa,
                        expected_home,
                        expected_away
                    )

                    if strength <= 0:
                        total_goals = fh + fa

                        strength = 1.0 / (
                            1.0
                            + abs(total_goals - 2.5)
                            + abs(hh + ha - 1.0)
                        )

                    penalty = sum(
                        weights.get(m, 1.0)
                        for m in mismatches
                    )

                    adjusted = strength / (1.0 + penalty * 2.0)

                    candidates.append({
                        "halfTimeScore": f"{hh}-{ha}",
                        "finalScore": f"{fh}-{fa}",
                        "source": (
                            "ANA SİSTEM"
                            if is_main
                            else "UZLAŞTIRILMIŞ ALTERNATİF"
                        ),
                        "rawStrength": (
                            strength if is_main else adjusted
                        ),
                        "matchedMarkets": (
                            len(expectations) - len(mismatches)
                        ),
                        "conflictingMarkets": mismatches
                    })

    candidates.sort(
        key=lambda x: (
            x["source"] == "ANA SİSTEM",
            x["matchedMarkets"],
            x["rawStrength"]
        ),
        reverse=True
    )

    return candidates[:limit]


def build_six_score_picks(
    expectations,
    home_history,
    away_history,
    home_team_name,
    away_team_name,
    expectation_details=None
):
    (
        expected_home,
        expected_away,
        home_profile,
        away_profile
    ) = expected_goals(
        home_history,
        away_history,
        home_team_name,
        away_team_name
    )

    candidates = generate_score_candidates(
        expectations,
        expected_home,
        expected_away,
        limit=200
    )

    selected = candidates[:MAX_SCORE_PICKS]

    main_count = sum(
        1 for item in selected
        if item["source"] == "ANA SİSTEM"
    )

    fallback_used = main_count < MAX_SCORE_PICKS

    raw = [
        max(0.0, float(item.get("rawStrength", 0)))
        for item in selected
    ]

    total = sum(raw)

    for index, item in enumerate(selected):
        item["rank"] = index + 1

        item["supportScore"] = (
            round(raw[index] / total * 100, 1)
            if total else 0.0
        )

        item.pop("rawStrength", None)

    sample_counts = {
        "homeScored": home_profile["sampleScored"],
        "homeConceded": home_profile["sampleConceded"],
        "awayScored": away_profile["sampleScored"],
        "awayConceded": away_profile["sampleConceded"]
    }

    sufficient = all(
        value >= MIN_SYSTEM_GOAL_SAMPLES
        for value in sample_counts.values()
    )

    meta = {
        "available": sufficient,
        "fallbackUsed": fallback_used,
        "reason": (
            "Bazı skorlar çelişen sinyaller nedeniyle uzlaştırılmış "
            "alternatif olarak üretildi; her skorun conflictingMarkets "
            "alanı kontrol edilebilir."
            if fallback_used
            else "Skorlar ana sistemin kesin beklentileriyle uyumlu."
        ),
        "homeExpectedGoals": (
            round(expected_home, 2)
            if expected_home is not None else None
        ),
        "awayExpectedGoals": (
            round(expected_away, 2)
            if expected_away is not None else None
        ),
        "homeSamples": min(
            home_profile["sampleScored"],
            home_profile["sampleConceded"]
        ),
        "awaySamples": min(
            away_profile["sampleScored"],
            away_profile["sampleConceded"]
        ),
        "sampleCounts": sample_counts,
        "minimumSamples": MIN_SYSTEM_GOAL_SAMPLES
    }

    return selected, meta


# ============================================================
# KURAL TARAMASI
# ============================================================

def analyze_match(match):
    home_history = match.get("homeMatches") or []
    away_history = match.get("awayMatches") or []
    ref_history = match.get("refMatches") or []

    signals = []

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        add_pattern(
            signals,
            f"A1_{side}",
            f"İY TOPLAM ÖRÜNTÜ ({side})",
            total_values(history, "halfTimeScore")
        )

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        add_analysis(
            signals,
            f"A2_{side}",
            f"İY TAKIM GOLÜ ({side})",
            own_values(history, "teamGoalsHT")
        )

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        add_streak(
            signals,
            f"A3_{side}",
            f"İY TOPLAM SERİ ({side})",
            total_values(history, "halfTimeScore")
        )

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        add_pattern(
            signals,
            f"B1_{side}",
            f"MS TOPLAM ÖRÜNTÜ ({side})",
            total_values(history, "finalScore")
        )

    for side, history in (
        ("EV", home_history),
        ("DEP", away_history)
    ):
        add_analysis(
            signals,
            f"B2_{side}",
            f"MS TAKIM GOLÜ ({side})",
            own_values(history, "teamGoalsFT")
        )

    ref_ht = total_values(ref_history, "halfTimeScore")
    ref_ft = total_values(ref_history, "finalScore")

    add_analysis(signals, "C1", "HAKEM İY TOPLAM", ref_ht)
    add_analysis(signals, "C2", "HAKEM MS TOPLAM", ref_ft)

    add_analysis(
        signals,
        "C3",
        "HAKEM EV SAHİBİ İY GOL",
        side_values(ref_history, "halfTimeScore", "home")
    )

    add_analysis(
        signals,
        "C4",
        "HAKEM EV SAHİBİ MS GOL",
        side_values(ref_history, "finalScore", "home")
    )

    add_analysis(
        signals,
        "C5",
        "HAKEM DEPLASMAN İY GOL",
        side_values(ref_history, "halfTimeScore", "away")
    )

    add_analysis(
        signals,
        "C6",
        "HAKEM DEPLASMAN MS GOL",
        side_values(ref_history, "finalScore", "away")
    )

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
        ref_history,
        match.get("home"),
        match.get("away")
    )

    score_picks, alternative_meta = build_six_score_picks(
        expectations,
        home_history,
        away_history,
        match.get("home"),
        match.get("away"),
        expectation_details
    )

    special = collect_special_series(
        home_history,
        away_history
    )

    _, _, home_goal_profile, away_goal_profile = expected_goals(
        home_history,
        away_history,
        match.get("home"),
        match.get("away")
    )

    goal_data_quality = {
        "homeScored": home_goal_profile["sampleScored"],
        "homeConceded": home_goal_profile["sampleConceded"],
        "awayScored": away_goal_profile["sampleScored"],
        "awayConceded": away_goal_profile["sampleConceded"]
    }

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
        },
        "goalDataQuality": goal_data_quality
    }


# ============================================================
# GUNLUK SISTEM TAHMINLERI
# ============================================================

def build_system_predictions(matches, target_date):
    candidates = []
    turkey_timezone = timezone(timedelta(hours=3))

    for match in matches:
        match_datetime = parse_date(match.get("date"))

        if not match_datetime:
            continue

        if match_datetime.tzinfo is None:
            match_datetime = match_datetime.replace(
                tzinfo=timezone.utc
            )

        if (
            match_datetime.astimezone(turkey_timezone).date()
            != target_date
        ):
            continue

        scenarios = match.get("scoreScenarios") or []

        if not scenarios:
            continue

        goal_quality = match.get("goalDataQuality") or {}

        sample_counts = {
            "homeScored": int(goal_quality.get("homeScored") or 0),
            "homeConceded": int(goal_quality.get("homeConceded") or 0),
            "awayScored": int(goal_quality.get("awayScored") or 0),
            "awayConceded": int(goal_quality.get("awayConceded") or 0)
        }

        if any(
            count < MIN_SYSTEM_GOAL_SAMPLES
            for count in sample_counts.values()
        ):
            continue

        best = scenarios[0]

        expectations = match.get("expectations") or {}
        details = match.get("expectationDetails") or {}

        fixed_markets = [
            market
            for market, value in expectations.items()
            if value in ("TEK", "ÇİFT")
        ]

        support_counts = [
            float(
                (details.get(market) or {}).get("supportCount") or 0
            )
            for market in fixed_markets
        ]

        consensus = (
            sum(support_counts) / len(support_counts) / 3 * 100
            if support_counts
            else 50.0
        )

        data_coverage = (
            sum(
                min(count, RECENT_FORM_LIMIT) / RECENT_FORM_LIMIT
                for count in sample_counts.values()
            ) / 4 * 100
        )

        expectation_coverage = (
            len(fixed_markets) / 6 * 100
            if fixed_markets
            else 50.0
        )

        signal_count = int(match.get("signalCount") or 0)

        selection_score = (
            data_coverage * 0.35
            + expectation_coverage * 0.30
            + consensus * 0.20
            + min(signal_count, 12) / 12 * 100 * 0.15
        )

        if selection_score < MIN_SYSTEM_SELECTION_SCORE:
            continue

        # SERİ VE ÖRÜNTÜ SAYILARINI AYRI HESAPLA
        signals = match.get("signals") or []
        special_series = match.get("specialSeries") or []

        series_signals = [
            signal for signal in signals
            if signal.get("kind") == "SERİ"
        ]

        pattern_signals = [
            signal for signal in signals
            if signal.get("kind") == "ÖRÜNTÜ"
        ]

        # Normal seriler + 6 ve üzeri özel seriler
        max_series_length = max(
            [
                int(signal.get("length") or 0)
                for signal in series_signals
            ]
            + [
                int(signal.get("length") or 0)
                for signal in special_series
            ]
            + [0]
        )

        series_count = (
            len(series_signals) + len(special_series)
        )

        pattern_count = len(pattern_signals)

        candidates.append({
            "id": match.get("id"),
            "date": match.get("date"),
            "country": match.get("country"),
            "league": match.get("league"),
            "home": match.get("home"),
            "away": match.get("away"),
            "halfTimeScore": best.get("halfTimeScore"),
            "finalScore": best.get("finalScore"),
            "scoreSource": best.get("source"),
            "selectionScore": round(selection_score, 1),
            "fixedMarketCount": len(fixed_markets),
            "signalCount": signal_count,
            "seriesCount": series_count,
            "patternCount": pattern_count,
            "maxSeriesLength": max_series_length,
            "goalSampleCounts": sample_counts,
            "reason": (
                f"{signal_count} sinyal; en uzun seri "
                f"{max_series_length}; {series_count} seri, "
                f"{pattern_count} örüntü; "
                f"{len(fixed_markets)}/6 kesin pazar "
                "ve veri kalitesi değerlendirildi."
            )
        })

    # ÖNCELİK:
    # 1. En çok sinyal
    # 2. En uzun seri
    # 3. Veri ve beklenti kalitesi
    # 4. Kesin pazar sayısı
    candidates.sort(
        key=lambda item: (
            item["signalCount"],
            item["maxSeriesLength"],
            item["selectionScore"],
            item["fixedMarketCount"],
            item.get("date") or ""
        ),
        reverse=True
    )

    maximum = (
        SYSTEM_PREDICTION_GROUPS
        * SYSTEM_PICKS_PER_GROUP
    )

    selected = candidates[:maximum]

    groups = []

    for group_index in range(SYSTEM_PREDICTION_GROUPS):
        start = group_index * SYSTEM_PICKS_PER_GROUP
        end = start + SYSTEM_PICKS_PER_GROUP

        group_picks = selected[start:end]

        if group_picks:
            groups.append({
                "group": group_index + 1,
                "title": f"Grup {group_index + 1}",
                "matches": group_picks
            })

    return {
        "date": target_date.isoformat(),
        "targetCount": maximum,
        "groupsOf": SYSTEM_PICKS_PER_GROUP,
        "selectedCount": len(selected),
        "groupCount": len(groups),
        "groups": groups,
        "note": (
            "Sistem tahminleri önce toplam sinyal sayısına, "
            "eşitlikte en uzun seriye; ardından veri kapsamı "
            "ve beklenti tutarlılığına göre sıralanır. "
            "Her grupta en fazla 3 maç bulunur. "
            "Seçim puanı gerçek olasılık değildir."
        )
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

        has_expectation = any(
            value != "DEĞİŞKEN"
            for value in analysis["expectations"].values()
        )

        has_scores = bool(analysis["scoreScenarios"])

        goal_quality = analysis["goalDataQuality"]

        has_goal_data = all(
            int(goal_quality.get(field) or 0)
            >= MIN_SYSTEM_GOAL_SAMPLES
            for field in (
                "homeScored",
                "homeConceded",
                "awayScored",
                "awayConceded"
            )
        )

        if (
            not signals
            and not special
            and not has_expectation
            and not has_scores
            and not has_goal_data
        ):
            continue

        signal_count = len(signals) + len(special)

        series_signals = [
            signal for signal in signals
            if signal.get("kind") == "SERİ"
        ]

        pattern_signals = [
            signal for signal in signals
            if signal.get("kind") == "ÖRÜNTÜ"
        ]

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
            "signalCount": signal_count,
            "seriesCount": (
                len(series_signals) + len(special)
            ),
            "patternCount": len(pattern_signals),
            "maxSeriesLength": max(
                [
                    signal.get("length", 0)
                    for signal in series_signals
                ]
                + [
                    signal.get("length", 0)
                    for signal in special
                ]
                + [0]
            ),
            "maxPatternLength": max(
                [
                    signal.get("length", 0)
                    for signal in pattern_signals
                ] + [0]
            ),
            "summary": (
                f"{signal_count} sinyal tespit edildi. "
                f"{len(series_signals) + len(special)} seri ve "
                f"{len(pattern_signals)} örüntü bulgusu var. "
                + (
                    f"En güçlü skor senaryosu İY "
                    f"{analysis['scoreScenarios'][0]['halfTimeScore']} / "
                    f"MS {analysis['scoreScenarios'][0]['finalScore']}."
                    if analysis["scoreScenarios"]
                    else "Yeterli veya uyumlu skor senaryosu üretilemedi."
                )
            ),
            "dataQuality": analysis["dataQuality"],
            "goalDataQuality": analysis["goalDataQuality"]
        })

    # Genel maç listesi sıralaması
    results.sort(
        key=lambda item: (
            item["signalCount"],
            item["maxSeriesLength"],
            item["maxPatternLength"],
            item.get("date") or ""
        ),
        reverse=True
    )

    turkey_timezone = timezone(timedelta(hours=3))

    target_date = now.astimezone(
        turkey_timezone
    ).date()

    system_predictions = build_system_predictions(
        results,
        target_date
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
            "systemPredictionGroups": SYSTEM_PREDICTION_GROUPS,
            "systemPicksPerGroup": SYSTEM_PICKS_PER_GROUP,
            "systemPredictionMaximum": (
                SYSTEM_PREDICTION_GROUPS
                * SYSTEM_PICKS_PER_GROUP
            ),
            "note": (
                "Dönüşümlü ve ikili blok örüntülerinde beklenen "
                "sonuç, örüntünün devamı değil bozulma senaryosudur. "
                "Çelişkili beklentilerde skor üretimi tamamen "
                "durdurulmaz; uzlaştırılmış alternatifler ayrı "
                "etiketlenir. Skor destek puanları gerçek olasılık "
                "değildir. Bu çıktı garanti veya bahis tavsiyesi değildir."
            )
        },

        "summary": {
            "sourceMatches": len(matches),
            "finishedMatches": finished_count,
            "upcomingMatches": upcoming_count,
            "matchesWithSignals": len(results),
            "totalSignals": sum(
                item["signalCount"] for item in results
            ),
            "systemPredictionCount": (
                system_predictions["selectedCount"]
            )
        },

        "systemPredictions": system_predictions,
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
        f"Toplam sinyal: {output['summary']['totalSignals']}"
    )
    print(
        f"Sistem tahmini: "
        f"{system_predictions['selectedCount']}/9"
    )
    print("analiz.json kaydedildi.")
    print("=" * 60)


if __name__ == "__main__":
    main()
