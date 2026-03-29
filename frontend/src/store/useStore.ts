import { create } from "zustand";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
type JsonObject = { [key: string]: JsonValue };
export type ThemeMode = "day" | "night";

export type SummaryData = {
  transcript: string;
  earned: number;
  spent: number;
  items: string;
  expenses: string;
};

export type Entry = {
  entry_date?: string;
  transcription?: string;
  total_earned?: JsonValue;
  total_spent?: JsonValue;
  items_sold?: JsonValue;
  expenses?: JsonValue;
  mood_indicator?: JsonValue;
};

export type InventoryItem = {
  id?: string;
  phone?: string;
  item_name: string;
  item_name_hi?: string;
  unit: string;
  daily_stock: number;
  current_stock: number;
  price_per_unit?: number;
  stock_date?: string;
  is_active?: boolean;
};

export type AIKeyFinding = {
  title_en: string;
  title_hi: string;
  description_en: string;
  description_hi: string;
  type: "positive" | "warning" | "critical" | "neutral";
  icon: string;
};

export type AIRecommendation = {
  text_en: string;
  text_hi: string;
  priority: "high" | "medium" | "low";
};

export type CategoryBreakdown = {
  name: string;
  amount: number;
  percentage: number;
};

export type AIInsightsData = {
  narrative_en: string;
  narrative_hi: string;
  key_findings: AIKeyFinding[];
  recommendations: AIRecommendation[];
  health_score: number;
  category_breakdown: CategoryBreakdown[];
  metrics: JsonObject;
  audio_hi_base64: string | null;
  audio_en_base64: string | null;
};

const DEFAULT_VENDOR_ID = "123e4567-e89b-12d3-a456-426614174000";
const MODE_STORAGE_KEY = "vyapaarsaathi-theme-mode";

const initialSummary: SummaryData = {
  transcript: "No recording yet",
  earned: 0,
  spent: 0,
  items: "-",
  expenses: "-",
};

function getInitialMode(): ThemeMode {
  if (typeof window === "undefined") return "day";
  return window.localStorage.getItem(MODE_STORAGE_KEY) === "night" ? "night" : "day";
}

function getInitialOnboarded(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem("vyapaarsaathi-onboarded") === "true";
}

function getInitialLanguage(): "en" | "hi" {
  if (typeof window === "undefined") return "en";
  return window.localStorage.getItem("vyapaarsaathi-language") === "hi" ? "hi" : "en";
}

function getInitialString(key: string, defaultVal: string = ""): string {
  if (typeof window === "undefined") return defaultVal;
  return window.localStorage.getItem(key) || defaultVal;
}

export function formatInr(value: number): string {
  return `Rs ${value.toFixed(0)}`;
}

export function toNumber(value: JsonValue | undefined): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

export function toItemSummary(value: JsonValue | undefined): string {
  if (!Array.isArray(value) || value.length === 0) return "-";
  const parts: string[] = [];
  for (const row of value) {
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const itemName = row.item_name;
    const qty = row.quantity;
    const amount = row.amount;
    if (typeof itemName !== "string" || itemName.trim() === "") continue;
    if (typeof qty === "number") parts.push(`${itemName} (${qty})`);
    else if (typeof amount === "number") parts.push(`${itemName} (${formatInr(amount)})`);
    else parts.push(itemName);
  }
  return parts.length > 0 ? parts.join(", ") : "-";
}

export function summaryFromEntry(entry: JsonObject): SummaryData {
  return {
    transcript: typeof entry.transcription === "string" && entry.transcription.trim()
      ? entry.transcription
      : "No clear transcript found.",
    earned: toNumber(entry.total_earned),
    spent: toNumber(entry.total_spent),
    items: toItemSummary(entry.items_sold),
    expenses: toItemSummary(entry.expenses),
  };
}

