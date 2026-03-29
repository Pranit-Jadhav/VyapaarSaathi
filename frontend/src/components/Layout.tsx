import { NavLink, Outlet } from "react-router-dom";
import { useStore } from "../store/useStore";

export default function Layout() {
  const { language } = useStore();
  const isHindi = language === "hi";
  
  const isNight = false;
  const pageBg = "bg-[radial-gradient(circle_at_top_left,_#dff1f7,_#f7fbff_45%,_#e7f0fb)]";

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-full px-3 py-1.5 transition ${
      isActive 
        ? "bg-slate-200 text-slate-800 font-bold" 
        : "hover:bg-slate-100 text-slate-500 font-semibold"
    }`;

  return (
    <div className={`min-h-screen ${pageBg} flex flex-col`}>
      <header className={`border-b border-transparent ${isNight ? "bg-[#111827]/80" : "bg-white/70"} backdrop-blur sticky top-0 z-10 transition-colors`}>
        <div className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Vyapaar Saathi Logo" className="h-12 w-12 object-contain drop-shadow-md" />
            <div>
              <p className="text-sm font-semibold text-slate-700">Vyapaar Saathi</p>
              <p className="text-xs text-slate-500">{isHindi ? "बिज़नेस डैशबोर्ड" : "Business Dashboard"}</p>
            </div>
          </div>
          <nav className="flex flex-wrap items-center gap-1 text-sm">
            <NavLink to="/" className={linkClass}>{isHindi ? "होम" : "Home"}</NavLink>
            <NavLink to="/ledger" className={linkClass}>{isHindi ? "खाता" : "Ledger"}</NavLink>
            <NavLink to="/record" className={linkClass}>{isHindi ? "रिकॉर्ड" : "Record"}</NavLink>
            <NavLink to="/insights" className={linkClass}>{isHindi ? "AI सुझाव" : "AI Insights"}</NavLink>
            <NavLink to="/inventory" className={linkClass}>{isHindi ? "स्टॉक" : "Inventory"}</NavLink>
            <NavLink to="/profile" className={linkClass}>{isHindi ? "प्रोफाइल" : "Profile"}</NavLink>
          </nav>
        </div>
      </header>

      <main className="flex w-full flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
