import React, { useMemo, useState, useEffect, useCallback } from "react";

const LEAGUES = [
  "Türkiye: Süper Lig",
  "Türkiye: 1.Lig",
  "İngiltere: Premier Lig",
  "İngiltere: Championship",
  "İtalya: Serie A",
  "İtalya: Serie B",
  "İspanya: La Liga",
  "İspanya: La Liga 2",
  "Belçika: Pro Lig",
  "Portekiz: Liga Portugal",
  "Hollanda: Eredivisie",
  "Fransa: Ligue 1",
  "Fransa: Ligue 2",
  "Almanya: Bundesliga",
  "Almanya: Bundesliga 2",
  "Yunanistan: Super Lig",
  "Rusya: Premier Lig",
  "Suudi Arabistan: Pro Lig",
  "İskoçya: Premier Ship",
  "Avusturya: Bundesliga",
  "Azerbaycan: Premier Lig",
  "ABD: MLS",
  "AVRUPA: Uefa Şampiyonlar Ligi",
  "AVRUPA: Uefa Avrupa Ligi",
  "AVRUPA: Uefa Konferans Ligi",
];

const INITIAL_MATCHES = [
  {
    id: "m-finished-1",
    country: "İtalya",
    league: "İtalya: Serie A",
    date: "2026-11-27 13:30",
    home: "Juventus",
    away: "Milan",
    referee: "Marco Guida",
    status: "finished",
    finalScore: "İY 0-0 | MS 1-0",
    homeMatches: [
      "0-0 (1-0)",
      "1-0 (2-1)",
      "0-0 (0-0)",
      "1-0 (1-1)",
      "0-0 (2-0)",
      "1-0 (1-0)",
      "0-0 (1-1)",
    ],
    awayMatches: [
      "1-0 (2-1)",
      "0-1 (1-2)",
      "1-0 (1-0)",
      "0-1 (2-2)",
      "1-0 (3-1)",
      "0-1 (1-1)",
      "1-0 (2-0)",
    ],
    refMatches: [
      "0-0 (1-1)",
      "1-0 (2-1)",
      "0-1 (1-2)",
      "1-1 (2-0)",
      "0-0 (1-0)",
      "1-0 (2-2)",
    ],
  },
  {
    id: "m-finished-2",
    country: "Türkiye",
    league: "Türkiye: 1.Lig",
    date: "2026-11-27 15:00",
    home: "Kocaelispor",
    away: "Sakaryaspor",
    referee: "Atilla Karaoğlan",
    status: "finished",
    finalScore: "İY 1-0 | MS 2-1",
    homeMatches: [
      "1-0 (2-1)",
      "0-1 (1-2)",
      "1-0 (3-0)",
      "0-1 (0-1)",
      "1-0 (2-0)",
      "0-1 (1-1)",
    ],
    awayMatches: [
      "0-0 (1-1)",
      "1-1 (2-2)",
      "0-0 (0-0)",
      "1-1 (1-0)",
      "0-0 (2-1)",
      "1-1 (1-2)",
    ],
    refMatches: [
      "1-0 (2-1)",
      "0-0 (1-0)",
      "1-1 (2-2)",
      "0-1 (1-2)",
      "1-0 (1-1)",
      "0-0 (2-0)",
    ],
  },
  {
    id: "m-1",
    country: "Türkiye",
    league: "Türkiye: Süper Lig",
    date: "2026-11-27 20:00",
    home: "Galatasaray",
    away: "Trabzonspor",
    referee: "Halil Umut Meler",
    status: "upcoming",
    finalScore: "",
    homeMatches: [
      "1-0 (2-1)",
      "0-1 (3-0)",
      "1-0 (1-1)",
      "0-1 (2-0)",
      "1-0 (4-1)",
      "0-1 (1-0)",
      "1-0 (2-2)",
    ],
    awayMatches: [
      "1-0 (2-1)",
      "1-1 (3-2)",
      "0-1 (1-0)",
      "0-0 (2-2)",
      "1-0 (1-2)",
      "1-1 (3-1)",
    ],
    refMatches: [
      "1-0 (2-1)",
      "0-1 (1-2)",
      "1-0 (3-1)",
      "0-1 (0-1)",
      "1-0 (2-0)",
      "0-1 (2-1)",
    ],
  },
  {
    id: "m-2",
    country: "İngiltere",
    league: "İngiltere: Premier Lig",
    date: "2026-11-27 22:30",
    home: "Arsenal",
    away: "Chelsea",
    referee: "Michael Oliver",
    status: "upcoming",
    finalScore: "",
    homeMatches: [
      "1-0 (2-0)",
      "0-0 (1-0)",
      "1-0 (3-1)",
      "0-0 (2-1)",
      "1-0 (1-1)",
      "0-0 (2-0)",
    ],
    awayMatches: [
      "0-0 (1-1)",
      "1-0 (2-1)",
      "0-0 (0-0)",
      "1-0 (1-2)",
      "0-0 (2-2)",
      "1-0 (3-0)",
    ],
    refMatches: [
      "0-0 (1-0)",
      "1-0 (2-1)",
      "0-0 (1-1)",
      "1-0 (3-0)",
      "0-0 (0-0)",
      "1-0 (2-2)",
    ],
  },
  {
    id: "m-3",
    country: "İspanya",
    league: "İspanya: La Liga",
    date: "2026-11-28 18:15",
    home: "Real Madrid",
    away: "Atletico Madrid",
    referee: "Jesús Gil Manzano",
    status: "upcoming",
    finalScore: "",
    homeMatches: [
      "0-0 (1-1)",
      "1-1 (2-2)",
      "0-0 (0-0)",
      "1-1 (1-0)",
      "0-0 (2-1)",
      "1-1 (3-1)",
    ],
    awayMatches: [
      "1-0 (2-1)",
      "0-1 (1-2)",
      "1-0 (1-0)",
      "0-1 (2-0)",
      "1-0 (3-1)",
      "0-1 (1-1)",
    ],
    refMatches: [
      "1-0 (2-1)",
      "0-1 (1-0)",
      "1-0 (2-2)",
      "0-1 (1-2)",
      "1-0 (3-0)",
      "0-1 (1-1)",
    ],
  },
  {
    id: "m-4",
    country: "Almanya",
    league: "Almanya: Bundesliga",
    date: "2026-11-28 20:30",
    home: "Bayern Munich",
    away: "Borussia Dortmund",
    referee: "Felix Zwayer",
    status: "upcoming",
    finalScore: "",
    homeMatches: [
      "0-0 (1-0)",
      "0-1 (1-2)",
      "1-1 (2-2)",
      "1-0 (3-1)",
      "0-0 (0-0)",
      "0-1 (2-1)",
      "1-1 (1-1)",
    ],
    awayMatches: [
      "1-0 (2-1)",
      "0-0 (1-1)",
      "1-0 (3-0)",
      "0-0 (2-0)",
      "1-0 (1-2)",
      "0-0 (1-0)",
    ],
    refMatches: [
      "1-0 (2-1)",
      "0-1 (1-2)",
      "1-0 (3-2)",
      "0-1 (0-1)",
      "1-0 (2-0)",
      "0-1 (1-1)",
    ],
  },
  {
    id: "m-5",
    country: "Hollanda",
    league: "Hollanda: Eredivisie",
    date: "2026-11-28 21:00",
    home: "PSV Eindhoven",
    away: "Ajax",
    referee: "Danny Makkelie",
    status: "upcoming",
    finalScore: "",
    homeMatches: [
      "1-0 (2-1)",
      "1-1 (3-1)",
      "0-0 (2-0)",
      "0-1 (1-2)",
      "1-0 (4-1)",
      "1-1 (2-2)",
    ],
    awayMatches: [
      "0-1 (1-2)",
      "1-0 (2-1)",
      "0-1 (0-2)",
      "1-0 (3-1)",
      "0-1 (1-1)",
      "1-0 (2-0)",
    ],
    refMatches: [
      "1-0 (2-1)",
      "0-1 (1-2)",
      "1-0 (3-1)",
      "0-1 (2-0)",
      "1-0 (1-1)",
      "0-1 (2-2)",
    ],
  },
];

