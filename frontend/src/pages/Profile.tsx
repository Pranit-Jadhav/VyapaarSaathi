import { useStore } from "../store/useStore";

export default function Profile() {
  const { vendorId, setVendorId, checkHealth, healthStatus, loading, language, setLanguage, entries, userName, downloadReport } = useStore();
  const isHindi = language === "hi";

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-bold text-slate-800">{isHindi ? "अकाउंट और प्राथमिकताएं" : "Account & Preferences"}</h2>
      <p className="text-xs text-slate-500 mb-6">{isHindi ? "अपनी पहचान, डेटा और सेटिंग्स प्रबंधित करें।" : "Manage your identity, data, and settings."}</p>
      
      <div className="grid gap-6 md:grid-cols-2">
         <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
           <p className="text-sm font-semibold text-slate-700">{isHindi ? "वेंडर आईडी" : "Vendor ID"}</p>
           <p className="text-xs text-slate-500 mb-3">{isHindi ? "डेटाबेस के लिए आपकी विशिष्ट पहचान।" : "Your unique identifier for the database."}</p>
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
               {loading.health ? (isHindi ? "जाँच कर रहा है..." : "Checking API & DB...") : (isHindi ? "सिस्टम जांचें" : "Run Health Check")}
             </button>
             <p className="mt-3 text-center text-xs font-medium text-slate-500">{healthStatus}</p>
           </div>
         </div>

         <div className="space-y-4">
           <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 flex justify-between items-center transition hover:bg-slate-50">
             <div>
                <p className="text-sm font-semibold text-slate-700">{isHindi ? "पसंदीदा भाषा" : "Display Language"}</p>
                <p className="text-xs font-medium text-slate-500">{isHindi ? "हिंदी" : "English"}</p>
             </div>
             <button 
               onClick={() => setLanguage(isHindi ? "en" : "hi")}
               className="text-xs font-bold text-slate-900 hover:text-slate-800 uppercase tracking-widest px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50"
             >
               {isHindi ? "बदलें" : "Change"}
             </button>
           </div>
           
           <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 flex justify-between items-center transition hover:bg-slate-50">
             <div>
                <p className="text-sm font-semibold text-slate-700">{isHindi ? "दैनिक अनुस्मारक" : "Daily Reminders"}</p>
                <p className="text-xs font-medium text-slate-500">{isHindi ? "रात 8 बजे अलर्ट" : "8:00 PM alert"}</p>
             </div>
             <button className="text-xs font-bold text-slate-900 hover:text-slate-800 uppercase tracking-widest px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50">
               {isHindi ? "संपादित करें" : "Edit"}
             </button>
           </div>
           
           <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 flex justify-between items-center transition hover:bg-slate-50">
             <div>
                <p className="text-sm font-semibold text-slate-700">{isHindi ? "रिपोर्ट डाउनलोड" : "Export Report"}</p>
                <p className="text-xs font-medium text-slate-500">{isHindi ? "सभी लेन-देन का PDF प्राप्त करें" : "Download PDF of all transactions"}</p>
             </div>
             <button 
               onClick={() => {
                 if (!entries || entries.length === 0) {
                   alert(isHindi ? "कोई लेन‑देन नहीं मिला" : "No entries to export");
                   return;
                 }
                 downloadReport();
               }}
               className="text-xs font-bold text-slate-600 hover:text-slate-800 uppercase tracking-widest px-3 py-1.5 rounded-lg border border-slate-300 bg-white shadow-sm"
             >
               {isHindi ? "डाउनलोड" : "Export"}
             </button>
           </div>
         </div>
      </div>
    </section>
  );
}
