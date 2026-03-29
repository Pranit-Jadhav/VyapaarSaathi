import { useEffect, useState } from "react";
import { useStore, InventoryItem } from "../store/useStore";

const UNITS = ["piece", "cup", "kg", "litre", "dozen", "packet", "bundle"];

export default function Inventory() {
  const { inventory, loadInventory, addInventoryItem, removeInventoryItem, language } = useStore();
  const isHindi = language === "hi";

  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editItem, setEditItem] = useState<InventoryItem | null>(null);
  const [form, setForm] = useState({
    item_name: "",
    item_name_hi: "",
    daily_stock: 50,
    unit: "piece",
    price_per_unit: 0,
  });

  // Only show items the vendor manually created (source = "catalog")
  const catalogItems = (inventory as (InventoryItem & { source?: string })[]).filter(
    i => !i.source || i.source === "catalog"
  );

  useEffect(() => {
    loadInventory();
    const id = setInterval(loadInventory, 30000);
    return () => clearInterval(id);
  }, []);

  const openNew = () => {
    setEditItem(null);
    setForm({ item_name: "", item_name_hi: "", daily_stock: 50, unit: "piece", price_per_unit: 0 });
    setShowForm(true);
  };

  const openEdit = (item: InventoryItem) => {
    setEditItem(item);
    setForm({
      item_name: item.item_name,
      item_name_hi: item.item_name_hi || "",
      daily_stock: item.daily_stock,
      unit: item.unit,
      price_per_unit: item.price_per_unit || 0,
    });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.item_name.trim() || form.daily_stock <= 0) return;
    setSaving(true);
    try {
      await addInventoryItem({
        item_name: form.item_name.trim().toLowerCase(),
        item_name_hi: form.item_name_hi.trim() || form.item_name.trim(),
        unit: form.unit,
        daily_stock: form.daily_stock,
        current_stock: editItem ? editItem.current_stock : form.daily_stock,
        price_per_unit: form.price_per_unit,
        is_active: true,
      });
      setShowForm(false);
      setEditItem(null);
    } finally {
      setSaving(false);
    }
  };

  const stockPct = (item: InventoryItem) =>
    item.daily_stock > 0 ? Math.min(100, Math.round((item.current_stock / item.daily_stock) * 100)) : 0;

  return (
    <div className="flex flex-col gap-6 flex-1">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-800">
              {isHindi ? "📦 मेरा स्टॉक" : "📦 My Inventory"}
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              {isHindi
                ? "आइटम जोड़ें और आवाज़ से स्टॉक / रेट बदलें"
                : "Add items below. Use voice to update stock count or price anytime."}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={loadInventory}
              className="rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition"
            >
              🔄 {isHindi ? "ताज़ा करें" : "Refresh"}
            </button>
            <button
              onClick={openNew}
              className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800 transition"
            >
              + {isHindi ? "आइटम जोड़ें" : "Add Item"}
            </button>
          </div>
        </div>

      </div>

      {/* ── Add / Edit Form ─────────────────────────────────────────────────── */}
      {showForm && (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-6 shadow">
          <h3 className="text-sm font-bold text-teal-800 mb-4">
            {editItem
              ? (isHindi ? `"${editItem.item_name}" संपादित करें` : `Edit "${editItem.item_name}"`)
              : (isHindi ? "नया आइटम जोड़ें" : "Add New Item")}
          </h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-600">{isHindi ? "आइटम नाम (अंग्रेज़ी)" : "Item Name (English)"}</span>
              <input
                disabled={!!editItem}
                type="text"
                placeholder="chai, samosa, vada pav..."
                value={form.item_name}
                onChange={e => setForm(f => ({ ...f, item_name: e.target.value }))}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-300 disabled:bg-slate-100"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-600">{isHindi ? "हिंदी नाम" : "Hindi Name"}</span>
              <input
                type="text"
                placeholder="चाय, समोसा..."
                value={form.item_name_hi}
                onChange={e => setForm(f => ({ ...f, item_name_hi: e.target.value }))}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-300"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-600">{isHindi ? "इकाई" : "Unit"}</span>
              <select
                value={form.unit}
                onChange={e => setForm(f => ({ ...f, unit: e.target.value }))}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-300 bg-white"
              >
                {UNITS.map(u => <option key={u}>{u}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-600">{isHindi ? "रोज़ाना स्टॉक" : "Daily Starting Stock"}</span>
              <input
                type="number" min={1}
                value={form.daily_stock}
                onChange={e => setForm(f => ({ ...f, daily_stock: parseInt(e.target.value) || 0 }))}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-300"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-600">{isHindi ? "कीमत प्रति यूनिट (₹)" : "Price per Unit (₹)"}</span>
              <input
                type="number" min={0} step={0.5}
                value={form.price_per_unit}
                onChange={e => setForm(f => ({ ...f, price_per_unit: parseFloat(e.target.value) || 0 }))}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-300"
              />
            </label>
          </div>
          <div className="flex gap-3 mt-5">
            <button
              onClick={handleSave}
              disabled={saving || !form.item_name.trim() || form.daily_stock <= 0}
              className="rounded-full bg-slate-900 px-6 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50 transition"
            >
              {saving ? (isHindi ? "सेव हो रहा है..." : "Saving...") : (isHindi ? "सेव करें" : "Save")}
            </button>
            <button
              onClick={() => { setShowForm(false); setEditItem(null); }}
              className="rounded-full border border-slate-200 px-6 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 transition"
            >
              {isHindi ? "रद्द" : "Cancel"}
            </button>
          </div>
        </div>
      )}

      {/* ── Empty State ─────────────────────────────────────────────────────── */}
      {catalogItems.length === 0 && !showForm && (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 shadow text-center">
          <p className="text-5xl mb-4">📦</p>
          <p className="font-bold text-slate-700 text-base">
            {isHindi ? "अभी कोई आइटम नहीं है" : "No items yet"}
          </p>
          <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
            {isHindi
              ? "ऊपर \"आइटम जोड़ें\" पर क्लिक करें और अपने प्रोडक्ट बनाएं।"
              : "Click \"Add Item\" above to create your first product. Then use voice to update stock or price."}
          </p>
          <button
            onClick={openNew}
            className="mt-5 rounded-full bg-slate-900 px-6 py-2.5 text-sm font-bold text-white hover:bg-slate-800 transition"
          >
            + {isHindi ? "पहला आइटम जोड़ें" : "Add First Item"}
          </button>
        </div>
      )}

      {/* ── Inventory Cards ──────────────────────────────────────────────────── */}
      {catalogItems.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {catalogItems.map(item => {
            const pct = stockPct(item);
            const barColor = pct > 50 ? "bg-emerald-400" : pct > 20 ? "bg-amber-400" : "bg-red-500";
            const textColor = pct > 50 ? "text-emerald-600" : pct > 20 ? "text-amber-500" : "text-red-600";
            const status = pct > 50
              ? (isHindi ? "पर्याप्त" : "Sufficient")
              : pct > 20
              ? (isHindi ? "कम हो रहा है" : "Running Low")
              : (isHindi ? "लगभग खत्म" : "Critical");

            return (
              <div
                key={item.id || item.item_name}
                className="relative rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-md transition flex flex-col gap-3"
              >
                {/* Low stock badge */}
                {pct <= 20 && (
                  <span className="absolute top-3 right-3 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold text-red-600 animate-pulse">
                    ⚠️ {isHindi ? "कम" : "Low"}
                  </span>
                )}

                {/* Item name */}
                <div>
                  <p className="text-base font-bold text-slate-800 capitalize leading-tight">
                    {item.item_name_hi && item.item_name_hi !== item.item_name
                      ? item.item_name_hi
                      : item.item_name}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">{item.item_name} · {item.unit}</p>
                </div>

                {/* Stock bar */}
                <div>
                  <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex justify-between mt-1.5 text-xs">
                    <span className="text-slate-600 font-medium">
                      {item.current_stock} / {item.daily_stock} {item.unit}s
                    </span>
                    <span className={`font-bold ${textColor}`}>{pct}% · {status}</span>
                  </div>
                </div>

                {/* Price + revenue row */}
                <div className="flex justify-between text-xs text-slate-500">
                  <span>
                    {item.price_per_unit && item.price_per_unit > 0
                      ? `₹${item.price_per_unit}/${item.unit}`
                      : (isHindi ? "कीमत नहीं" : "No price set")}
                  </span>
                  {item.price_per_unit && item.price_per_unit > 0 && (
                    <span className="font-semibold text-emerald-600">
                      ≈ ₹{Math.round((item.daily_stock - item.current_stock) * item.price_per_unit)} {isHindi ? "कमाई" : "earned"}
                    </span>
                  )}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => openEdit(item)}
                    className="flex-1 rounded-xl border border-slate-200 bg-slate-50 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100 transition"
                  >
                    ✏️ {isHindi ? "बदलें" : "Edit"}
                  </button>
                  <button
                    onClick={() => removeInventoryItem(item.item_name)}
                    className="rounded-xl border border-red-100 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-500 hover:bg-red-100 transition"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
