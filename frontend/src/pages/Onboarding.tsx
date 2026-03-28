import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStore } from "../store/useStore";

const vendorTypesEn = ["Chai seller", "Fruit cart", "Tailor", "Food stall", "Vegetables", "Other"];
const vendorTypesHi = ["चाय", "फल", "दर्जी", "खाना", "सब्जी", "अन्य"];

export default function Onboarding() {
  const navigate = useNavigate();
  const { 
    mode, setMode, 
    language, setLanguage, 
    vendorType, setVendorType,
    userName, setUserName,
    pin, setPin,
    setHasOnboarded
  } = useStore();

  const [step, setStep] = useState(1);

  const isNight = mode === "night";
  const bgMain = isNight ? "bg-[#1c1c1c] text-slate-200" : "bg-white text-slate-800";
  const bgCard = isNight ? "bg-[#252525] border-[#333]" : "bg-slate-50 border-slate-200";
  const textMuted = isNight ? "text-slate-400" : "text-slate-500";
  const tBtn = isNight ? "bg-[#333] hover:bg-[#444] text-white" : "bg-white hover:bg-slate-50 border border-slate-200 text-slate-800";
  const tBtnActive = "bg-indigo-600/20 border border-indigo-500 text-indigo-400";

  const handleFinish = () => {
    if (!userName.trim() || pin.length < 4) return;
    setHasOnboarded(true);
    navigate("/");
  };

  const isHindi = language === "hi";

  return (
    <div className={`min-h-screen ${isNight ? "bg-[#121212]" : "bg-slate-100"} flex flex-col items-center justify-center p-4`}>
      <div className="absolute top-4 right-4 flex items-center rounded-full bg-black/10 p-1 backdrop-blur-md">
        <button onClick={() => setMode("day")} className={`px-3 py-1 text-xs font-semibold rounded-full ${!isNight ? "bg-white text-slate-800 shadow-sm" : "text-slate-400"}`}>Day</button>
        <button onClick={() => setMode("night")} className={`px-3 py-1 text-xs font-semibold rounded-full ${isNight ? "bg-slate-800 text-white shadow-sm" : "text-slate-500"}`}>Night</button>
      </div>

      <div className={`w-full max-w-md rounded-3xl ${bgMain} p-6 sm:p-8 shadow-2xl transition-all`}>
        {/* Step Indicator */}
        <div className="mb-6 flex items-center justify-center gap-2">
          {[1, 2, 3].map((s) => (
            <div key={s} className={`h-1.5 rounded-full transition-all ${s === step ? "w-8 bg-indigo-500" : s < step ? "w-4 bg-indigo-500/50" : isNight ? "w-4 bg-[#333]" : "w-4 bg-slate-200"}`} />
          ))}
        </div>

        {/* SCREEN 1: Language */}
        {step === 1 && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="text-center mb-8">
              <h1 className="text-2xl font-bold mb-2">भाषा चुनें</h1>
              <p className={`text-sm ${textMuted}`}>Select your preferred language</p>
            </div>
            
            <div className={`rounded-3xl border p-5 ${bgCard}`}>
              <div className="grid gap-4">
                <button 
                  onClick={() => { setLanguage("hi"); setStep(2); }}
                  className={`flex w-full items-center justify-center rounded-2xl p-4 text-lg font-bold transition-all ${isHindi ? tBtnActive : tBtn}`}
                >
                  हिंदी
                </button>
                <button 
                  onClick={() => { setLanguage("en"); setStep(2); }}
                  className={`flex w-full items-center justify-center rounded-2xl p-4 text-lg font-bold transition-all ${!isHindi ? tBtnActive : tBtn}`}
                >
                  English
                </button>
              </div>
            </div>
            <p className={`mt-6 text-center text-xs ${textMuted}`}>
              {isHindi ? "आप इसे बाद में सेटिंग्स में बदल सकते हैं।" : "You can change this in settings anytime."}
            </p>
          </div>
        )}

        {/* SCREEN 2: Vendor Type */}
        {step === 2 && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="mb-6">
              <button onClick={() => setStep(1)} className={`mb-4 text-sm font-semibold transition hover:text-indigo-500 ${textMuted}`}>
                ← Back
              </button>
              <h1 className="text-2xl font-bold mb-2">
                {isHindi ? "आप क्या बेचते हैं?" : "What do you sell?"}
              </h1>
              <p className={`text-sm ${textMuted}`}>
                {isHindi ? "यह हमें बेहतर सुझाव देने में मदद करेगा।" : "This helps us tailor suggestions to your business."}
              </p>
            </div>

            <div className={`rounded-3xl border p-6 ${bgCard}`}>
              <div className="flex flex-wrap gap-3">
                {(isHindi ? vendorTypesHi : vendorTypesEn).map((type, idx) => {
                  const isActive = vendorType === type;
                  return (
                    <button
                      key={idx}
                      onClick={() => setVendorType(type)}
                      className={`rounded-full px-5 py-2 text-sm font-semibold transition-all ${
                        isActive 
                          ? "bg-indigo-500 text-white shadow-md scale-105" 
                          : isNight 
                            ? "bg-[#333] hover:bg-[#444] text-slate-300" 
                            : "bg-white hover:bg-slate-100 border border-slate-200 text-slate-700"
                      }`}
                    >
                      {type}
                    </button>
                  );
                })}
              </div>
            </div>

            <button 
              onClick={() => setStep(3)}
              disabled={!vendorType}
              className="mt-6 w-full rounded-2xl bg-indigo-500 py-4 text-sm font-bold text-white shadow-lg transition hover:bg-indigo-600 disabled:opacity-50 disabled:hover:bg-indigo-500"
            >
              {isHindi ? "जारी रखें" : "Continue"}
            </button>
          </div>
        )}

        {/* SCREEN 3: Name + PIN */}
        {step === 3 && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="mb-6">
              <button onClick={() => setStep(2)} className={`mb-4 text-sm font-semibold transition hover:text-indigo-500 ${textMuted}`}>
                ← Back
              </button>
              <h1 className="text-2xl font-bold mb-2">
                {isHindi ? "अपनी प्रोफाइल बनाएं" : "Create Profile"}
              </h1>
              <p className={`text-sm ${textMuted}`}>
                {isHindi ? "सुरक्षा के लिए एक पिन और अपना नाम दर्ज करें।" : "Set a name and a PIN to secure your ledger."}
              </p>
            </div>

            <div className={`rounded-3xl border p-6 space-y-6 ${bgCard}`}>
              <div>
                <label className={`mb-2 block text-sm font-semibold ${textMuted}`}>
                  {isHindi ? "अपना नाम बोलें या लिखें" : "Your Name"}
                </label>
                <div className={`flex items-center rounded-2xl border px-4 py-3 ${isNight ? "bg-[#1f1f1f] border-[#444]" : "bg-white border-slate-200"}`}>
                  <span className="mr-3 text-slate-400">🎤</span>
                  <input
                    type="text"
                    value={userName}
                    onChange={(e) => setUserName(e.target.value)}
                    placeholder={isHindi ? "टैप करें..." : "Tap to type..."}
                    className="w-full bg-transparent text-sm font-semibold outline-none placeholder:text-slate-400"
                  />
                </div>
              </div>

              <div>
                <label className={`mb-2 block text-sm font-semibold ${textMuted}`}>
                  {isHindi ? "4 अंक PIN बनाएं" : "Create 4-digit PIN"}
                </label>
                <div className="flex gap-3">
                  {[0, 1, 2, 3].map((i) => (
                    <input
                      key={i}
                      type="password"
                      maxLength={1}
                      value={pin[i] || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (!/^[0-9]?$/.test(val)) return;
                        const newPin = pin.substring(0, i) + val + pin.substring(i + 1);
                        setPin(newPin);
                        if (val && e.target.nextElementSibling) {
                          (e.target.nextElementSibling as HTMLInputElement).focus();
                        }
                      }}
                      className={`h-12 w-12 rounded-xl border text-center text-lg font-bold outline-none focus:border-indigo-500 transition-colors ${
                        isNight ? "bg-[#1f1f1f] border-[#444] text-white" : "bg-white border-slate-300 text-slate-900"
                      }`}
                    />
                  ))}
                </div>
              </div>
            </div>

            <button 
              onClick={handleFinish}
              disabled={!userName.trim() || pin.length < 4}
              className="mt-6 w-full rounded-2xl bg-teal-500 py-4 text-sm font-bold text-white shadow-lg transition hover:bg-teal-600 disabled:opacity-50 disabled:hover:bg-teal-500"
            >
              {isHindi ? "सहेजें और शुरू करें" : "Save & Open Ledger"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
