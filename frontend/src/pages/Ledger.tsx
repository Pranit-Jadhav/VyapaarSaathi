import { useMemo } from "react";
import { useStore, formatInr, toNumber, toItemSummary, formatDate, isSameDay, isSameWeek } from "../store/useStore";
import { FileText, Filter, Calendar as CalendarIcon, Clock, ChevronDown } from "lucide-react";

const ledgerTabs = [
  { id: "All", en: "All", hi: "सभी" },
  { id: "Today", en: "Today", hi: "आज" },
  { id: "This Week", en: "This Week", hi: "इस सप्ताह" },
  { id: "Profit Days", en: "Profit Days", hi: "मुनाफे वाले दिन" },
  { id: "Loss Days", en: "Loss Days", hi: "नुकसान वाले दिन" },
  { id: "Flagged", en: "Flagged", hi: "फ़्लैग किए गए" }
] as const;

export default function Ledger() {
  const { entries, ledgerTab, setLedgerTab, language, userName, downloadReport } = useStore();
  const isHindi = language === "hi";

  const filteredEntries = useMemo(() => {
    const today = new Date();
    if (ledgerTab === "All") return entries;
    
    return entries.filter((entry) => {
      const entryDate = entry.entry_date ? new Date(entry.entry_date) : null;
      const earned = toNumber(entry.total_earned);
      const spent = toNumber(entry.total_spent);
      
      if (!entryDate || Number.isNaN(entryDate.getTime())) return false;
      
      if (ledgerTab === "Today") return isSameDay(entryDate, today);
      if (ledgerTab === "This Week") return isSameWeek(entryDate, today);
      if (ledgerTab === "Profit Days") return earned - spent > 0;
      if (ledgerTab === "Loss Days") return earned - spent < 0;
      if (ledgerTab === "Flagged") {
        return entry.mood_indicator === "bad" || earned - spent < 0;
      }
      return true;
    });
  }, [entries, ledgerTab]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex-1">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{isHindi ? "खाता" : "Ledger"}</h2>
          <p className="text-xs text-slate-500">{entries.length} {isHindi ? "लेनदेन दर्ज हैं।" : "total entries recorded."}</p>
        </div>
        <button 
          type="button" 
          onClick={downloadReport}
          className="rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
        >
          {isHindi ? "डेटा डाउनलोड करें" : "Export Data"}
        </button>
      </div>
      
      <div className="mt-4 flex flex-wrap gap-2">
        {ledgerTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setLedgerTab(tab.id)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
              ledgerTab === tab.id 
                ? "bg-sky-500 text-white" 
                : "border border-slate-200 text-slate-500 hover:bg-slate-50"
            }`}
          >
            {isHindi ? tab.hi : tab.en}
          </button>
        ))}
      </div>
      
      <div className="mt-5 space-y-3">
        {filteredEntries.length === 0 ? (
          <p className="text-sm text-slate-500 py-8 text-center bg-slate-50/50 rounded-2xl border border-dashed border-slate-300">
            {isHindi ? "इस फ़िल्टर के लिए कोई लेनदेन नहीं मिला।" : "No entries found for this filter."}
          </p>
        ) : (
          filteredEntries.map((entry, idx) => {
            const earned = toNumber(entry.total_earned);
            const spent = toNumber(entry.total_spent);
            const net = earned - spent;
            return (
              <div key={idx} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 hover:shadow-md transition">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span className="font-medium text-slate-600">{formatDate(entry.entry_date)}</span>
                  <span className={`rounded-full px-2 py-1 text-xs font-bold ${
                    net >= 0 ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-600"
                  }`}>
                    {net >= 0 ? "+" : "-"}{formatInr(Math.abs(net))}
                  </span>
                </div>
                <div className="mt-3 text-sm font-semibold text-slate-700 leading-snug">
                  {toItemSummary(entry.items_sold)}
                </div>
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                    {isHindi ? "आय" : "Earned"} {formatInr(earned)}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                    {isHindi ? "व्यय" : "Spent"} {formatInr(spent)}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
