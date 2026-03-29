import { NavLink, Outlet } from "react-router-dom";
import { useStore } from "../store/useStore";

export default function Layout() {
  const { language } = useStore();
  const isHindi = language === "hi";

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-full px-4 py-2 text-sm font-medium transition ${
      isActive
        ? "bg-sky-500 text-white font-semibold shadow-sm"
        : "text-slate-600 hover:bg-sky-50 hover:text-sky-600"
    }`;

  return (
    <div className="min-h-screen bg-sky-50 flex flex-col">
      <header className="border-b border-sky-100 bg-white sticky top-0 z-10 shadow-sm">
        <div className="flex w-full items-center gap-12 px-6 py-2 sm:px-8 lg:px-12">

          {/* Logo + Brand */}
          <div className="flex items-center gap-4 shrink-0">
            <img
              src="/logo.png"
              alt="VyapaarSaathi Logo"
              className="h-16 w-auto object-contain"
            />
            <div className="flex flex-col leading-tight">
              <p className="text-base font-bold text-slate-900">VyapaarSaathi</p>
              <p className="text-xs text-sky-500 font-medium">
                {isHindi ? "आपका बिज़नेस साथी" : "Your Business Companion"}
              </p>
            </div>
          </div>

          {/* Nav Links */}
          <nav className="flex items-center gap-2">
            <NavLink to="/"          className={linkClass}>{isHindi ? "होम"       : "Home"}</NavLink>
            <NavLink to="/ledger"    className={linkClass}>{isHindi ? "खाता"      : "Ledger"}</NavLink>
            <NavLink to="/record"    className={linkClass}>{isHindi ? "रिकॉर्ड"  : "Record"}</NavLink>
            <NavLink to="/insights"  className={linkClass}>{isHindi ? "AI सुझाव"  : "AI Insights"}</NavLink>
            <NavLink to="/inventory" className={linkClass}>{isHindi ? "स्टॉक"    : "Inventory"}</NavLink>
            <NavLink to="/profile"   className={linkClass}>{isHindi ? "प्रोफाइल" : "Profile"}</NavLink>
          </nav>

        </div>
      </header>

      <main className="flex w-full flex-col gap-6 px-6 py-6 sm:px-8 lg:px-12 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
