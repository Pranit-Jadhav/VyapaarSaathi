import { useMemo } from "react";
import { useStore, formatInr } from "../store/useStore";

export default function Record() {
  const { startRecording, stopRecording, isRecording, recordStatus, summary } = useStore();
  
  const netProfit = useMemo(() => summary.earned - summary.spent, [summary.earned, summary.spent]);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="flex flex-col gap-4">
        <div className="rounded-3xl border border-slate-200 bg-white/80 p-8 shadow-lg flex-1 flex flex-col justify-center items-center">
          <div className="w-full max-w-sm">
            <div className="flex items-center justify-between mb-8">
              <p className="text-lg font-bold text-slate-800">Voice Entry</p>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                AI Processing
              </span>
            </div>
            
            <button
              type="button"
              onClick={startRecording}
              disabled={isRecording}
              className={`w-full rounded-3xl py-6 text-lg font-bold shadow-lg transition duration-300 ${
                isRecording 
                  ? "bg-rose-500 text-white animate-pulse shadow-rose-200" 
                  : "bg-slate-900 text-white hover:bg-slate-800 hover:shadow-xl hover:-translate-y-1"
              } disabled:opacity-60 disabled:hover:translate-y-0`}
            >
              {isRecording ? "Recording..." : "Start Recording"}
            </button>
            
            <button
              type="button"
              onClick={stopRecording}
              disabled={!isRecording}
              className="mt-4 w-full rounded-2xl border-2 border-slate-200 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
            >
              Stop Recording
            </button>
            
            <p className="mt-6 text-center text-sm text-slate-500 bg-slate-50 rounded-xl py-3 border border-slate-100">
              {recordStatus}
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-lg">
        <h2 className="text-xl font-bold text-slate-800">Latest Audio Result</h2>
        <p className="text-xs text-slate-500">Auto-extracted totals and translation</p>
        
        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/80 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400 mb-2">Transcript</p>
          <p className="text-sm leading-relaxed text-slate-700 font-medium italic">
            "{summary.transcript}"
          </p>
        </div>
        
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-emerald-50/50 p-5">
            <p className="text-xs font-semibold text-emerald-600/70 uppercase tracking-widest">Earned</p>
            <p className="mt-1 text-2xl font-bold text-emerald-700">{formatInr(summary.earned)}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-rose-50/50 p-5">
            <p className="text-xs font-semibold text-rose-600/70 uppercase tracking-widest">Spent</p>
            <p className="mt-1 text-2xl font-bold text-rose-700">{formatInr(summary.spent)}</p>
          </div>
        </div>
        
        <div className="mt-4 rounded-2xl bg-slate-900 p-5 text-white flex justify-between items-center shadow-md">
          <span className="text-sm font-semibold opacity-80 uppercase tracking-wider">Net Profit</span>
          <span className={`text-2xl font-black ${netProfit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {formatInr(netProfit)}
          </span>
        </div>
      </section>
    </div>
  );
}
