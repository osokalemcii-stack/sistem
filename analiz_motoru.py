def generate_main_score_scenarios(expectations, limit=60):
    # Alti piyasanin tamami degiskense ana sistemin kesin bir parity
    # karari yoktur. Bu durumda skor uretmeyip alternatif analize alan ac.
    if not any(value in ("TEK", "ÇİFT") for value in expectations.values()):
        return []

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