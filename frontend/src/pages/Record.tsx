import { useRef, useEffect, useState } from "react";
import { useStore } from "../store/useStore";

/* ── Counter Question Audio Player ──────────────────────────────────────── */
function CounterAudioPlayer({ base64, label }: { base64: string; label: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
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
      <audio ref={audioRef} src={`data:audio/mp3;base64,${base64}`} preload="auto" />
      <button
        onClick={() => {
          if (isPlaying) { audioRef.current?.pause(); setIsPlaying(false); }
          else { audioRef.current?.play(); setIsPlaying(true); }
        }}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-500 text-white text-xs hover:bg-sky-600 transition"
      >
        {isPlaying ? "⏸" : "▶"}
      </button>
      <span className="text-[10px] font-bold uppercase text-sky-500 tracking-wider">{label}</span>
    </div>
  );
}

/* ── Main Record Page ────────────────────────────────────────────────────── */
export default function Record() {
  const {
    startRecording, stopRecording, isRecording, recordStatus, language,
    pendingEntry, counterQuestion, counterAudioHi, counterAudioEn,
    conversationMode, cancelPending,
  } = useStore();
  const isHindi = language === "hi";
  const isAnswering = conversationMode === "answering";

  const reasonLabels: Record<string, { hi: string; en: string }> = {
    NEEDS_QUANTITY: { hi: "📊 मात्रा बताइए", en: "📊 Tell the quantity" },
    NEEDS_AMOUNT:   { hi: "💰 रकम बताइए",   en: "💰 Tell the amount" },
    NEEDS_BOTH:     { hi: "📊💰 मात्रा और रकम", en: "📊💰 Quantity & amount" },
    NEW_ITEM:       { hi: "📦 नया आइटम — कीमत", en: "📦 New item — tell price" },
    NEW_ITEM_SALE:  { hi: "🛒 कितने बेचे?", en: "🛒 How many sold?" },
  };

  return (
    <div className="flex flex-col gap-5">
      <style>{`
        @keyframes fadeInUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      {/* ── AI Counter Question Card ───────────────────────────────────── */}
      {isAnswering && counterQuestion && (
        <div
          className="rounded-2xl border border-sky-200 bg-sky-50 p-6"
          style={{ animation: "fadeInUp 0.3s ease-out" }}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-5 w-5 items-center justify-center rounded bg-sky-500 text-[10px] text-white font-bold">AI</span>
              <span className="text-xs font-bold uppercase text-sky-700 tracking-wider">
                {pendingEntry
                  ? (isHindi ? reasonLabels[pendingEntry.reason]?.hi : reasonLabels[pendingEntry.reason]?.en) || "Follow-up"
                  : "Follow-up"}
              </span>
            </div>
            {pendingEntry && (
              <span className="rounded-full bg-white border border-sky-200 px-2 py-0.5 text-[10px] font-bold text-sky-600 uppercase">
                {pendingEntry.category}
              </span>
            )}
          </div>
          <p className="text-sm font-semibold text-slate-800 leading-relaxed">
            {isHindi ? counterQuestion.hi : counterQuestion.en}
          </p>
          {counterAudioHi && isHindi && <CounterAudioPlayer base64={counterAudioHi} label="🔊 Hindi" />}
          {counterAudioEn && !isHindi && <CounterAudioPlayer base64={counterAudioEn} label="🔊 English" />}
          {counterAudioEn && isHindi && <CounterAudioPlayer base64={counterAudioEn} label="🔊 English" />}
          {counterAudioHi && !isHindi && <CounterAudioPlayer base64={counterAudioHi} label="🔊 हिंदी" />}
          <button
            onClick={cancelPending}
            className="mt-4 w-full rounded-xl border border-sky-200 bg-white py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50 transition"
          >
            {isHindi ? "✕ रद्द करें" : "✕ Cancel"}
          </button>
        </div>
      )}

      {/* ── Recording Card ─────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-sky-100 bg-white p-10 flex flex-col items-center justify-center gap-8 min-h-[480px]">
        {/* Icon */}
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-sky-100 border-2 border-sky-200">
          <span className="text-4xl">{isRecording ? "⏺" : "🎤"}</span>
        </div>

        {/* Title */}
        <div className="text-center">
          <p className="text-2xl font-bold text-slate-900">
            {isAnswering
              ? (isHindi ? "जवाब रिकॉर्ड करें" : "Record Your Answer")
              : (isHindi ? "ध्वनि प्रविष्टि" : "Voice Entry")}
          </p>
          <p className="text-sm text-slate-400 mt-1">
            {isAnswering
              ? (isHindi ? "AI का जवाब दें" : "Reply to the AI question")
              : (isHindi ? "बोलिए, AI समझेगा और दर्ज करेगा" : "Speak — AI understands & records")}
          </p>
          {isAnswering && (
            <span className="mt-3 inline-block rounded-full border border-sky-200 bg-sky-50 text-sky-600 px-3 py-1 text-xs font-semibold">
              {isHindi ? "जवाब मोड" : "Answer Mode"}
            </span>
          )}
        </div>

        {/* Record Button */}
        <button
          type="button"
          onClick={startRecording}
          disabled={isRecording}
          className={`w-full max-w-xs rounded-2xl py-5 text-base font-bold transition duration-200 shadow-sm ${
            isRecording
              ? "bg-rose-500 text-white animate-pulse"
              : "bg-sky-500 text-white hover:bg-sky-600"
          } disabled:opacity-60`}
        >
          {isRecording
            ? (isHindi ? "⏺ रिकॉर्डिंग..." : "⏺ Recording...")
            : isAnswering
              ? (isHindi ? "🎤 जवाब रिकॉर्ड करें" : "🎤 Record Answer")
              : (isHindi ? "🎤 रिकॉर्डिंग शुरू करें" : "🎤 Start Recording")}
        </button>

        {/* Stop Button */}
        <button
          type="button"
          onClick={stopRecording}
          disabled={!isRecording}
          className="w-full max-w-xs rounded-xl border border-slate-200 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
        >
          {isHindi ? "⏹ रिकॉर्डिंग रोकें" : "⏹ Stop Recording"}
        </button>

        {/* Status */}
        <p className={`w-full max-w-xs text-center text-sm rounded-xl py-3 border transition ${
          recordStatus.includes("✅")
            ? "bg-emerald-50 border-emerald-200 text-emerald-700 font-semibold"
            : "bg-sky-50 border-sky-100 text-slate-500"
        }`}>
          {recordStatus}
        </p>
      </div>
    </div>
  );
}
