import { useRef, useState, useEffect } from "react";
import { useStore, formatInr, type AIKeyFinding, type AIRecommendation, type CategoryBreakdown } from "../store/useStore";

/* ── Animated Health Score Ring ──────────────────────────────────────────── */
function HealthRing({ score, size = 160 }: { score: number; size?: number }) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;

  useEffect(() => {
    let frame: number;
    const duration = 1200;
    const start = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedScore(Math.round(score * eased));
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const color =
    score >= 70 ? "#10b981" : score >= 40 ? "#f59e0b" : "#ef4444";
  const bgColor =
    score >= 70 ? "#d1fae5" : score >= 40 ? "#fef3c7" : "#fee2e2";
  const label =
    score >= 70 ? "Healthy" : score >= 40 ? "Needs Attention" : "Critical";

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={bgColor} strokeWidth="10" />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-extrabold" style={{ color }}>{animatedScore}</span>
        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">{label}</span>
      </div>
    </div>
  );
}

/* ── Audio Player with Language Toggle ──────────────────────────────────── */
function DualAudioPlayer({
  audioHi, audioEn, isHindi,
}: {
  audioHi: string | null;
  audioEn: string | null;
  isHindi: boolean;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [audioLang, setAudioLang] = useState<"hi" | "en">(isHindi ? "hi" : "en");

  const currentBase64 = audioLang === "hi" ? audioHi : audioEn;
  const audioSrc = currentBase64 ? `data:audio/mp3;base64,${currentBase64}` : null;

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio || !audioSrc) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  };

  const switchLang = (lang: "hi" | "en") => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsPlaying(false);
    setProgress(0);
    setAudioLang(lang);
  };

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTimeUpdate = () => {
      if (audio.duration) setProgress((audio.currentTime / audio.duration) * 100);
    };
    const onEnded = () => { setIsPlaying(false); setProgress(0); };
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("ended", onEnded);
    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("ended", onEnded);
    };
  }, [audioLang]);

  const bars = Array.from({ length: 24 }, (_, i) => i);

  const hasHi = !!audioHi;
  const hasEn = !!audioEn;

  if (!hasHi && !hasEn) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 flex items-center justify-center h-full">
        <p className="text-sm text-slate-400">
          {isHindi ? "ऑडियो उपलब्ध नहीं है।" : "Audio not available."}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-gradient-to-r sky-50 p-5 shadow-sm">
      {audioSrc && <audio ref={audioRef} src={audioSrc} preload="auto" key={audioLang} />}

      {/* Header with language toggle */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-sky-500 animate-pulse" />
          <p className="text-xs font-bold uppercase tracking-wider text-slate-800">
            🔊 {isHindi ? "AI ऑडियो समरी" : "AI Audio Summary"}
          </p>
        </div>
        {/* Language Toggle */}
        <div className="flex rounded-full bg-white border border-slate-200 p-0.5 shadow-sm">
          <button
            onClick={() => switchLang("hi")}
            disabled={!hasHi}
            className={`rounded-full px-3 py-1 text-[11px] font-semibold transition ${
              audioLang === "hi"
                ? "bg-sky-500 text-white shadow"
                : "text-slate-500 hover:text-slate-900 disabled:opacity-30"
            }`}
          >
            🇮🇳 हिंदी
          </button>
          <button
            onClick={() => switchLang("en")}
            disabled={!hasEn}
            className={`rounded-full px-3 py-1 text-[11px] font-semibold transition ${
              audioLang === "en"
                ? "bg-sky-500 text-white shadow"
                : "text-slate-500 hover:text-slate-900 disabled:opacity-30"
            }`}
          >
            🇬🇧 English
          </button>
        </div>
      </div>

      {/* Waveform Visualization */}
      <div className="flex items-end justify-center gap-[3px] h-12 mb-4">
        {bars.map((i) => {
          const baseHeight = 12 + Math.sin(i * 0.7) * 8 + Math.cos(i * 1.3) * 6;
          const height = isPlaying
            ? baseHeight + Math.sin(Date.now() / 200 + i * 0.5) * 10
            : baseHeight * 0.4;
          return (
            <div
              key={i}
              className="rounded-full w-[4px] transition-all duration-150"
              style={{
                height: `${Math.max(4, height)}px`,
                backgroundColor: i / bars.length * 100 < progress
                  ? "#6366f1"
                  : isPlaying ? "#a5b4fc" : "#c7d2fe",
              }}
            />
          );
        })}
      </div>

      {/* Progress Bar */}
      <div className="h-1.5 rounded-full bg-slate-100 mb-3 overflow-hidden">
        <div
          className="h-full rounded-full bg-sky-500 transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Play/Pause Button */}
      <button
        onClick={togglePlay}
        disabled={!audioSrc}
        className="w-full rounded-xl bg-sky-500 py-2.5 text-sm font-semibold text-white shadow hover:bg-sky-600 transition flex items-center justify-center gap-2 disabled:opacity-50"
      >
        {isPlaying ? (
          <>⏸ {isHindi ? "रोकें" : "Pause"}</>
        ) : (
          <>▶ {audioLang === "hi" ? "हिंदी में सुनें" : "Play in English"}</>
        )}
      </button>
    </div>
  );
}

