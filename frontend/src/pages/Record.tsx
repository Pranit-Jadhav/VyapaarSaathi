import { useMemo, useRef, useEffect, useState } from "react";
import { useStore, formatInr } from "../store/useStore";

/* ── Counter Question Audio Player ──────────────────────────────────────── */
function CounterAudioPlayer({ base64, label }: { base64: string; label: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const audioSrc = `data:audio/mp3;base64,${base64}`;

  useEffect(() => {
    // Auto-play the counter question
    const timer = setTimeout(() => {
      audioRef.current?.play().then(() => setIsPlaying(true)).catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [base64]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onEnded = () => setIsPlaying(false);
    audio.addEventListener("ended", onEnded);
    return () => audio.removeEventListener("ended", onEnded);
  }, []);

  return (
    <div className="flex items-center gap-3 mt-2">
      <audio ref={audioRef} src={audioSrc} preload="auto" />
      <button
        onClick={() => {
          if (isPlaying) {
            audioRef.current?.pause();
            setIsPlaying(false);
          } else {
            audioRef.current?.play();
            setIsPlaying(true);
          }
        }}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-500 text-white text-xs hover:bg-indigo-600 transition"
      >
        {isPlaying ? "⏸" : "▶"}
      </button>
      <span className="text-[10px] font-bold uppercase text-indigo-400 tracking-wider">{label}</span>
      {isPlaying && (
        <div className="flex items-center gap-[2px]">
          {[0, 1, 2, 3, 4].map(i => (
            <div
              key={i}
              className="w-1 bg-indigo-400 rounded-full"
              style={{
                height: `${8 + Math.sin(Date.now() / 200 + i) * 6}px`,
                animation: `pulse 0.6s ease-in-out ${i * 0.1}s infinite alternate`,
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Main Record Page ───────────────────────────────────────────────────── */
export default function Record() {
  const {
    startRecording, stopRecording, isRecording, recordStatus, summary, language,
    pendingEntry, counterQuestion, counterAudioHi, counterAudioEn,
    conversationMode, cancelPending,
  } = useStore();
  const isHindi = language === "hi";
  
  const netProfit = useMemo(() => summary.earned - summary.spent, [summary.earned, summary.spent]);
  const isAnswering = conversationMode === "answering";

  const reasonLabels: Record<string, { hi: string; en: string }> = {
    NEEDS_QUANTITY: { hi: "📊 मात्रा बताइए", en: "📊 Tell the quantity" },
    NEEDS_AMOUNT: { hi: "💰 रकम बताइए", en: "💰 Tell the amount" },
    NEEDS_BOTH: { hi: "📊💰 मात्रा और रकम बताइए", en: "📊💰 Tell quantity & amount" },
    NEW_ITEM: { hi: "📦 नया आइटम — कीमत बताइए", en: "📦 New item — tell price" },
    NEW_ITEM_SALE: { hi: "🛒 कितने बेचे?", en: "🛒 How many sold?" },
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* CSS for counter question pulse */}
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          from { transform: scaleY(0.6); }
          to { transform: scaleY(1.4); }
        }
      `}</style>

      <section className="flex flex-col gap-4">
        {/* ── Counter Question Card (visible when pending) ─────────────── */}
        {isAnswering && counterQuestion && (
          <div
            className="rounded-3xl border-2 border-indigo-300 bg-gradient-to-br from-indigo-50 via-violet-50 to-purple-50 p-6 shadow-lg"
            style={{ animation: "fadeInUp 0.4s ease-out" }}
          >
            {/* Badge */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-indigo-500 text-xs text-white font-bold animate-pulse">AI</span>
                <span className="text-xs font-bold uppercase text-indigo-700 tracking-wider">
                  {pendingEntry
                    ? (isHindi ? reasonLabels[pendingEntry.reason]?.hi : reasonLabels[pendingEntry.reason]?.en) || "Follow-up"
                    : "Follow-up"}
                </span>
              </div>
              {pendingEntry && (
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-600 uppercase">
                  {pendingEntry.category}
                </span>
              )}
            </div>

            {/* Question text */}
            <p className="text-sm font-semibold text-slate-800 leading-relaxed">
              {isHindi ? counterQuestion.hi : counterQuestion.en}
            </p>

            {/* Audio playback */}
            {counterAudioHi && isHindi && (
              <CounterAudioPlayer base64={counterAudioHi} label="🔊 Hindi" />
            )}
            {counterAudioEn && !isHindi && (
              <CounterAudioPlayer base64={counterAudioEn} label="🔊 English" />
            )}
            {/* Show other language option */}
            {counterAudioEn && isHindi && (
              <CounterAudioPlayer base64={counterAudioEn} label="🔊 English" />
            )}
            {counterAudioHi && !isHindi && (
              <CounterAudioPlayer base64={counterAudioHi} label="🔊 हिंदी" />
            )}

            {/* Cancel button */}
            <button
              onClick={cancelPending}
              className="mt-4 w-full rounded-xl border border-slate-200 bg-white py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50 transition"
            >
              {isHindi ? "✕ रद्द करें" : "✕ Cancel"}
            </button>
          </div>
        )}

        {/* ── Recording Card ──────────────────────────────────────────── */}
        <div className="rounded-3xl border border-slate-200 bg-white/80 p-8 shadow-lg flex-1 flex flex-col justify-center items-center">
          <div className="w-full max-w-sm">
            <div className="flex items-center justify-between mb-8">
              <p className="text-lg font-bold text-slate-800">
                {isAnswering
                  ? (isHindi ? "जवाब रिकॉर्ड करें" : "Record Answer")
                  : (isHindi ? "ध्वनि प्रविष्टि" : "Voice Entry")}
              </p>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                isAnswering
                  ? "bg-indigo-100 text-indigo-700"
                  : "bg-slate-100 text-slate-500"
              }`}>
                {isAnswering
                  ? (isHindi ? "जवाब मोड" : "Answer Mode")
                  : (isHindi ? "AI प्रोसेसिंग" : "AI Processing")}
              </span>
            </div>
            
            <button
              type="button"
              onClick={startRecording}
              disabled={isRecording}
              className={`w-full rounded-3xl py-6 text-lg font-bold shadow-lg transition duration-300 ${
                isRecording
                  ? "bg-rose-500 text-white animate-pulse shadow-rose-200" 
                  : isAnswering
                    ? "bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-xl hover:-translate-y-1"
                    : "bg-slate-900 text-white hover:bg-slate-800 hover:shadow-xl hover:-translate-y-1"
              } disabled:opacity-60 disabled:hover:translate-y-0`}
            >
              {isRecording
                ? (isHindi ? "रिकॉर्डिंग..." : "Recording...")
                : isAnswering
                  ? (isHindi ? "🎤 जवाब रिकॉर्ड करें" : "🎤 Record Your Answer")
                  : (isHindi ? "रिकॉर्डिंग शुरू करें" : "Start Recording")}
            </button>
            
            <button
              type="button"
              onClick={stopRecording}
              disabled={!isRecording}
              className="mt-4 w-full rounded-2xl border-2 border-slate-200 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
            >
              {isHindi ? "रिकॉर्डिंग रोकें" : "Stop Recording"}
            </button>
            
            <p className={`mt-6 text-center text-sm bg-slate-50 rounded-xl py-3 border border-slate-100 ${
              recordStatus.includes("✅") ? "text-emerald-600 font-semibold" : "text-slate-500"
            }`}>
              {recordStatus}
            </p>
          </div>
        </div>
      </section>

      {/* ── Results Section ──────────────────────────────────────────── */}
      <section className="rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-lg">
        <h2 className="text-xl font-bold text-slate-800">{isHindi ? "नवीनतम ऑडियो परिणाम" : "Latest Audio Result"}</h2>
        <p className="text-xs text-slate-500">{isHindi ? "ऑटो-एक्सट्रेक्ट किए गए कुल और अनुवाद" : "Auto-extracted totals and translation"}</p>
        
        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/80 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400 mb-2">{isHindi ? "ट्रांसक्रिप्ट" : "Transcript"}</p>
          <p className="text-sm leading-relaxed text-slate-700 font-medium italic">
            {isHindi && summary.transcript === "No recording yet" ? '"अभी तक कोई रिकॉर्डिंग नहीं"' : `"${summary.transcript}"`}
          </p>
        </div>
        
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-emerald-50/50 p-5">
            <p className="text-xs font-semibold text-emerald-600/70 uppercase tracking-widest">{isHindi ? "आय" : "Earned"}</p>
            <p className="mt-1 text-2xl font-bold text-emerald-700">{formatInr(summary.earned)}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-rose-50/50 p-5">
            <p className="text-xs font-semibold text-rose-600/70 uppercase tracking-widest">{isHindi ? "व्यय" : "Spent"}</p>
            <p className="mt-1 text-2xl font-bold text-rose-700">{formatInr(summary.spent)}</p>
          </div>
        </div>
        
        <div className="mt-4 rounded-2xl bg-slate-900 p-5 text-white flex justify-between items-center shadow-md">
          <span className="text-sm font-semibold opacity-80 uppercase tracking-wider">{isHindi ? "शुद्ध लाभ" : "Net Profit"}</span>
          <span className={`text-2xl font-black ${netProfit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {formatInr(netProfit)}
          </span>
        </div>
      </section>
    </div>
  );
}
