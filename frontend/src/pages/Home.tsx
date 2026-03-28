import { useMemo, useEffect } from "react";
import { Link } from "react-router-dom";
import { useStore, formatInr, toNumber, toItemSummary, formatDate } from "../store/useStore";

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
  const { summary, entries, metrics, loadEntries, vendorId } = useStore();

  useEffect(() => {
    if (entries.length === 0) {
      loadEntries();
    }
  }, [entries.length, loadEntries, vendorId]);

  const netProfit = useMemo(() => summary.earned - summary.spent, [summary.earned, summary.spent]);

  // Aggregate earnings for the last 7 days
  const last7DaysData = useMemo(() => {
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - (6 - i));
      return {
        dateObj: d,
        label: d.toLocaleDateString(undefined, { weekday: "short" }),
        earned: 0,
      };
    });

    entries.forEach((entry) => {
      const entryDate = entry.entry_date ? new Date(entry.entry_date) : null;
      if (!entryDate || Number.isNaN(entryDate.getTime())) return;
      const earned = toNumber(entry.total_earned);

      const matchingDay = days.find(
        (d) =>
          d.dateObj.getFullYear() === entryDate.getFullYear() &&
          d.dateObj.getMonth() === entryDate.getMonth() &&
          d.dateObj.getDate() === entryDate.getDate()
      );
      if (matchingDay) matchingDay.earned += earned;
    });

    const maxEarned = Math.max(...days.map((d) => d.earned), 100); // minimum scale 100
    return { days, maxEarned };
  }, [entries]);

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-5 lg:grid-cols-3">
        <div className="col-span-2 rounded-3xl bg-gradient-to-r from-sky-500 via-teal-500 to-emerald-400 p-6 text-white shadow-xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-white/80">Today's net profit</p>
              <h2 className="mt-2 text-4xl font-extrabold">{formatInr(netProfit)}</h2>
              <p className="mt-1 text-sm text-white/80">From recorded entries</p>
            </div>
            <div className="rounded-2xl bg-white/20 px-3 py-2 text-xs font-semibold">7d Streak</div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl bg-white/15 p-4">
              <p className="text-xs text-white/70">Total Earnings</p>
              <p className="mt-1 text-xl font-bold">{formatInr(summary.earned)}</p>
            </div>
            <div className="rounded-2xl bg-white/15 p-4">
              <p className="text-xs text-white/70">Total Expenses</p>
              <p className="mt-1 text-xl font-bold">{formatInr(summary.spent)}</p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-lg flex-1 flex flex-col justify-center">
             <p className="text-sm font-semibold text-slate-700">Quick Actions</p>
             <Link
                to="/record"
                className="mt-4 block w-full text-center rounded-2xl bg-slate-900 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
              >
                Go to Record
              </Link>
              <Link
                to="/ledger"
                className="mt-3 block w-full text-center rounded-2xl border border-slate-200 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
              >
                View Ledger
              </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <StatPill label="Weekly Average" value={`${formatInr(metrics.avg_daily_net_profit_inr ? toNumber(metrics.avg_daily_net_profit_inr) : 589)} / day`} />
        <StatPill label="Best Performing Day" value={typeof metrics.best_day_of_week === "string" ? metrics.best_day_of_week : "Sunday"} />
        <StatPill label="Streak" value="7 days" tone="good" />
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-700">Revenue Flow</p>
              <p className="text-xs text-slate-500">Your earnings over the last 7 days</p>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">+18% vs last week</span>
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
            <p className="text-sm font-semibold text-slate-700">Recent Activity</p>
            <Link to="/ledger" className="text-xs font-semibold text-sky-600 hover:text-sky-700 hover:underline">View All</Link>
          </div>
          <div className="mt-4 space-y-3">
            {entries.length === 0 ? (
              <p className="text-xs text-slate-500">No entries yet.</p>
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