function parseScoreToken(token) {
  if (!token || typeof token !== "string") return null;
  const clean = token.trim();
  const parenMatch = clean.match(/(\d+)\s*-\s*(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*\)/);
  if (parenMatch) {
    return {
      iyH: Number(parenMatch[1]),
      iyA: Number(parenMatch[2]),
      msH: Number(parenMatch[3]),
      msA: Number(parenMatch[4]),
      raw: `${parenMatch[1]}-${parenMatch[2]} (${parenMatch[3]}-${parenMatch[4]})`,
    };
  }
  const slashMatch = clean.match(/(\d+)\s*-\s*(\d+)\s*\/\s*(\d+)\s*-\s*(\d+)/);
  if (slashMatch) {
    return {
      iyH: Number(slashMatch[1]),
      iyA: Number(slashMatch[2]),
      msH: Number(slashMatch[3]),
      msA: Number(slashMatch[4]),
      raw: `${slashMatch[1]}-${slashMatch[2]} (${slashMatch[3]}-${slashMatch[4]})`,
    };
  }
  const simpleMs = clean.match(/^(\d+)\s*-\s*(\d+)$/);
  if (simpleMs) {
    const msH = Number(simpleMs[1]);
    const msA = Number(simpleMs[2]);
    const iyH = msH > 0 ? Math.min(msH, 1) : 0;
    const iyA = msA > 0 ? Math.min(msA, 1) : 0;
    return {
      iyH,
      iyA,
      msH,
      msA,
      raw: `${iyH}-${iyA} (${msH}-${msA})`,
    };
  }
  return null;
}

function toOddEven(sum) {
  return Math.abs(Number(sum || 0)) % 2 === 1 ? "T" : "Ç";
}

