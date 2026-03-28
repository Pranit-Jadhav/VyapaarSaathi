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
  loading: { health: boolean; entries: boolean; insights: boolean; suggestions: boolean };
  setLoading: (field: keyof AppState["loading"], val: boolean) => void;
  ledgerTab: string;
  setLedgerTab: (tab: string) => void;

  checkHealth: () => Promise<void>;
  loadEntries: () => Promise<void>;
  runInsights: () => Promise<void>;
  runSuggestions: () => Promise<void>;
  uploadRecording: (blob: Blob) => Promise<void>;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
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
  loading: { health: false, entries: false, insights: false, suggestions: false },
  setLoading: (field, val) => set((state) => ({ loading: { ...state.loading, [field]: val } })),
  ledgerTab: "All",
  setLedgerTab: (tab) => set({ ledgerTab: tab }),

  checkHealth: async () => {
    const { vendorId, setLoading, setOutput, setHealthStatus, setEntries, setSummary } = get();
    setLoading("health", true);
    setHealthStatus("Checking API and database...");
    try {
      const api = await fetchJson("/health");
      const entriesData = await fetchJson(`/entries?vendor_id=${encodeURIComponent(vendorId)}&limit=1`);
      
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
      const data = await fetchJson(`/entries?vendor_id=${encodeURIComponent(vendorId)}&limit=7`);
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
    const { vendorId, setRecordStatus, setOutput, setSummary, setEntries, entries } = get();
    setRecordStatus("Uploading voice note...");
    const form = new FormData();
    form.append("audio", blob, "voice-entry.webm");
    form.append("vendor_id", vendorId.trim());

    try {
      const data = await fetchJson("/record", { method: "POST", body: form });
      setOutput(data);
      const entry = data.data;
      if (entry && typeof entry === "object" && !Array.isArray(entry)) {
        setSummary(summaryFromEntry(entry as JsonObject));
        setEntries([entry as Entry, ...entries].slice(0, 7));
      }
      setRecordStatus("Entry saved successfully.");
    } catch (error) {
      setOutput({ error: String(error) });
      setRecordStatus("Upload failed. Check raw output.");
    }
  },

  startRecording: async () => {
    const { uploadRecording, setRecordStatus, setIsRecording } = get();
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
        await uploadRecording(blob);
        
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
  }
}));
