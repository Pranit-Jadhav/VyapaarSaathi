"use strict";
const outputEl = document.getElementById("output");
const vendorIdEl = document.getElementById("vendorId");
const recordStatusEl = document.getElementById("recordStatus");
const healthStatusEl = document.getElementById("healthStatus");
const summaryTranscriptEl = document.getElementById("summaryTranscript");
const summaryEarnedEl = document.getElementById("summaryEarned");
const summarySpentEl = document.getElementById("summarySpent");
const summaryProfitEl = document.getElementById("summaryProfit");
const summaryItemsEl = document.getElementById("summaryItems");
const summaryExpensesEl = document.getElementById("summaryExpenses");
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const entriesBtn = document.getElementById("entriesBtn");
const insightsBtn = document.getElementById("insightsBtn");
const suggestBtn = document.getElementById("suggestBtn");
const healthBtn = document.getElementById("healthBtn");
let mediaRecorder = null;
let chunks = [];
let stopTimer = null;
function mustExist(el, name) {
    if (!el) {
        throw new Error(`Missing required element: ${name}`);
    }
    return el;
}
function getVendorId() {
    return mustExist(vendorIdEl, "vendorId").value.trim();
}
function printJson(data) {
    mustExist(outputEl, "output").textContent = JSON.stringify(data, null, 2);
}
function toNumber(value) {
    if (typeof value === "number") {
        return value;
    }
    if (typeof value === "string") {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
}
function formatInr(value) {
    return `Rs ${value.toFixed(2)}`;
}
function toItemSummary(value) {
    if (!Array.isArray(value) || value.length === 0) {
        return "-";
    }
    const parts = [];
    for (const row of value) {
        if (!row || typeof row !== "object" || Array.isArray(row)) {
            continue;
        }
        const itemName = row.item_name;
        const qty = row.quantity;
        const amount = row.amount;
        if (typeof itemName !== "string" || itemName.trim() === "") {
            continue;
        }
        if (typeof qty === "number") {
            parts.push(`${itemName} (${qty})`);
            continue;
        }
        if (typeof amount === "number") {
            parts.push(`${itemName} (${formatInr(amount)})`);
            continue;
        }
        parts.push(itemName);
    }
    return parts.length > 0 ? parts.join(", ") : "-";
}
function renderRecordSummary(responseData) {
    const entry = responseData.data;
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
        return;
    }
    const transcript = typeof entry.transcription === "string" && entry.transcription.trim() !== ""
        ? entry.transcription
        : "No clear transcript found.";
    const earned = toNumber(entry.total_earned);
    const spent = toNumber(entry.total_spent);
    const profit = earned - spent;
    mustExist(summaryTranscriptEl, "summaryTranscript").textContent = transcript;
    mustExist(summaryEarnedEl, "summaryEarned").textContent = formatInr(earned);
    mustExist(summarySpentEl, "summarySpent").textContent = formatInr(spent);
    mustExist(summaryProfitEl, "summaryProfit").textContent = formatInr(profit);
    mustExist(summaryItemsEl, "summaryItems").textContent = toItemSummary(entry.items_sold);
    mustExist(summaryExpensesEl, "summaryExpenses").textContent = toItemSummary(entry.expenses);
}
async function fetchJson(path, options) {
    const res = await fetch(`${window.location.origin}${path}`, options);
    const text = await res.text();
    let data;
    try {
        data = JSON.parse(text);
    }
    catch {
        data = { raw: text };
    }
    if (!res.ok) {
        throw new Error(JSON.stringify(data));
    }
    return data;
}
async function checkHealth() {
    const button = mustExist(healthBtn, "healthBtn");
    button.disabled = true;
    mustExist(healthStatusEl, "healthStatus").textContent = "Checking backend...";
    try {
        const api = await fetchJson("/health");
        const entries = await fetchJson(`/entries?vendor_id=${encodeURIComponent(getVendorId())}&limit=1`);
        const countValue = Array.isArray(entries.entries) ? entries.entries.length : 0;
        printJson({
            api,
            supabase_probe: "ok",
            entries_count: countValue
        });
        mustExist(healthStatusEl, "healthStatus").textContent = "Backend and database checks passed.";
    }
    catch (error) {
        printJson({ error: String(error) });
        mustExist(healthStatusEl, "healthStatus").textContent = "Health check failed. Check output below.";
    }
    finally {
        button.disabled = false;
    }
}
async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
        mustExist(recordStatusEl, "recordStatus").textContent = "Audio recording is not supported in this browser.";
        return;
    }
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        chunks = [];
        mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                chunks.push(event.data);
            }
        };
        mediaRecorder.onstop = async () => {
            if (stopTimer !== null) {
                window.clearTimeout(stopTimer);
                stopTimer = null;
            }
            mustExist(recordBtn, "recordBtn").disabled = false;
            mustExist(stopBtn, "stopBtn").disabled = true;
            if (chunks.length === 0) {
                mustExist(recordStatusEl, "recordStatus").textContent = "No audio was recorded.";
                return;
            }
            mustExist(recordStatusEl, "recordStatus").textContent = "Uploading voice note to backend...";
            const form = new FormData();
            form.append("audio", new Blob(chunks, { type: "audio/webm" }), "voice-entry.webm");
            form.append("vendor_id", getVendorId());
            try {
                const data = await fetchJson("/record", { method: "POST", body: form });
                printJson(data);
                renderRecordSummary(data);
                mustExist(recordStatusEl, "recordStatus").textContent = "Entry saved successfully.";
            }
            catch (error) {
                printJson({ error: String(error) });
                mustExist(recordStatusEl, "recordStatus").textContent = "Upload failed. See output for details.";
            }
            stream.getTracks().forEach((track) => track.stop());
        };
        mediaRecorder.start();
        mustExist(recordBtn, "recordBtn").disabled = true;
        mustExist(stopBtn, "stopBtn").disabled = false;
        mustExist(recordStatusEl, "recordStatus").textContent = "Recording started. Speak clearly. Auto-stop in 3 minutes.";
        stopTimer = window.setTimeout(() => {
            if (mediaRecorder?.state === "recording") {
                mediaRecorder.stop();
            }
        }, 180000);
    }
    catch (error) {
        mustExist(recordStatusEl, "recordStatus").textContent = `Microphone error: ${String(error)}`;
    }
}
function stopRecording() {
    if (mediaRecorder?.state === "recording") {
        mediaRecorder.stop();
    }
}
async function loadEntries() {
    const button = mustExist(entriesBtn, "entriesBtn");
    button.disabled = true;
    try {
        const data = await fetchJson(`/entries?vendor_id=${encodeURIComponent(getVendorId())}&limit=7`);
        printJson(data);
    }
    catch (error) {
        printJson({ error: String(error) });
    }
    finally {
        button.disabled = false;
    }
}
async function runInsights() {
    const button = mustExist(insightsBtn, "insightsBtn");
    button.disabled = true;
    try {
        const data = await fetchJson(`/insights?vendor_id=${encodeURIComponent(getVendorId())}&refresh=true`);
        printJson(data);
    }
    catch (error) {
        printJson({ error: String(error) });
    }
    finally {
        button.disabled = false;
    }
}
async function runSuggestions() {
    const button = mustExist(suggestBtn, "suggestBtn");
    button.disabled = true;
    try {
        const data = await fetchJson(`/suggestions?vendor_id=${encodeURIComponent(getVendorId())}&refresh=true`);
        printJson(data);
    }
    catch (error) {
        printJson({ error: String(error) });
    }
    finally {
        button.disabled = false;
    }
}
mustExist(recordBtn, "recordBtn").addEventListener("click", () => {
    void startRecording();
});
mustExist(stopBtn, "stopBtn").addEventListener("click", stopRecording);
mustExist(entriesBtn, "entriesBtn").addEventListener("click", () => {
    void loadEntries();
});
mustExist(insightsBtn, "insightsBtn").addEventListener("click", () => {
    void runInsights();
});
mustExist(suggestBtn, "suggestBtn").addEventListener("click", () => {
    void runSuggestions();
});
mustExist(healthBtn, "healthBtn").addEventListener("click", () => {
    void checkHealth();
});