function analyzeSequence(seq, halfLabel) {
  if (!Array.isArray(seq) || seq.length < 4) {
    return {
      maxStreak: 0,
      streakSymbol: null,
      patternLabel: null,
      hasStreak5Plus: false,
      hasStreak6Plus: false,
      hasPattern: false,
      half: halfLabel,
      seq,
    };
  }

  let maxStreak = 1;
  let curStreak = 1;
  let bestSymbol = seq[0];
  let curSymbol = seq[0];

  for (let i = 1; i < seq.length; i++) {
    if (seq[i] === seq[i - 1]) {
      curStreak += 1;
      curSymbol = seq[i];
      if (curStreak >= maxStreak) {
        maxStreak = curStreak;
        bestSymbol = curSymbol;
      }
    } else {
      curStreak = 1;
      curSymbol = seq[i];
    }
  }

  const tail4 = seq.slice(-4).join("-");
  const tail5 = seq.length >= 5 ? seq.slice(-5).join("-") : "";
  const tail6 = seq.length >= 6 ? seq.slice(-6).join("-") : "";

  let patternLabel = null;
  if (
    tail6 === "T-Ç-T-Ç-T-Ç" ||
    tail6 === "Ç-T-Ç-T-Ç-T" ||
    tail5 === "T-Ç-T-Ç-T" ||
    tail5 === "Ç-T-Ç-T-Ç" ||
    tail4 === "T-Ç-T-Ç" ||
    tail4 === "Ç-T-Ç-T"
  ) {
    patternLabel = `Alternatif (${tail4})`;
  } else if (
    tail6 === "T-T-Ç-Ç-T-T" ||
    tail6 === "Ç-Ç-T-T-Ç-Ç" ||
    tail4 === "T-T-Ç-Ç" ||
    tail4 === "Ç-Ç-T-T"
  ) {
    patternLabel = `İkili Blok (${tail4})`;
  }

  return {
    maxStreak,
    streakSymbol: bestSymbol,
    patternLabel,
    hasStreak5Plus: maxStreak >= 5,
    hasStreak6Plus: maxStreak >= 6,
    hasPattern: Boolean(patternLabel),
    half: halfLabel,
    seq,
  };
}

function mergeScope(iyFlag, msFlag) {
  if (iyFlag && msFlag) return "İY + MS";
  if (iyFlag) return "İY";
  if (msFlag) return "MS";
  return null;
}

function isMatchFinished(match, nowMs = Date.now()) {
  if (match.isManualTest) return false;
  if (match.status === "finished") return true;
  if (!match.date) return false;
  const parsed = new Date(String(match.date).replace(" ", "T"));
  if (Number.isNaN(parsed.getTime())) return false;
  const finishThresholdMs = parsed.getTime() + 115 * 60 * 1000;
  return nowMs >= finishThresholdMs;
}

