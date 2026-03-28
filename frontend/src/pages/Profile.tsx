import { useStore } from "../store/useStore";

export default function Profile() {
  const { vendorId, setVendorId, checkHealth, healthStatus, loading } = useStore();

  return (
    <section className="rounded-3xl border border-slate-200 bg-white/80 p-6 shadow-lg">
      <h2 className="text-xl font-bold text-slate-800">Account & Preferences</h2>
      <p className="text-xs text-slate-500 mb-6">Manage your identity, data, and settings.</p>
      
      <div className="grid gap-6 md:grid-cols-2">
         <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
           <p className="text-sm font-semibold text-slate-700">Vendor ID</p>
           <p className="text-xs text-slate-500 mb-3">Your unique identifier for the database.</p>
           <input
             type="text"
             value={vendorId}
             onChange={(e) => setVendorId(e.target.value)}
             className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 outline-none focus:ring-4 focus:ring-teal-100 transition"
           />
           
           <div className="mt-5">
             <button
               type="button"
               onClick={checkHealth}
               disabled={loading.health}
               className="w-full rounded-2xl bg-slate-900 py-3 text-sm font-semibold text-white shadow-md hover:bg-slate-800 transition disabled:opacity-60"
             >
               {loading.health ? "Checking API & DB..." : "Run Health Check"}
             </button>
             <p className="mt-3 text-center text-xs font-medium text-slate-500">{healthStatus}</p>
           </div>
         </div>

         <div className="space-y-4">
           <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 flex justify-between items-center transition hover:bg-slate-50">
             <div>
                <p className="text-sm font-semibold text-slate-700">Display Language</p>
                <p className="text-xs font-medium text-slate-500">English</p>
             </div>
             <button className="text-xs font-bold text-teal-600 hover:text-teal-700 uppercase tracking-widest px-3 py-1.5 rounded-lg border border-teal-200 bg-teal-50">Change</button>
           </div>
           
           <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 flex justify-between items-center transition hover:bg-slate-50">
             <div>
                <p className="text-sm font-semibold text-slate-700">Daily Reminders</p>
                <p className="text-xs font-medium text-slate-500">8:00 PM alert</p>
             </div>
             <button className="text-xs font-bold text-teal-600 hover:text-teal-700 uppercase tracking-widest px-3 py-1.5 rounded-lg border border-teal-200 bg-teal-50">Change</button>
           </div>
           
           <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 flex justify-between items-center transition hover:bg-slate-50">
             <div>
                <p className="text-sm font-semibold text-slate-700">Export Report</p>
                <p className="text-xs font-medium text-slate-500">Download PDF of all transactions</p>
             </div>
             <button className="text-xs font-bold text-slate-600 hover:text-slate-800 uppercase tracking-widest px-3 py-1.5 rounded-lg border border-slate-300 bg-white shadow-sm">Export</button>
           </div>
         </div>
      </div>
    </section>
  );
}