export function formatDate(dateValue?: string): string {
  if (!dateValue) return "Unknown date";
  const parsed = new Date(dateValue);
  if (Number.isNaN(parsed.getTime())) return dateValue;
  return parsed.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function isSameWeek(dateValue: Date, today: Date): boolean {
  const start = new Date(today);
  start.setDate(today.getDate() - today.getDay());
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(start.getDate() + 7);
  return dateValue >= start && dateValue < end;
}

// In dev mode, leave empty so requests go through the Vite proxy (same-origin, no CORS).
// The proxy in vite.config.js forwards /health, /record, /entries, etc. to port 8000.
// Only set VITE_API_URL when the frontend is deployed separately from the backend.
const API_BASE = import.meta.env.VITE_API_URL || "";

async function fetchJson(path: string, options?: RequestInit): Promise<JsonObject> {
  const base = API_BASE || window.location.origin;
  const response = await fetch(`${base}${path}`, options);
  const raw = await response.text();
  let data: JsonObject;
  try {
    data = JSON.parse(raw) as JsonObject;
  } catch {
    data = { raw };
  }
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data;
}

interface AppState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  vendorId: string;
  setVendorId: (id: string) => void;
  output: JsonObject;
  setOutput: (out: JsonObject) => void;
  summary: SummaryData;
  setSummary: (sum: SummaryData) => void;
  recordStatus: string;
  setRecordStatus: (s: string) => void;
  healthStatus: string;
  setHealthStatus: (s: string) => void;
  isRecording: boolean;
  setIsRecording: (rec: boolean) => void;
  entries: Entry[];
  setEntries: (entries: Entry[]) => void;
  insights: string[];
  alerts: string[];
  metrics: JsonObject;
  suggestions: JsonValue[];
  loading: { health: boolean; entries: boolean; insights: boolean; suggestions: boolean; aiInsights: boolean };
  setLoading: (field: keyof AppState["loading"], val: boolean) => void;
  ledgerTab: string;
  setLedgerTab: (tab: string) => void;

  hasOnboarded: boolean;
  setHasOnboarded: (val: boolean) => void;
  language: "en" | "hi";
  setLanguage: (val: "en" | "hi") => void;
  vendorType: string;
  setVendorType: (val: string) => void;
  userName: string;
  setUserName: (val: string) => void;
  pin: string;
  setPin: (val: string) => void;

  checkHealth: () => Promise<void>;
  loadEntries: () => Promise<void>;
  runInsights: () => Promise<void>;
  runSuggestions: () => Promise<void>;
  uploadRecording: (blob: Blob) => Promise<void>;
  uploadAnswer: (blob: Blob) => Promise<void>;
  cancelPending: () => void;
  startRecording: () => Promise<void>;
  stopRecording: () => void;

  // Conversation state
  pendingEntry: { reason: string; category: string } | null;
  counterQuestion: { hi: string; en: string } | null;
  counterAudioHi: string | null;
  counterAudioEn: string | null;
  conversationMode: "normal" | "answering";

  // Inventory
  inventory: InventoryItem[];
  loadInventory: () => Promise<void>;
  addInventoryItem: (item: Omit<InventoryItem, 'id' | 'phone' | 'stock_date'>) => Promise<void>;
  removeInventoryItem: (itemName: string) => Promise<void>;

  // Reports
  downloadReport: () => Promise<void>;

  // AI Insights
  aiInsights: AIInsightsData | null;
  aiInsightsPhase: string;
  runAIInsights: () => Promise<void>;
}

let recorderInstance: MediaRecorder | null = null;
let chunksArray: BlobPart[] = [];
let stopTimerRef: number | null = null;