function analyzeMatch(match, nowMs = Date.now()) {
  const parseList = (arr) =>
    (Array.isArray(arr) ? arr : [])
      .map(parseScoreToken)
      .filter(Boolean);

  const hParsed = parseList(match.homeMatches);
  const aParsed = parseList(match.awayMatches);
  const rParsed = parseList(match.refMatches);

  const hIySeq = hParsed.map((x) => toOddEven(x.iyH + x.iyA));
  const hMsSeq = hParsed.map((x) => toOddEven(x.msH + x.msA));
  const aIySeq = aParsed.map((x) => toOddEven(x.iyH + x.iyA));
  const aMsSeq = aParsed.map((x) => toOddEven(x.msH + x.msA));
  const rIySeq = rParsed.map((x) => toOddEven(x.iyH + x.iyA));
  const rMsSeq = rParsed.map((x) => toOddEven(x.msH + x.msA));

  const hIy = analyzeSequence(hIySeq, "İY");
  const hMs = analyzeSequence(hMsSeq, "MS");
  const aIy = analyzeSequence(aIySeq, "İY");
  const aMs = analyzeSequence(aMsSeq, "MS");
  const rIy = analyzeSequence(rIySeq, "İY");
  const rMs = analyzeSequence(rMsSeq, "MS");

  const streakIyHit = hIy.hasStreak5Plus || aIy.hasStreak5Plus || rIy.hasStreak5Plus;
  const streakMsHit = hMs.hasStreak5Plus || aMs.hasStreak5Plus || rMs.hasStreak5Plus;
  const hasRealSeries = streakIyHit || streakMsHit;
  const seriesScope = mergeScope(streakIyHit, streakMsHit);

  const patternIyHit = hIy.hasPattern || aIy.hasPattern || rIy.hasPattern;
  const patternMsHit = hMs.hasPattern || aMs.hasPattern || rMs.hasPattern;
  const hasRealPattern = patternIyHit || patternMsHit;
  const patternScope = mergeScope(patternIyHit, patternMsHit);

  const combinedScope = mergeScope(
    streakIyHit || patternIyHit,
    streakMsHit || patternMsHit
  );

  const iySeriesHit = hIy.hasStreak5Plus || aIy.hasStreak5Plus || rIy.hasStreak5Plus;
  const hasIySeries = iySeriesHit;

  const special6PlusItems = [];
  const push6Plus = (owner, half, res) => {
    if (res.hasStreak6Plus) {
      special6PlusItems.push(
        `${owner} [${half}]: ${res.maxStreak} maç üst üste ${res.streakSymbol}`
      );
    }
  };
  push6Plus(match.home, "İY", hIy);
  push6Plus(match.home, "MS", hMs);
  push6Plus(match.away, "İY", aIy);
  push6Plus(match.away, "MS", aMs);
  if (match.referee && match.referee !== "Bilinmiyor") {
    push6Plus(`Hakem (${match.referee})`, "İY", rIy);
    push6Plus(`Hakem (${match.referee})`, "MS", rMs);
  }

  const candidateScores = [
    { label: "0-0 (1-0)", weight: 34 },
    { label: "1-0 (2-1)", weight: 26 },
    { label: "0-0 (1-1)", weight: 22 },
    { label: "1-0 (1-1)", weight: 18 },
  ];

  if (hasRealPattern && patternScope === "İY") {
    candidateScores[0].weight += 8;
    candidateScores[2].weight += 6;
  }
  if (hasRealSeries && seriesScope === "MS") {
    candidateScores[1].weight += 9;
    candidateScores[3].weight += 5;
  }

  const totalWeight = candidateScores.reduce((acc, item) => acc + item.weight, 0);
  let runningPercent = 0;
  const probableScores = candidateScores.map((item, idx) => {
    if (idx === candidateScores.length - 1) {
      const remainder = Math.max(1, 100 - runningPercent);
      return { ...item, percent: remainder };
    }
    const pct = Math.max(1, Math.round((item.weight / totalWeight) * 100));
    runningPercent += pct;
    return { ...item, percent: pct };
  });

  const rules = [
    { id: "A.1", title: "Ev Sahibi İY Tek/Çift Seri Kontrolü", passed: hIy.hasStreak5Plus, detail: `En uzun seri: ${hIy.maxStreak}` },
    { id: "A.2", title: "Ev Sahibi MS Tek/Çift Seri Kontrolü", passed: hMs.hasStreak5Plus, detail: `En uzun seri: ${hMs.maxStreak}` },
    { id: "A.3", title: "Deplasman İY Tek/Çift Seri Kontrolü", passed: aIy.hasStreak5Plus, detail: `En uzun seri: ${aIy.maxStreak}` },
    { id: "A.4", title: "Deplasman MS Tek/Çift Seri Kontrolü", passed: aMs.hasStreak5Plus, detail: `En uzun seri: ${aMs.maxStreak}` },
    { id: "A.5", title: "Hakem İY/MS Tek/Çift Seri Kontrolü", passed: rIy.hasStreak5Plus || rMs.hasStreak5Plus, detail: `İY:${rIy.maxStreak} / MS:${rMs.maxStreak}` },
    { id: "B.1", title: "Ev Sahibi İY Örüntü Taraması", passed: hIy.hasPattern, detail: hIy.patternLabel || "Örüntü yok" },
    { id: "B.2", title: "Ev Sahibi MS Örüntü Taraması", passed: hMs.hasPattern, detail: hMs.patternLabel || "Örüntü yok" },
    { id: "B.3", title: "Deplasman İY Örüntü Taraması", passed: aIy.hasPattern, detail: aIy.patternLabel || "Örüntü yok" },
    { id: "B.4", title: "Deplasman MS Örüntü Taraması", passed: aMs.hasPattern, detail: aMs.patternLabel || "Örüntü yok" },
    { id: "B.5", title: "Hakem İY/MS Örüntü Taraması", passed: rIy.hasPattern || rMs.hasPattern, detail: rIy.patternLabel || rMs.patternLabel || "Örüntü yok" },
    { id: "C.5", title: "6+ Özel Seri Tespiti", passed: special6PlusItems.length > 0, detail: special6PlusItems.length > 0 ? `${special6PlusItems.length} adet 6+ seri` : "YOK" },
    { id: "C.6", title: "Örüntü + Seri Kesişimi", passed: hasRealSeries && hasRealPattern, detail: hasRealSeries && hasRealPattern ? "Seri ve Örüntü birlikte aktif" : "Kesişim yok" },
    { id: "C.7", title: "Olası Skor Dağılımı (%100 Normalize)", passed: true, detail: probableScores.map((s) => `%${s.percent} ${s.label}`).join(" • ") },
  ];

  const categories = [];
  if (hasRealSeries && hasRealPattern) {
    categories.push({ key: "combo", label: "⚡ ÖRÜNTÜ VE SERİ OLAN MAÇLAR", scope: combinedScope });
  }
  if (hasRealSeries) {
    categories.push({ key: "series", label: "🚨 YÜKSEK SERİ", scope: seriesScope });
  }
  if (hasRealPattern) {
    categories.push({ key: "pattern", label: "📣 DEVAM EDEN ÖRÜNTÜ", scope: patternScope });
  }
  if (hasIySeries) {
    categories.push({ key: "iySeries", label: "⏱️ İY SERİSİ OLANLAR", scope: "İY" });
  }

  const finished = isMatchFinished(match, nowMs);

  return {
    ...match,
    finished,
    hasRealSeries,
    hasRealPattern,
    hasIySeries,
    seriesScope,
    patternScope,
    combinedScope,
    special6PlusItems,
    probableScores,
    rules,
    categories,
    hIy,
    hMs,
    aIy,
    aMs,
  };
}