/* ── Category Bar Chart ─────────────────────────────────────────────────── */
function CategoryChart({ data, isHindi }: { data: CategoryBreakdown[]; isHindi: boolean }) {
  if (!data || data.length === 0) return null;
  const maxPct = Math.max(...data.map(d => d.percentage), 1);

  const colors = [
    "bg-emerald-500", "bg-sky-500", "bg-violet-500", "bg-amber-500",
    "bg-rose-500", "bg-sky-500", "bg-sky-500", "bg-pink-500",
  ];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <span className="w-2 h-2 rounded-full bg-emerald-500" />
        <p className="text-xs font-bold uppercase tracking-wider text-slate-800">
          {isHindi ? "📊 कैटेगरी विश्लेषण" : "📊 Category Breakdown"}
        </p>
      </div>
      <div className="space-y-3">
        {data.map((cat, idx) => (
          <div key={cat.name}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-slate-800 capitalize">{cat.name}</span>
              <span className="text-slate-500">₹{cat.amount} · {cat.percentage}%</span>
            </div>
            <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${colors[idx % colors.length]}`}
                style={{ width: `${(cat.percentage / maxPct) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Finding Card ───────────────────────────────────────────────────────── */
function FindingCard({ finding, isHindi, delay }: { finding: AIKeyFinding; isHindi: boolean; delay: number }) {
  const typeStyles = {
    positive: "border-emerald-200 bg-emerald-50/80",
    warning: "border-amber-200 bg-amber-50/80",
    critical: "border-red-200 bg-red-50/80",
    neutral: "border-slate-200 bg-slate-50/80",
  };
  const dotColors = {
    positive: "bg-emerald-500",
    warning: "bg-amber-500",
    critical: "bg-red-500",
    neutral: "bg-slate-400",
  };

  return (
    <div
      className={`rounded-2xl border p-4 shadow-sm transition hover:shadow-md ${typeStyles[finding.type]}`}
      style={{ animation: `fadeInUp 0.5s ease-out ${delay}ms both` }}
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl">{finding.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-1.5 h-1.5 rounded-full ${dotColors[finding.type]}`} />
            <p className="text-sm font-bold text-slate-800">
              {isHindi ? finding.title_hi : finding.title_en}
            </p>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            {isHindi ? finding.description_hi : finding.description_en}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Recommendation Item ────────────────────────────────────────────────── */
function RecommendationItem({ rec, index, isHindi }: { rec: AIRecommendation; index: number; isHindi: boolean }) {
  const priorityBadge = {
    high: "bg-red-100 text-red-700",
    medium: "bg-amber-100 text-amber-700",
    low: "bg-slate-100 text-slate-600",
  };

  return (
    <div
      className="flex items-start gap-3 rounded-xl border border-slate-100 bg-white p-4 shadow-sm hover:shadow-md transition"
      style={{ animation: `fadeInUp 0.5s ease-out ${index * 100 + 300}ms both` }}
    >
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
        {index + 1}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-800 leading-relaxed">
          {isHindi ? rec.text_hi : rec.text_en}
        </p>
      </div>
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${priorityBadge[rec.priority]}`}>
        {rec.priority}
      </span>
    </div>
  );
}

/* ── Loading Skeleton ───────────────────────────────────────────────────── */
function LoadingSkeleton({ phase }: { phase: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="relative">
        <div className="w-20 h-20 rounded-full border-4 border-slate-200 animate-ping absolute inset-0 opacity-30" />
        <div className="w-20 h-20 rounded-full border-4 border-t-sky-500 border-r-sky-300 border-b-sky-100 border-l-transparent animate-spin" />
      </div>
      <p className="mt-6 text-sm font-semibold text-slate-600 animate-pulse">{phase}</p>
      <div className="mt-3 flex gap-1">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-sky-400"
            style={{ animation: `bounce 1s ease-in-out ${i * 0.15}s infinite` }}
          />
        ))}
      </div>
    </div>
  );
}

/* ── Main Insights Page ──────────────────────────────────────────────────── */
export default function Insights() {
  const { aiInsights, aiInsightsPhase, runAIInsights, loading, language } = useStore();
  const isHindi = language === "hi";
  const isLoading = loading.aiInsights;

  return (
    <div className="flex flex-col gap-6 flex-1">
      {/* CSS Animations */}
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-8px); }
        }
      `}</style>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-cyan-500 text-sm text-white shadow">✦</span>
              {isHindi ? "AI बिज़नेस सलाहकार" : "AI Business Advisor"}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {isHindi
                ? "आपके डेटा का गहरा विश्लेषण — हिंदी और अंग्रेज़ी, दोनों में टेक्स्ट और ऑडियो।"
                : "Deep analysis of your business data — text & audio in both Hindi and English."}
            </p>
          </div>
          <button
            type="button"
            onClick={runAIInsights}
            disabled={isLoading}
            className="rounded-full bg-gradient-to-r from-sky-500 to-cyan-500 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:shadow-xl hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {isHindi ? "विश्लेषण हो रहा है..." : "Analyzing..."}
              </>
            ) : (
              <>🧠 {isHindi ? "विश्लेषण शुरू करें" : "Generate Analysis"}</>
            )}
          </button>
        </div>
      </div>

      {/* ── Loading State ───────────────────────────────────────────────── */}
      {isLoading && <LoadingSkeleton phase={aiInsightsPhase} />}

      {/* ── Results ─────────────────────────────────────────────────────── */}
      {!isLoading && aiInsights && (
        <>
          {/* Row 1: Health Score + Audio Player */}
          <div className="grid gap-5 md:grid-cols-2">
            {/* Health Score */}
            <div
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col items-center justify-center"
              style={{ animation: "fadeInUp 0.5s ease-out 0ms both" }}
            >
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4">
                {isHindi ? "🏥 बिज़नेस स्वास्थ्य स्कोर" : "🏥 Business Health Score"}
              </p>
              <HealthRing score={aiInsights.health_score} />
              <div className="mt-4 grid grid-cols-3 gap-3 w-full">
                {[
                  {
                    label: isHindi ? "कुल आय" : "Income",
                    value: `₹${aiInsights.metrics.total_income ?? 0}`,
                    color: "text-emerald-600",
                  },
                  {
                    label: isHindi ? "कुल खर्च" : "Expense",
                    value: `₹${aiInsights.metrics.total_expense ?? 0}`,
                    color: "text-rose-600",
                  },
                  {
                    label: isHindi ? "शुद्ध लाभ" : "Net Profit",
                    value: `₹${aiInsights.metrics.net_profit ?? 0}`,
                    color: "text-slate-900",
                  },
                ].map((m) => (
                  <div key={m.label} className="text-center">
                    <p className="text-[10px] text-slate-400 font-semibold uppercase">{m.label}</p>
                    <p className={`text-sm font-bold ${m.color}`}>{m.value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Audio Player + Narrative */}
            <div style={{ animation: "fadeInUp 0.5s ease-out 100ms both" }} className="flex flex-col gap-5">
              <DualAudioPlayer
                audioHi={aiInsights.audio_hi_base64}
                audioEn={aiInsights.audio_en_base64}
                isHindi={isHindi}
              />

              {/* Narrative Text */}
              <div className="rounded-2xl border border-sky-100 bg-gradient-to-br from-white to-sky-50/50 p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-3">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-md bg-sky-500 text-[10px] text-white font-bold animate-pulse">AI</span>
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-800">
                    {isHindi ? "सारांश" : "Summary"}
                  </p>
                </div>
                <p className="text-sm font-medium text-slate-800 leading-relaxed">
                  {isHindi ? aiInsights.narrative_hi : aiInsights.narrative_en}
                </p>
              </div>
            </div>
          </div>

          {/* Row 2: Key Findings */}
          {aiInsights.key_findings.length > 0 && (
            <div>
              <h3 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
                <span className="text-base">🔍</span>
                {isHindi ? "मुख्य निष्कर्ष" : "Key Findings"}
              </h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {aiInsights.key_findings.map((finding, idx) => (
                  <FindingCard key={idx} finding={finding} isHindi={isHindi} delay={idx * 80} />
                ))}
              </div>
            </div>
          )}

          {/* Row 3: Category Breakdown + Recommendations */}
          <div className="grid gap-5 lg:grid-cols-2">
            <div style={{ animation: "fadeInUp 0.5s ease-out 200ms both" }}>
              <CategoryChart data={aiInsights.category_breakdown} isHindi={isHindi} />
            </div>

            {aiInsights.recommendations.length > 0 && (
              <div>
                <h3 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
                  <span className="text-base">💡</span>
                  {isHindi ? "सुझाव और कार्रवाई" : "Recommendations"}
                </h3>
                <div className="space-y-2">
                  {aiInsights.recommendations.map((rec, idx) => (
                    <RecommendationItem key={idx} rec={rec} index={idx} isHindi={isHindi} />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Row 4: Metrics Footer */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" style={{ animation: "fadeInUp 0.5s ease-out 400ms both" }}>
            {[
              {
                label: isHindi ? "दैनिक औसत लाभ" : "Avg Daily Profit",
                value: `₹${aiInsights.metrics.avg_daily_profit ?? 0}`,
                bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500",
              },
              {
                label: isHindi ? "सबसे अच्छा दिन" : "Best Day of Week",
                value: `${aiInsights.metrics.best_day_of_week ?? "N/A"}`,
                bg: "bg-sky-50", text: "text-sky-700", dot: "bg-sky-500",
              },
              {
                label: isHindi ? "खर्चा अनुपात" : "Expense Ratio",
                value: `${aiInsights.metrics.expense_ratio ?? 0}%`,
                bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500",
              },
              {
                label: isHindi ? "ट्रेंड" : "Business Trend",
                value: `${aiInsights.metrics.trend ?? "stable"}`,
                bg: "bg-violet-50", text: "text-violet-700", dot: "bg-violet-500",
              },
            ].map((m) => (
              <div key={m.label} className={`rounded-2xl border border-slate-200 ${m.bg} p-4 shadow-sm`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{m.label}</p>
                </div>
                <p className={`text-lg font-bold ${m.text} capitalize`}>{m.value}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Empty State ─────────────────────────────────────────────────── */}
      {!isLoading && !aiInsights && (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 shadow text-center">
          <div className="text-5xl mb-4">🧠</div>
          <p className="font-bold text-slate-800 text-base">
            {isHindi ? "अभी तक कोई विश्लेषण नहीं" : "No analysis yet"}
          </p>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            {isHindi
              ? "ऊपर \"विश्लेषण शुरू करें\" बटन दबाएं। AI आपके बिज़नेस डेटा का गहरा विश्लेषण करेगा और हिंदी व अंग्रेज़ी दोनों में ऑडियो में सुनाएगा।"
              : "Click \"Generate Analysis\" above. AI will deeply analyze your business data and narrate it in both Hindi and English audio."}
          </p>
          <button
            onClick={runAIInsights}
            disabled={isLoading}
            className="mt-6 rounded-full bg-gradient-to-r from-sky-500 to-cyan-500 px-8 py-3 text-sm font-bold text-white shadow-sm hover:shadow-xl hover:brightness-110 transition"
          >
            🧠 {isHindi ? "AI विश्लेषण शुरू करें" : "Start AI Analysis"}
          </button>
        </div>
      )}
    </div>
  );
}