export const useStore = create<AppState>((set, get) => ({
  mode: getInitialMode(),
  setMode: (mode) => {
    window.localStorage.setItem(MODE_STORAGE_KEY, mode);
    set({ mode });
  },

  hasOnboarded: getInitialOnboarded(),
  setHasOnboarded: (val) => {
    window.localStorage.setItem("vyapaarsaathi-onboarded", String(val));
    set({ hasOnboarded: val });
  },
  language: getInitialLanguage(),
  setLanguage: (val) => {
    window.localStorage.setItem("vyapaarsaathi-language", val);
    set({ language: val });
  },
  vendorType: getInitialString("vyapaarsaathi-vendortype", ""),
  setVendorType: (val) => {
    window.localStorage.setItem("vyapaarsaathi-vendortype", val);
    set({ vendorType: val });
  },
  userName: getInitialString("vyapaarsaathi-username", ""),
  setUserName: (val) => {
    window.localStorage.setItem("vyapaarsaathi-username", val);
    set({ userName: val });
  },
  pin: getInitialString("vyapaarsaathi-pin", ""),
  setPin: (val) => {
    window.localStorage.setItem("vyapaarsaathi-pin", val);
    set({ pin: val });
  },
  vendorId: DEFAULT_VENDOR_ID,
  setVendorId: (id) => set({ vendorId: id }),
  output: { message: "Run any action to see backend output" },
  setOutput: (out) => set({ output: out }),
  summary: initialSummary,
  setSummary: (sum) => set({ summary: sum }),
  recordStatus: "Ready to record",
  setRecordStatus: (s) => set({ recordStatus: s }),
  healthStatus: "Not checked yet",
  setHealthStatus: (s) => set({ healthStatus: s }),
  isRecording: false,
  setIsRecording: (rec) => set({ isRecording: rec }),
  entries: [],
  setEntries: (entries) => set({ entries }),
  insights: [],
  alerts: [],
  metrics: {},
  suggestions: [],
  inventory: [],
  aiInsights: null,
  aiInsightsPhase: "",
  pendingEntry: null,
  counterQuestion: null,
  counterAudioHi: null,
  counterAudioEn: null,
  conversationMode: "normal" as "normal" | "answering",
  loading: { health: false, entries: false, insights: false, suggestions: false, aiInsights: false },
  setLoading: (field, val) => set((state) => ({ loading: { ...state.loading, [field]: val } })),
  ledgerTab: "All",
  setLedgerTab: (tab) => set({ ledgerTab: tab }),

  checkHealth: async () => {
    const { vendorId, setLoading, setOutput, setHealthStatus, setEntries, setSummary } = get();
    setLoading("health", true);
    setHealthStatus("Checking API and database...");
    try {
      const api = await fetchJson("/health");
      const entriesData = await fetchJson(`/entries?vendor_id=${encodeURIComponent(vendorId)}&limit=200`);
      
      const entriesList = Array.isArray(entriesData.entries) ? entriesData.entries : [];
      setEntries(entriesList as Entry[]);
      if (entriesList.length > 0) {
        const latest = entriesList[0];
        if (latest && typeof latest === "object" && !Array.isArray(latest)) {
          setSummary(summaryFromEntry(latest as JsonObject));
        }
      }

      const countValue = Array.isArray(entriesData.entries) ? entriesData.entries.length : 0;
      setOutput({ api, supabase_probe: "ok", entries_count: countValue });
      setHealthStatus("Backend and database checks passed.");
    } catch (error) {
      setOutput({ error: String(error) });
      setHealthStatus("Health check failed. Check raw output.");
    } finally {
      setLoading("health", false);
    }
  },

  loadEntries: async () => {
    const { vendorId, setLoading, setOutput, setEntries, setSummary } = get();
    setLoading("entries", true);
    try {
      const data = await fetchJson(`/entries?vendor_id=${encodeURIComponent(vendorId)}&limit=200`);
      setOutput(data);
      
      const entriesList = Array.isArray(data.entries) ? data.entries : [];
      setEntries(entriesList as Entry[]);
      if (entriesList.length > 0) {
        const latest = entriesList[0];
        if (latest && typeof latest === "object" && !Array.isArray(latest)) {
          setSummary(summaryFromEntry(latest as JsonObject));
        }
      }
    } catch (error) {
      setOutput({ error: String(error) });
    } finally {
      setLoading("entries", false);
    }
  },

  runInsights: async () => {
    const { vendorId, setLoading, setOutput } = get();
    setLoading("insights", true);
    try {
      const data = await fetchJson(`/insights?vendor_id=${encodeURIComponent(vendorId)}&refresh=true`);
      setOutput(data);
      const nextInsights = Array.isArray(data.patterns) ? (data.patterns as string[]) : [];
      const nextAlerts = Array.isArray(data.alerts) ? (data.alerts as string[]) : [];
      set({ 
        insights: nextInsights, 
        alerts: nextAlerts,
        metrics: typeof data.metrics === "object" && data.metrics !== null && !Array.isArray(data.metrics) ? data.metrics as JsonObject : {}
      });
    } catch (error) {
      setOutput({ error: String(error) });
    } finally {
      setLoading("insights", false);
    }
  },

  runSuggestions: async () => {
    const { vendorId, setLoading, setOutput } = get();
    setLoading("suggestions", true);
    try {
      const data = await fetchJson(`/suggestions?vendor_id=${encodeURIComponent(vendorId)}&refresh=true`);
      setOutput(data);
      set({ suggestions: Array.isArray(data.suggestions) ? data.suggestions : [] });
    } catch (error) {
      setOutput({ error: String(error) });
    } finally {
      setLoading("suggestions", false);
    }
  },

  uploadRecording: async (blob: Blob) => {
    const { vendorId, setRecordStatus, setOutput, setSummary, setEntries } = get();
    setRecordStatus("Uploading voice note...");
    // Reset summary to blank while processing — don't show stale data
    setSummary({ transcript: "Processing...", earned: 0, spent: 0, items: "-", expenses: "-" });
    const form = new FormData();
    form.append("audio", blob, "voice-entry.webm");
    form.append("vendor_id", vendorId.trim());

    try {
      const data = await fetchJson("/record", { method: "POST", body: form });
      setOutput(data);

      // Check if conversation engine returned a pending status with counter question
      if (data.status === "pending") {
        set({
          pendingEntry: {
            reason: (data.pending_reason as string) || "",
            category: (data.pending_category as string) || "",
          },
          counterQuestion: {
            hi: (data.counter_question_hi as string) || "",
            en: (data.counter_question_en as string) || "",
          },
          counterAudioHi: (data.counter_audio_hi as string) || null,
          counterAudioEn: (data.counter_audio_en as string) || null,
          conversationMode: "answering",
        });
        setRecordStatus("Waiting for your answer...");

        // Still sync any entries that were saved (e.g. complete entries in a batch)
        if (data.data && (data.data as JsonObject).total_earned) {
          setSummary(summaryFromEntry(data.data as JsonObject));
        }
        await get().loadEntries();
        return;
      }

      // Complete — save normally
      if (data.data) {
        setSummary(summaryFromEntry(data.data as JsonObject));
      }
      // Clear any pending state
      set({
        pendingEntry: null,
        counterQuestion: null,
        counterAudioHi: null,
        counterAudioEn: null,
        conversationMode: "normal",
      });

      await get().loadEntries();
      
      if (Array.isArray(data.inventory_updates) && data.inventory_updates.length > 0) {
        get().loadInventory();
      }
      
      setRecordStatus("Entry saved successfully.");
    } catch (error) {
      setOutput({ error: String(error) });
      setRecordStatus("Upload failed. Check raw output.");
    }
  },

  uploadAnswer: async (blob: Blob) => {
    const { vendorId, setRecordStatus, setOutput, setSummary } = get();
    setRecordStatus("Processing your answer...");
    const form = new FormData();
    form.append("audio", blob, "voice-answer.webm");
    form.append("vendor_id", vendorId.trim());

    try {
      const data = await fetchJson("/record/answer", { method: "POST", body: form });
      setOutput(data);

      if (data.status === "pending") {
        // Still pending — another round of questions
        set({
          pendingEntry: {
            reason: (data.pending_reason as string) || "",
            category: (data.pending_category as string) || "",
          },
          counterQuestion: {
            hi: (data.counter_question_hi as string) || "",
            en: (data.counter_question_en as string) || "",
          },
          counterAudioHi: (data.counter_audio_hi as string) || null,
          counterAudioEn: (data.counter_audio_en as string) || null,
          conversationMode: "answering",
        });
        setRecordStatus("Waiting for your answer...");
        
        // If inventory was created in this round, refresh
        if (data.inventory_created) {
          get().loadInventory();
        }
        return;
      }

      // Complete!
      if (data.data) {
        setSummary(summaryFromEntry(data.data as JsonObject));
      }
      set({
        pendingEntry: null,
        counterQuestion: null,
        counterAudioHi: null,
        counterAudioEn: null,
        conversationMode: "normal",
      });

      await get().loadEntries();
      get().loadInventory();
      setRecordStatus("✅ Entry saved successfully!");
    } catch (error) {
      setOutput({ error: String(error) });
      setRecordStatus("Answer processing failed.");
    }
  },

  cancelPending: () => {
    const { vendorId } = get();
    set({
      pendingEntry: null,
      counterQuestion: null,
      counterAudioHi: null,
      counterAudioEn: null,
      conversationMode: "normal",
    });
    // Fire-and-forget cancel on server
    fetchJson(`/record/cancel?vendor_id=${encodeURIComponent(vendorId)}`, { method: "POST" }).catch(() => {});
  },

  startRecording: async () => {
    const { uploadRecording, uploadAnswer, conversationMode, setRecordStatus, setIsRecording } = get();
    if (!navigator.mediaDevices?.getUserMedia) {
      setRecordStatus("Audio recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksArray = [];

      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      recorderInstance = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) chunksArray.push(event.data);
      };

      recorder.onstop = async () => {
        setIsRecording(false);
        if (stopTimerRef !== null) {
          window.clearTimeout(stopTimerRef);
          stopTimerRef = null;
        }

        if (chunksArray.length === 0) {
          setRecordStatus("No audio was recorded.");
          return;
        }

        const blob = new Blob(chunksArray, { type: "audio/webm" });
        // Route to correct handler based on conversation state
        if (conversationMode === "answering") {
          await uploadAnswer(blob);
        } else {
          await uploadRecording(blob);
        }
        
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
      setIsRecording(true);
      setRecordStatus("Recording started. Auto-stop in 3 minutes.");

      stopTimerRef = window.setTimeout(() => {
        if (recorderInstance?.state === "recording") {
          recorderInstance.stop();
        }
      }, 180000);
    } catch (error) {
      setRecordStatus(`Microphone error: ${String(error)}`);
    }
  },

  stopRecording: () => {
    if (recorderInstance?.state === "recording") {
      recorderInstance.stop();
    }
  },

  // ── Inventory ──────────────────────────────────────────────────────────────
  loadInventory: async () => {
    const { vendorId } = get();
    try {
      const data = await fetchJson(`/inventory?vendor_id=${encodeURIComponent(vendorId)}`);
      const items = Array.isArray(data.inventory) ? data.inventory : [];
      set({ inventory: items as InventoryItem[] });
    } catch (e) {
      console.warn("loadInventory failed:", e);
    }
  },

  addInventoryItem: async (item) => {
    const { vendorId, loadInventory } = get();
    const base = API_BASE || "";
    try {
      const res = await fetch(`${base}/inventory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vendor_id: vendorId,
          item_name: item.item_name,
          daily_stock: item.daily_stock,
          unit: item.unit,
          price_per_unit: item.price_per_unit ?? 0,
          item_name_hi: item.item_name_hi ?? "",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
    } catch (e) {
      console.error("addInventoryItem failed:", e);
      alert(`Failed to save item: ${e instanceof Error ? e.message : String(e)}`);
      return;
    }
    await loadInventory();
  },

  removeInventoryItem: async (itemName) => {
    const { vendorId, loadInventory } = get();
    const base = API_BASE || "";
    try {
      const res = await fetch(
        `${base}/inventory/${encodeURIComponent(itemName)}?vendor_id=${encodeURIComponent(vendorId)}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (e) {
      console.error("removeInventoryItem failed:", e);
      alert(`Failed to remove item: ${e instanceof Error ? e.message : String(e)}`);
      return;
    }
    await loadInventory();
  },

  downloadReport: async () => {
    const { vendorId } = get();
    try {
      const data = await fetchJson(`/api/report?vendor_id=${encodeURIComponent(vendorId)}`);
      if (data.pdf_url && typeof data.pdf_url === "string") {
        window.open(data.pdf_url, "_blank");
      } else {
        alert("Failed to generated report or no sales data found.");
      }
    } catch (e: any) {
      console.warn("downloadReport failed:", e);
      alert("Error fetching report from server.");
    }
  },

  // ── AI Insights ────────────────────────────────────────────────────────────
  runAIInsights: async () => {
    const { vendorId, userName, vendorType, language, setLoading } = get();
    setLoading("aiInsights", true);
    set({ aiInsightsPhase: language === "hi" ? "डेटा विश्लेषण हो रहा है..." : "Analyzing your data..." });
    try {
      // Small delay so the user sees the phase text
      await new Promise(r => setTimeout(r, 300));
      set({ aiInsightsPhase: language === "hi" ? "AI सुझाव बना रहा है..." : "Generating AI insights..." });

      const data = await fetchJson(
        `/ai-insights?vendor_id=${encodeURIComponent(vendorId)}&vendor_name=${encodeURIComponent(userName || "Vendor")}&vendor_type=${encodeURIComponent(vendorType || "street vendor")}&language=${encodeURIComponent(language)}`
      );

      set({ aiInsightsPhase: language === "hi" ? "ऑडियो बना रहा है..." : "Creating audio summary..." });
      await new Promise(r => setTimeout(r, 200));

      set({
        aiInsights: {
          narrative_en: (data.narrative_en as string) || "",
          narrative_hi: (data.narrative_hi as string) || "",
          key_findings: (data.key_findings as AIKeyFinding[]) || [],
          recommendations: (data.recommendations as AIRecommendation[]) || [],
          health_score: (data.health_score as number) || 0,
          category_breakdown: (data.category_breakdown as CategoryBreakdown[]) || [],
          metrics: (typeof data.metrics === "object" && data.metrics !== null && !Array.isArray(data.metrics) ? data.metrics : {}) as JsonObject,
          audio_hi_base64: (data.audio_hi_base64 as string) || null,
          audio_en_base64: (data.audio_en_base64 as string) || null,
        },
        aiInsightsPhase: "",
      });
    } catch (error) {
      console.error("runAIInsights failed:", error);
      set({ aiInsightsPhase: "" });
    } finally {
      setLoading("aiInsights", false);
    }
  },
}));
