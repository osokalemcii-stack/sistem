import json
import os

# Lig listesi tanimlama
ligler = [
    "Türkiye Süper Lig",
    "Türkiye 1. Lig",
    "İngiltere Premier Lig",
    "İtalya Serie A",
    "İtalya Serie B",
]

# Örnek bülten verisi oluşturma
bulten_verisi = []
for lig in ligler:
    bulten_verisi.append(
        {
            "lig": lig,
            "maclar": [
                {
                    "ev_sahibi": "Takim A",
                    "deplasman": "Takim B",
                    "oran_ev": 2.10,
                    "oran_beraberlik": 3.20,
                    "oran_deplasman": 3.00,
                }
            ],
        }
    )

# Dosyayı kaydetme
dosya_yolu = "bulten.json"
with open(dosya_yolu, "w", encoding="utf-8") as f:
    json.dump(bulten_verisi, f, ensure_ascii=False, indent=4)

print(f"{dosya_yolu} başarıyla oluşturuldu.")
