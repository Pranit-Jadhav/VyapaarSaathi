import { useStore, formatInr } from "../store/useStore";

export default function Insights() {
  const { runInsights, runSuggestions, loading, insights, alerts, metrics, suggestions, language } = useStore();
  const isHindi = language === "hi";

  return (
    <section className="rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{isHindi ? "AI सुझाव" : "AI Insights"}</h2>
          <p className="text-xs text-slate-500">{isHindi ? "आपके व्यवसाय के स्वास्थ्य का गहरा विश्लेषण।" : "Deep analysis of your business health."}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={runInsights}
            disabled={loading.insights}
            className="rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
          >
            {loading.insights ? (isHindi ? "रीफ्रेश हो रहा है..." : "Refreshing...") : (isHindi ? "पैटर्न डेटा रीफ्रेश करें" : "Refresh Pattern Data")}
          </button>
          <button
            type="button"
            onClick={runSuggestions}
            disabled={loading.suggestions}
            className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
          >
            {loading.suggestions ? (isHindi ? "लोड हो रहा है..." : "Loading...") : (isHindi ? "स्टॉक प्लान बनाएं" : "Generate Stock Plan")}
          </button>
        </div>
      </div>
      
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-emerald-50/80 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center gap-2 mb-2">
             <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
             <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">{isHindi ? "सुझाव" : "Insight"}</p>
          </div>
          <p className="text-sm font-medium text-slate-700 leading-relaxed">
            {insights[0] ?? (isHindi ? "अपना बेस्ट सेलर और दैनिक औसत प्राप्त करने के लिए सुझाव चलाएं।" : "Run insights to get your best seller and daily average.")}
          </p>
        </div>
        
        <div className="rounded-2xl border border-slate-200 bg-sky-50/80 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center gap-2 mb-2">
             <span className="w-2 h-2 rounded-full bg-sky-500"></span>
             <p className="text-xs font-bold uppercase tracking-wider text-sky-700">{isHindi ? "दैनिक औसत" : "Daily Average"}</p>
          </div>
          <p className="text-sm font-medium text-slate-700 leading-relaxed">
            {typeof metrics.avg_daily_net_profit_inr === "number"
              ? (isHindi ? `आप प्रति दिन लगभग ${formatInr(metrics.avg_daily_net_profit_inr)} कमाते हैं।` : `You earn around ${formatInr(metrics.avg_daily_net_profit_inr)} per day.`)
              : (isHindi ? "आपका दैनिक औसत यहां दिखाई देगा।" : "Your daily average will appear here.")}
          </p>
        </div>
        
        <div className="rounded-2xl border border-slate-200 bg-amber-50/80 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center gap-2 mb-2">
             <span className="w-2 h-2 rounded-full bg-amber-500"></span>
             <p className="text-xs font-bold uppercase tracking-wider text-amber-700">{isHindi ? "चेतावनी" : "Alerts"}</p>
          </div>
          <p className="text-sm font-medium text-slate-700 leading-relaxed">
            {alerts[0] ?? (isHindi ? "पिछले 7 दिनों में कोई विसंगति नहीं पाई गई।" : "No anomalies detected in the last 7 days.")}
          </p>
        </div>
        
        <div className="rounded-2xl border border-slate-200 bg-violet-50/80 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center gap-2 mb-2">
             <span className="w-2 h-2 rounded-full bg-violet-500"></span>
             <p className="text-xs font-bold uppercase tracking-wider text-violet-700">{isHindi ? "कल का स्टॉक" : "Tomorrow's Stock"}</p>
          </div>
          {suggestions.length > 0 ? (
            <ul className="space-y-2 mt-2">
               {suggestions.slice(0, 3).map((item: any, idx) => (
                  <li key={idx} className="flex justify-between text-sm text-slate-700 font-medium">
                     <span>{item.item_name} <span className="opacity-50 ml-1">{isHindi ? "औसत" : "avg"} {item.avg_daily_sold}</span></span>
                     <span className="font-bold text-violet-900 bg-violet-100 rounded-lg px-2 text-xs py-0.5">{item.suggested_qty} {isHindi ? "इकाई" : "units"}</span>
                  </li>
               ))}
            </ul>
          ) : (
            <p className="text-sm font-medium text-slate-700 leading-relaxed">{isHindi ? "अगले दिन की योजना देखने के लिए स्टॉक सुझाव उत्पन्न करें।" : "Generate stock suggestions to see next-day plan."}</p>
          )}
        </div>
      </div>
    </section>
  );
}
