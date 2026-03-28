import { useMemo, useEffect } from "react";
import { Link } from "react-router-dom";
import { useStore, formatInr, toNumber, toItemSummary, formatDate, isSameDay } from "../store/useStore";

function StatPill(props: { label: string; value: string; tone?: "good" | "warn" | "info" }) {
  const tone = props.tone ?? "info";
  const toneStyles = tone === "good"
    ? "bg-emerald-50 text-emerald-700"
    : tone === "warn"
      ? "bg-amber-50 text-amber-700"
      : "bg-sky-50 text-sky-700";
  return (
    <div className={`rounded-2xl px-4 py-3 text-sm font-semibold ${toneStyles}`}>
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{props.label}</p>
      <p className="mt-1 text-lg font-bold text-slate-900">{props.value}</p>
    </div>
  );
}

export default function Home() {
  const { entries, metrics, loadEntries, vendorId, language } = useStore();
  const isHindi = language === "hi";

  useEffect(() => {
    if (entries.length === 0) {
      loadEntries();
    }
  }, [entries.length, loadEntries, vendorId]);

  const todayStats = useMemo(() => {
    let earned = 0;
    let spent = 0;
    const today = new Date();
    
    entries.forEach((entry) => {
      const entryDate = entry.entry_date ? new Date(entry.entry_date) : null;
      if (!entryDate || Number.isNaN(entryDate.getTime())) return;
      
      if (isSameDay(entryDate, today)) {
        earned += toNumber(entry.total_earned);
        spent += toNumber(entry.total_spent);
      }
    });
    
    return { earned, spent, net: earned - spent };
  }, [entries]);

  // Aggregate earnings for the last 7 days & calculate metrics
  const last7DaysData = useMemo(() => {
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (6 - i));
      return {
        dateObj: d,
        label: d.toLocaleDateString(undefined, { weekday: "short" }),
        fullDayName: d.toLocaleDateString(undefined, { weekday: "long" }),
        earned: 0,
        spent: 0,
        net: 0,
        hasActivity: false,
      };
    });

    entries.forEach((entry) => {
      const entryDate = entry.entry_date ? new Date(entry.entry_date) : null;
      if (!entryDate || Number.isNaN(entryDate.getTime())) return;
      const earned = toNumber(entry.total_earned);
      const spent = toNumber(entry.total_spent);

      const matchingDay = days.find(
        (d) =>
          d.dateObj.getFullYear() === entryDate.getFullYear() &&
          d.dateObj.getMonth() === entryDate.getMonth() &&
          d.dateObj.getDate() === entryDate.getDate()
      );
      if (matchingDay) {
        matchingDay.earned += earned;
        matchingDay.spent += spent;
        matchingDay.net += (earned - spent);
        matchingDay.hasActivity = true;
      }
    });

    const maxEarned = Math.max(...days.map((d) => d.earned), 100); // minimum scale 100
    
    const totalWeeklyNet = days.reduce((sum, d) => sum + d.net, 0);
    const weeklyAverage = Math.round(totalWeeklyNet / 7);

    let bestDay = days[6];
    let maxNet = -Infinity;
    let hasAnyData = false;
    for (const d of days) {
      if (d.hasActivity && d.net > maxNet) {
        bestDay = d;
        maxNet = d.net;
        hasAnyData = true;
      }
    }

    return { 
      days, 
      maxEarned, 
      weeklyAverage, 
      bestDayName: hasAnyData ? bestDay.fullDayName : "N/A"
    };
  }, [entries]);

  const streakDays = useMemo(() => {
    if (entries.length === 0) return 0;
    
    const uniqueDates = new Set<string>();
    entries.forEach(e => {
        if (e.entry_date) {
            const d = new Date(e.entry_date);
            if (!Number.isNaN(d.getTime())) {
                uniqueDates.add(`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`);
            }
        }
    });
    
    let streak = 0;
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${today.getMonth()}-${today.getDate()}`;
    
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = `${yesterday.getFullYear()}-${yesterday.getMonth()}-${yesterday.getDate()}`;

    if (!uniqueDates.has(todayStr) && !uniqueDates.has(yesterdayStr)) {
      return 0;
    }

    const checkDate = new Date();
    if (!uniqueDates.has(todayStr)) {
       checkDate.setDate(checkDate.getDate() - 1);
    }
    
    while(true) {
       const strDate = `${checkDate.getFullYear()}-${checkDate.getMonth()}-${checkDate.getDate()}`;
       if (uniqueDates.has(strDate)) {
           streak++;
           checkDate.setDate(checkDate.getDate() - 1);
       } else {
           break;
       }
    }
    return streak;
  }, [entries]);

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-5 lg:grid-cols-3">
        <div className="col-span-2 rounded-3xl bg-gradient-to-r from-sky-500 via-teal-500 to-emerald-400 p-6 text-white shadow-xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-white/80">{isHindi ? "आज का कुल मुनाफा" : "Today's net profit"}</p>
              <h2 className="mt-2 text-4xl font-extrabold">{formatInr(todayStats.net)}</h2>
              <p className="mt-1 text-sm text-white/80">{isHindi ? "दर्ज किए गए लेनदेन से" : "From recorded entries"}</p>
            </div>
            <div className="rounded-2xl bg-white/20 px-3 py-2 text-xs font-semibold">{streakDays}{isHindi ? " दिन की स्ट्रीक" : "d Streak"}</div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl bg-white/15 p-4">
              <p className="text-xs text-white/70">{isHindi ? "कुल आय" : "Total Earnings"}</p>
              <p className="mt-1 text-xl font-bold">{formatInr(todayStats.earned)}</p>
            </div>
            <div className="rounded-2xl bg-white/15 p-4">
              <p className="text-xs text-white/70">{isHindi ? "कुल खर्च" : "Total Expenses"}</p>
              <p className="mt-1 text-xl font-bold">{formatInr(todayStats.spent)}</p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-lg flex-1 flex flex-col justify-center">
              <p className="text-sm font-semibold text-slate-700">{isHindi ? "त्वरित कार्य" : "Quick Actions"}</p>
              <Link
                to="/record"
                className="mt-4 block w-full text-center rounded-2xl bg-slate-900 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
              >
                {isHindi ? "रिकॉर्ड करें" : "Go to Record"}
              </Link>
              <Link
                to="/ledger"
                className="mt-3 block w-full text-center rounded-2xl border border-slate-200 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
              >
                {isHindi ? "खाता देखें" : "View Ledger"}
              </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <StatPill label={isHindi ? "साप्ताहिक औसत" : "Weekly Average"} value={`${formatInr(last7DaysData.weeklyAverage)} ${isHindi ? "/ दिन" : "/ day"}`} />
        <StatPill label={isHindi ? "सबसे अच्छा दिन" : "Best Performing Day"} value={last7DaysData.bestDayName} tone="good" />
        <StatPill label={isHindi ? "स्ट्रीक" : "Streak"} value={`${streakDays} ${isHindi ? "दिन" : "days"}`} tone={streakDays > 0 ? "good" : "info"} />
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-700">{isHindi ? "आय का प्रवाह" : "Revenue Flow"}</p>
              <p className="text-xs text-slate-500">{isHindi ? "पिछले 7 दिनों में आपकी कमाई" : "Your earnings over the last 7 days"}</p>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">{isHindi ? "पिछले सप्ताह से +18%" : "+18% vs last week"}</span>
          </div>
          <div className="mt-4 h-48 w-full rounded-2xl flex items-end justify-between bg-slate-50 border border-slate-100 p-4 pt-10 px-6 gap-2">
            {last7DaysData.days.map((day, idx) => {
              const heightPercent = Math.max((day.earned / last7DaysData.maxEarned) * 100, 2);
              return (
                <div key={idx} className="flex flex-col items-center gap-2 group relative w-full h-full justify-end">
                  {/* Tooltip */}
                  <div className="absolute -top-8 opacity-0 group-hover:opacity-100 transition whitespace-nowrap bg-slate-800 text-white text-xs px-2 py-1 rounded shadow-lg pointer-events-none z-10">
                    {formatInr(day.earned)}
                  </div>
                  {/* Bar */}
                  <div 
                    className="w-full max-w-[40px] bg-gradient-to-t from-teal-500 to-emerald-400 rounded-t-sm transition-all duration-500 hover:brightness-110" 
                    style={{ height: `${heightPercent}%` }}
                  ></div>
                  {/* Label */}
                  <span className="text-[10px] sm:text-xs font-semibold text-slate-500">{day.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-700">{isHindi ? "हाल की गतिविधियां" : "Recent Activity"}</p>
            <Link to="/ledger" className="text-xs font-semibold text-sky-600 hover:text-sky-700 hover:underline">{isHindi ? "सभी देखें" : "View All"}</Link>
          </div>
          <div className="mt-4 space-y-3">
            {entries.length === 0 ? (
              <p className="text-xs text-slate-500">{isHindi ? "कौई गतिविधि नहीं।" : "No entries yet."}</p>
            ) : (
              entries.slice(0, 3).map((entry, idx) => {
                const earned = toNumber(entry.total_earned);
                const spent = toNumber(entry.total_spent);
                const net = earned - spent;
                return (
                  <div key={idx} className="rounded-2xl border border-slate-100 bg-slate-50/80 p-3">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{formatDate(entry.entry_date)}</span>
                      <span className={net >= 0 ? "text-emerald-600" : "text-rose-600"}>{formatInr(net)}</span>
                    </div>
                    <p className="mt-2 text-xs text-slate-600">{toItemSummary(entry.items_sold)}</p>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
