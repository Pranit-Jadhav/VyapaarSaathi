import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useStore } from "../store/useStore";

export default function Layout() {
  const { mode, setMode, output, startRecording, isRecording } = useStore();
  const navigate = useNavigate();
  
  const isNight = mode === "night";
  const pageBg = isNight
    ? "bg-[radial-gradient(circle_at_top_left,_#1e293b,_#0f172a_45%,_#0b1120)]"
    : "bg-[radial-gradient(circle_at_top_left,_#dff1f7,_#f7fbff_45%,_#e7f0fb)]";

  const handleQuickRecord = () => {
    navigate("/record");
    startRecording();
  };

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-full px-3 py-1.5 transition ${
      isActive 
        ? "bg-slate-200 text-slate-800 font-bold" 
        : "hover:bg-slate-100 text-slate-500 font-semibold"
    }`;

  return (
    <div className={`min-h-screen ${pageBg} flex flex-col`}>
      <header className="border-b border-white/60 bg-white/70 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-teal-500 text-white shadow-lg">✦</div>
            <div>
              <p className="text-sm font-semibold text-slate-700">Vyapaar Saathi</p>
              <p className="text-xs text-slate-500">Business Dashboard</p>
            </div>
          </div>
          <nav className="flex flex-wrap items-center gap-1 text-sm">
            <NavLink to="/" className={linkClass}>Home</NavLink>
            <NavLink to="/ledger" className={linkClass}>Ledger</NavLink>
            <NavLink to="/record" className={linkClass}>Record</NavLink>
            <NavLink to="/insights" className={linkClass}>AI Insights</NavLink>
            <NavLink to="/profile" className={linkClass}>Profile</NavLink>
          </nav>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleQuickRecord}
              disabled={isRecording}
              className="rounded-full bg-teal-500 px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:bg-teal-600 disabled:opacity-50"
            >
              {isRecording ? "Recording..." : "Quick Record"}
            </button>
            <div className="inline-flex rounded-full border border-slate-200 bg-white p-1 text-xs font-semibold text-slate-600">
              <button
                type="button"
                onClick={() => setMode("day")}
                className={`rounded-full px-3 py-1 ${mode === "day" ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}
              >
                Day
              </button>
              <button
                type="button"
                onClick={() => setMode("night")}
                className={`rounded-full px-3 py-1 ${mode === "night" ? "bg-teal-600 text-white" : "hover:bg-slate-100"}`}
              >
                Night
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 flex-1">
        <Outlet />

        <details className="mt-8 rounded-3xl border border-slate-200 bg-white/80 p-4 shadow-lg">
          <summary className="cursor-pointer text-sm font-semibold text-slate-600">Developer Console</summary>
          <pre className="mt-4 max-h-[20rem] overflow-auto rounded-2xl border border-slate-200 bg-slate-950 p-3 text-xs text-emerald-200">
            {JSON.stringify(output, null, 2)}
          </pre>
        </details>
      </main>
    </div>
  );
}