export default function TekCiftAnalizApp() {
  const [matches, setMatches] = useState(INITIAL_MATCHES);
  const [selectedLeague, setSelectedLeague] = useState("ALL");
  const [showFinished, setShowFinished] = useState(false);
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [showTestModal, setShowTestModal] = useState(false);
  const [showUrlModal, setShowUrlModal] = useState(false);
  const [jsonText, setJsonText] = useState("");
  const [jsonStatus, setJsonStatus] = useState("");

  const [liveUrl, setLiveUrl] = useState(() => {
    try {
      return localStorage.getItem("tekcift_live_url") || "";
    } catch {
      return "";
    }
  });
  const [autoDailyRefresh, setAutoDailyRefresh] = useState(() => {
    try {
      return localStorage.getItem("tekcift_auto_daily") !== "false";
    } catch {
      return true;
    }
  });
  const [lastSyncedAt, setLastSyncedAt] = useState("");
  const [syncMessage, setSyncMessage] = useState("");

  const [testForm, setTestForm] = useState({
    league: "Türkiye: Süper Lig",
    date: "2026-11-28 19:00",
    home: "Fenerbahçe",
    away: "Beşiktaş",
    referee: "Ali Şansalan",
    homeMatchesText: "1-0 (2-1), 0-1 (1-2), 1-0 (3-0), 0-1 (2-0), 1-0 (1-1), 0-1 (2-1)",
    awayMatchesText: "0-0 (1-1), 1-1 (2-2), 0-0 (0-0), 1-1 (1-0), 0-0 (2-1), 1-1 (1-2)",
    refMatchesText: "1-0 (2-1), 0-0 (1-0), 1-1 (2-2), 0-1 (1-2)",
  });

  const fetchLiveBulletin = useCallback(async (targetUrl) => {
    const cleanUrl = (targetUrl || "").trim();
    if (!cleanUrl) return;
    setSyncMessage("Bülten çekiliyor...");
    try {
      const sep = cleanUrl.includes("?") ? "&" : "?";
      const res = await fetch(`${cleanUrl}${sep}t=${Date.now()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!Array.isArray(data)) throw new Error("JSON bir liste olmalıdır");
      setMatches(data);
      const nowStr = new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
      setLastSyncedAt(nowStr);
      setSyncMessage(`Güncellendi (${data.length} maç)`);
      try {
        localStorage.setItem("tekcift_last_sync_date", new Date().toISOString().slice(0, 10));
      } catch {}
    } catch (err) {
      setSyncMessage(`Bağlantı uyarısı: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    if (!liveUrl) return;
    fetchLiveBulletin(liveUrl);
    if (!autoDailyRefresh) return;
    const interval = setInterval(() => {
      try {
        const today = new Date().toISOString().slice(0, 10);
        const lastDate = localStorage.getItem("tekcift_last_sync_date");
        if (lastDate !== today) {
          fetchLiveBulletin(liveUrl);
        }
      } catch {}
    }, 30 * 60 * 1000);
    return () => clearInterval(interval);
  }, [liveUrl, autoDailyRefresh, fetchLiveBulletin]);

  const analyzedMatches = useMemo(() => {
    const nowMs = Date.now();
    return matches.map((m) => analyzeMatch(m, nowMs));
  }, [matches]);

  const finishedMatches = useMemo(() => {
    return analyzedMatches.filter((m) => {
      if (!m.finished) return false;
      if (selectedLeague !== "ALL" && m.league !== selectedLeague) return false;
      return true;
    });
  }, [analyzedMatches, selectedLeague]);

  const activeMatches = useMemo(() => {
    return analyzedMatches.filter((m) => {
      if (m.finished) return false;
      if (selectedLeague !== "ALL" && m.league !== selectedLeague) return false;
      return m.categories.length > 0;
    });
  }, [analyzedMatches, selectedLeague]);

  const groupedActive = useMemo(() => {
    const groups = {
      combo: [],
      series: [],
      pattern: [],
      iySeries: [],
    };
    activeMatches.forEach((m) => {
      m.categories.forEach((cat) => {
        if (groups[cat.key]) {
          groups[cat.key].push({ match: m, scope: cat.scope });
        }
      });
    });
    return groups;
  }, [activeMatches]);

  const selectedMatch = useMemo(
    () => analyzedMatches.find((m) => m.id === selectedMatchId) || null,
    [analyzedMatches, selectedMatchId]
  );

  const handleJsonImport = () => {
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) {
        setJsonStatus("Hata: JSON kök yapısı bir dizi ([ ... ]) olmalıdır.");
        return;
      }
      const normalized = parsed.map((item, idx) => ({
        ...item,
        id: item.id || `imp-${Date.now()}-${idx}`,
        homeMatches: Array.isArray(item.homeMatches) ? item.homeMatches : [],
        awayMatches: Array.isArray(item.awayMatches) ? item.awayMatches : [],
        refMatches: Array.isArray(item.refMatches) ? item.refMatches : [],
      }));
      setMatches(normalized);
      setJsonStatus(`${normalized.length} maç başarıyla yüklendi.`);
      setShowJsonModal(false);
      setJsonText("");
    } catch (e) {
      setJsonStatus(`JSON Hatası: ${e.message}`);
    }
  };

  const handleCreateTestMatch = (e) => {
    e.preventDefault();
    const splitScores = (txt) =>
      txt
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

    const newTest = {
      id: `test-${Date.now()}`,
      country: testForm.league.split(":")[0] || "Özel",
      league: testForm.league,
      date: testForm.date,
      home: testForm.home.trim() || "Ev Sahibi",
      away: testForm.away.trim() || "Deplasman",
      referee: testForm.referee.trim() || "Bilinmiyor",
      status: "upcoming",
      finalScore: "",
      isManualTest: true,
      homeMatches: splitScores(testForm.homeMatchesText),
      awayMatches: splitScores(testForm.awayMatchesText),
      refMatches: splitScores(testForm.refMatchesText),
    };

    setMatches((prev) => [newTest, ...prev]);
    setSelectedMatchId(newTest.id);
    setShowTestModal(false);
  };

  const saveLiveUrlConfig = () => {
    try {
      localStorage.setItem("tekcift_live_url", liveUrl.trim());
      localStorage.setItem("tekcift_auto_daily", String(autoDailyRefresh));
    } catch {}
    if (liveUrl.trim()) {
      fetchLiveBulletin(liveUrl.trim());
    }
    setShowUrlModal(false);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0B0A10",
        color: "#F3E8FF",
        fontFamily: "system-ui, -apple-system, sans-serif",
        padding: "16px",
      }}
    >
      <div style={{ maxWidth: 1120, margin: "0 auto" }}>
        {/* Üst Başlık ve Kontrol Çubuğu */}
        <header
          style={{
            background: "linear-gradient(135deg, #151221 0%, #1E1932 100%)",
            border: "1px solid #3B2866",
            borderRadius: 16,
            padding: 16,
            marginBottom: 16,
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#E9D5FF" }}>
              TEK / ÇİFT ANALİZ MOTORU (25 LİG)
            </div>
            <div style={{ fontSize: 12, color: "#C4B5FD", marginTop: 4 }}>
              13 Kural (A.1–C.7) • 6+ Özel Seri • İY/MS Bağımsız Tarama
              {lastSyncedAt ? ` • Son Güncelleme: ${lastSyncedAt}` : ""}
            </div>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <button
              onClick={() => setShowFinished((prev) => !prev)}
              style={{
                background: showFinished ? "#2563EB" : "#1E1932",
                color: "#FFFFFF",
                border: "1px solid #4C1D95",
                borderRadius: 10,
                padding: "8px 12px",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              {showFinished ? "🏁 Biten Maçları Gizle" : "🏁 Biten Maçları Göster"} ({finishedMatches.length})
            </button>

            <button
              onClick={() => setShowUrlModal(true)}
              style={{
                background: "#2A1F46",
                color: "#F3E8FF",
                border: "1px solid #A855F7",
                borderRadius: 10,
                padding: "8px 12px",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              🌐 Canlı URL & Oto-Yenile
            </button>

            <button
              onClick={() => setShowJsonModal(true)}
              style={{
                background: "#1E1932",
                color: "#DDD6FE",
                border: "1px solid #4C1D95",
                borderRadius: 10,
                padding: "8px 12px",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              📥 Gerçek Bülten Yükle (JSON)
            </button>

            <button
              onClick={() => setShowTestModal(true)}
              style={{
                background: "#9333EA",
                color: "#FFFFFF",
                border: "none",
                borderRadius: 10,
                padding: "8px 12px",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              🧪 Kendi Maçını Test Et
            </button>
          </div>
        </header>

        {syncMessage && (
          <div
            style={{
              background: "#151221",
              border: "1px solid #3B2866",
              borderRadius: 10,
              padding: "8px 14px",
              marginBottom: 14,
              fontSize: 13,
              color: "#D8B4FE",
            }}
          >
            {syncMessage}
          </div>
        )}

        {/* Lig Filtresi */}
        <div
          style={{
            background: "#151221",
            border: "1px solid #2E234B",
            borderRadius: 14,
            padding: 12,
            marginBottom: 16,
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#C4B5FD" }}>Lig Seçimi:</span>
            <select
              value={selectedLeague}
              onChange={(e) => setSelectedLeague(e.target.value)}
              style={{
                background: "#0B0A10",
                color: "#F3E8FF",
                border: "1px solid #4C1D95",
                borderRadius: 8,
                padding: "7px 10px",
                fontSize: 13,
              }}
            >
              <option value="ALL">Tüm Ligler (25 Lig)</option>
              {LEAGUES.map((lg) => (
                <option key={lg} value={lg}>
                  {lg}
                </option>
              ))}
            </select>
          </div>
          <div style={{ fontSize: 12, color: "#A78BFA" }}>
            Aktif Sinyalli Maç: <strong>{activeMatches.length}</strong>
          </div>
        </div>

        {/* Biten Maçlar Ayrı Kategorisi */}
        {showFinished && (
          <section
            style={{
              background: "#151221",
              border: "1px solid #3B82F6",
              borderRadius: 16,
              padding: 16,
              marginBottom: 18,
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 800, color: "#93C5FD", marginBottom: 12 }}>
              🏁 BİTEN MAÇLAR ({finishedMatches.length})
            </div>
            {finishedMatches.length === 0 ? (
              <div style={{ fontSize: 13, color: "#A1A1AA" }}>Bu filtrede biten maç bulunmuyor.</div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
                {finishedMatches.map((m) => (
                  <div
                    key={m.id}
                    onClick={() => setSelectedMatchId(m.id)}
                    style={{
                      background: "#0B0A10",
                      border: "1px solid #27273A",
                      borderRadius: 12,
                      padding: 12,
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontSize: 11, color: "#93C5FD", fontWeight: 700 }}>
                      {m.league} • {m.date}
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 800, marginTop: 4 }}>
                      {m.home} vs {m.away}
                    </div>
                    <div
                      style={{
                        marginTop: 8,
                        padding: "6px 10px",
                        borderRadius: 8,
                        background: "#172554",
                        color: "#BFDBFE",
                        fontWeight: 700,
                        fontSize: 13,
                      }}
                    >
                      MAÇ SONUCU: {m.finalScore || "Tamamlandı"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* 4 Ana Kategori Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
          {[
            { key: "combo", title: "⚡ ÖRÜNTÜ VE SERİ OLAN MAÇLAR", accent: "#A855F7" },
            { key: "series", title: "🚨 YÜKSEK SERİ", accent: "#EC4899" },
            { key: "pattern", title: "📣 DEVAM EDEN ÖRÜNTÜ", accent: "#3B82F6" },
            { key: "iySeries", title: "⏱️ İY SERİSİ OLANLAR", accent: "#8B5CF6" },
          ].map((col) => {
            const items = groupedActive[col.key] || [];
            return (
              <div
                key={col.key}
                style={{
                  background: "#151221",
                  border: `1px solid ${col.accent}55`,
                  borderRadius: 16,
                  padding: 14,
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 800, color: "#F3E8FF", marginBottom: 10 }}>
                  {col.title} ({items.length})
                </div>

                {items.length === 0 ? (
                  <div style={{ fontSize: 12, color: "#9CA3AF", padding: "12px 0" }}>
                    Şu an bu kuralı karşılayan aktif maç yok.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {items.map(({ match: m, scope }) => (
                      <div
                        key={`${col.key}-${m.id}`}
                        onClick={() => setSelectedMatchId(m.id)}
                        style={{
                          background: "#0B0A10",
                          border: "1px solid #2E234B",
                          borderRadius: 12,
                          padding: 12,
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                          <span style={{ fontSize: 11, color: "#C4B5FD" }}>{m.league}</span>
                          {scope && (
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 800,
                                padding: "2px 7px",
                                borderRadius: 999,
                                background: "#2E1065",
                                color: "#E9D5FF",
                                border: "1px solid #9333EA",
                              }}
                            >
                              [{scope}]
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 800, marginTop: 4 }}>
                          {m.home} vs {m.away}
                        </div>
                        <div style={{ fontSize: 11, color: "#A1A1AA", marginTop: 2 }}>
                          {m.date} • Hakem: {m.referee || "Bilinmiyor"}
                        </div>
                        <div style={{ fontSize: 11, color: "#D8B4FE", marginTop: 6 }}>
                          6+ Özel Seri: {m.special6PlusItems.length > 0 ? m.special6PlusItems.join(" | ") : "YOK"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Seçili Maç Detay Paneli */}
        {selectedMatch && (
          <div
            style={{
              marginTop: 18,
              background: "#151221",
              border: "1px solid #A855F7",
              borderRadius: 16,
              padding: 16,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
              <div>
                <div style={{ fontSize: 12, color: "#C4B5FD" }}>
                  {selectedMatch.league} • {selectedMatch.date} • Hakem: {selectedMatch.referee}
                </div>
                <div style={{ fontSize: 18, fontWeight: 800, marginTop: 2 }}>
                  {selectedMatch.home} vs {selectedMatch.away}
                </div>
              </div>
              <button
                onClick={() => setSelectedMatchId(null)}
                style={{
                  background: "#27273A",
                  color: "#FFF",
                  border: "none",
                  borderRadius: 8,
                  padding: "6px 12px",
                  cursor: "pointer",
                  fontWeight: 700,
                }}
              >
                Kapat
              </button>
            </div>

            {selectedMatch.finished && selectedMatch.finalScore && (
              <div
                style={{
                  marginTop: 10,
                  padding: "8px 12px",
                  borderRadius: 10,
                  background: "#172554",
                  color: "#BFDBFE",
                  fontWeight: 700,
                  fontSize: 13,
                }}
              >
                Tamamlanan Skor: {selectedMatch.finalScore}
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#E9D5FF", marginBottom: 6 }}>
                Olası İY / MS Skor Dağılımı (%100)
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {selectedMatch.probableScores.map((sc) => (
                  <span
                    key={sc.label}
                    style={{
                      background: "#1E1932",
                      border: "1px solid #6D28D9",
                      borderRadius: 10,
                      padding: "6px 10px",
                      fontSize: 12,
                      fontWeight: 700,
                    }}
                  >
                    %{sc.percent} • {sc.label}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#E9D5FF", marginBottom: 6 }}>
                6+ Özel Seriler
              </div>
              <div style={{ fontSize: 12, color: "#D8B4FE" }}>
                {selectedMatch.special6PlusItems.length > 0
                  ? selectedMatch.special6PlusItems.join(" • ")
                  : "YOK (DEĞİŞKEN)"}
              </div>
            </div>

            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#E9D5FF", marginBottom: 8 }}>
                13 Kural Motoru (A.1 – C.7)
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
                {selectedMatch.rules.map((r) => (
                  <div
                    key={r.id}
                    style={{
                      background: "#0B0A10",
                      border: `1px solid ${r.passed ? "#7E22CE" : "#27273A"}`,
                      borderRadius: 10,
                      padding: 10,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ fontWeight: 800, color: r.passed ? "#E9D5FF" : "#9CA3AF" }}>
                      {r.id}: {r.passed ? "AKTİF" : "PASİF"}
                    </div>
                    <div style={{ marginTop: 2 }}>{r.title}</div>
                    <div style={{ fontSize: 11, color: "#A78BFA", marginTop: 4 }}>{r.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Canlı URL Modal */}
        {showUrlModal && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.75)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
              zIndex: 50,
            }}
          >
            <div
              style={{
                width: "100%",
                maxWidth: 520,
                background: "#151221",
                border: "1px solid #7E22CE",
                borderRadius: 16,
                padding: 18,
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 10 }}>
                🌐 Canlı Bülten URL & Günlük Oto-Yenile
              </div>
              <input
                type="text"
                placeholder="https://raw.githubusercontent.com/.../bulten.json"
                value={liveUrl}
                onChange={(e) => setLiveUrl(e.target.value)}
                style={{
                  width: "100%",
                  background: "#0B0A10",
                  color: "#FFF",
                  border: "1px solid #4C1D95",
                  borderRadius: 10,
                  padding: 10,
                  fontSize: 13,
                  marginBottom: 12,
                }}
              />
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 14 }}>
                <input
                  type="checkbox"
                  checked={autoDailyRefresh}
                  onChange={(e) => setAutoDailyRefresh(e.target.checked)}
                />
                Her gün otomatik kontrol edip yenile
              </label>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button
                  onClick={() => setShowUrlModal(false)}
                  style={{
                    background: "#27273A",
                    color: "#FFF",
                    border: "none",
                    borderRadius: 8,
                    padding: "8px 14px",
                    cursor: "pointer",
                  }}
                >
                  İptal
                </button>
                <button
                  onClick={saveLiveUrlConfig}
                  style={{
                    background: "#9333EA",
                    color: "#FFF",
                    border: "none",
                    borderRadius: 8,
                    padding: "8px 14px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Kaydet ve Çek
                </button>
              </div>
            </div>
          </div>
        )}

        {/* JSON Yükleme Modal */}
        {showJsonModal && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.75)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
              zIndex: 50,
            }}
          >
            <div
              style={{
                width: "100%",
                maxWidth: 560,
                background: "#151221",
                border: "1px solid #7E22CE",
                borderRadius: 16,
                padding: 18,
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 10 }}>
                📥 Gerçek Bülten Yükle (JSON)
              </div>
              <textarea
                rows={8}
                placeholder='[ { "league": "Türkiye: Süper Lig", "home": "...", "away": "...", "homeMatches": ["1-0 (2-1)"], "awayMatches": ["0-0 (1-1)"] } ]'
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                style={{
                  width: "100%",
                  background: "#0B0A10",
                  color: "#FFF",
                  border: "1px solid #4C1D95",
                  borderRadius: 10,
                  padding: 10,
                  fontSize: 12,
                  marginBottom: 8,
                }}
              />
              {jsonStatus && <div style={{ fontSize: 12, color: "#F87171", marginBottom: 8 }}>{jsonStatus}</div>}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button
                  onClick={() => setShowJsonModal(false)}
                  style={{
                    background: "#27273A",
                    color: "#FFF",
                    border: "none",
                    borderRadius: 8,
                    padding: "8px 14px",
                    cursor: "pointer",
                  }}
                >
                  Kapat
                </button>
                <button
                  onClick={handleJsonImport}
                  style={{
                    background: "#9333EA",
                    color: "#FFF",
                    border: "none",
                    borderRadius: 8,
                    padding: "8px 14px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Bülteni Yükle
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Kendi Maçını Test Et Modal */}
        {showTestModal && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.75)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
              zIndex: 50,
            }}
          >
            <form
              onSubmit={handleCreateTestMatch}
              style={{
                width: "100%",
                maxWidth: 540,
                background: "#151221",
                border: "1px solid #7E22CE",
                borderRadius: 16,
                padding: 18,
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 800 }}>🧪 Kendi Maçını Test Et</div>
              <select
                value={testForm.league}
                onChange={(e) => setTestForm({ ...testForm, league: e.target.value })}
                style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
              >
                {LEAGUES.map((lg) => (
                  <option key={lg} value={lg}>
                    {lg}
                  </option>
                ))}
              </select>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <input
                  type="text"
                  placeholder="Ev Sahibi"
                  value={testForm.home}
                  onChange={(e) => setTestForm({ ...testForm, home: e.target.value })}
                  style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
                />
                <input
                  type="text"
                  placeholder="Deplasman"
                  value={testForm.away}
                  onChange={(e) => setTestForm({ ...testForm, away: e.target.value })}
                  style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <input
                  type="text"
                  placeholder="Tarih Saat (YYYY-MM-DD HH:MM)"
                  value={testForm.date}
                  onChange={(e) => setTestForm({ ...testForm, date: e.target.value })}
                  style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
                />
                <input
                  type="text"
                  placeholder="Hakem"
                  value={testForm.referee}
                  onChange={(e) => setTestForm({ ...testForm, referee: e.target.value })}
                  style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
                />
              </div>
              <input
                type="text"
                placeholder="Ev Sahibi Son Maçlar (ör: 1-0 (2-1), 0-1 (1-2))"
                value={testForm.homeMatchesText}
                onChange={(e) => setTestForm({ ...testForm, homeMatchesText: e.target.value })}
                style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
              />
              <input
                type="text"
                placeholder="Deplasman Son Maçlar"
                value={testForm.awayMatchesText}
                onChange={(e) => setTestForm({ ...testForm, awayMatchesText: e.target.value })}
                style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
              />
              <input
                type="text"
                placeholder="Hakem Son Maçlar"
                value={testForm.refMatchesText}
                onChange={(e) => setTestForm({ ...testForm, refMatchesText: e.target.value })}
                style={{ background: "#0B0A10", color: "#FFF", border: "1px solid #4C1D95", borderRadius: 8, padding: 8 }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
                <button
                  type="button"
                  onClick={() => setShowTestModal(false)}
                  style={{ background: "#27273A", color: "#FFF", border: "none", borderRadius: 8, padding: "8px 14px", cursor: "pointer" }}
                >
                  İptal
                </button>
                <button
                  type="submit"
                  style={{ background: "#9333EA", color: "#FFF", border: "none", borderRadius: 8, padding: "8px 14px", fontWeight: 700, cursor: "pointer" }}
                >
                  Analiz Et
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
