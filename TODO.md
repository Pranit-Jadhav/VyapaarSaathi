# VyapaarSaathi – TODO LIST

## Phase 1 — Foundation (0‑6 h)

### Backend
- [ ] **Supabase setup** – create project, run SQL for 5 tables, enable storage bucket, phone‑OTP auth, RLS, copy connection string. *(≈30 min)*
- [ ] **FastAPI skeleton** – scaffold 7 empty endpoints (`/record`, `/entries`, `/insights`, `/suggestions`, `/score`, `/pdf`, `/confirm`), wire Supabase client, implement audio upload, deploy to Railway. *(≈1 h)*
- [ ] **Free transcription** – Use open‑source Whisper model locally for Hindi/Hinglish transcription, parse transcript & language, store word‑level timestamps. *(≈1 h)*
- [ ] **Groq extraction (MOST IMPORTANT)** – craft system prompt with 6 Hinglish few‑shot examples, call `llama3-70b-8192` via Groq (temp 0), parse JSON (`items_sold`, `expenses`, `total_earned`, `total_spent`, `stockout_mentions`, `mood_indicator` + confidence), store in `daily_entries`. *(≈2 h)*

### Frontend
- [ ] **React app scaffold** – Vite + React 18 + Tailwind, 4 routes (Home, Record, Ledger, Profile), i18n (`react‑i18next`), Supabase JS client, Zustand + React‑Query, deploy to Vercel, keep bundle < 200 KB gzipped. *(≈1 h)*
- [ ] **Onboarding flow** – three screens: language pick, vendor type, voice‑captured name + 4‑digit PIN, tutorial voice note prompt; set UI & AI language. *(≈1 h)*
- [ ] **PWA + offline** – Workbox service worker, Dexie.js IndexedDB queue for audio, sync on reconnect, Opus compression (~130 KB/min), 2G timeout handling. *(≈30 min)*

---

## Phase 2 — Core Product (6‑14 h)

### Backend
- [ ] **Pattern engine** – 5 SQL analytics queries, send stats to Claude → 3 Hindi sentences, store in `vendor_insights`, schedule nightly APScheduler job (2 am IST), require ≥ 4 entries. *(≈2 h)*
- [ ] **Stock suggestion engine** – compute avg daily qty (last 7 days), boost for recent `stockout_mentions`, call Open‑Meteo (no key) for weather, apply multipliers, round to nearest 5, output Hindi lines. *(≈1 h)*
- [ ] **Anomaly detection** – 7‑day rolling averages, z‑score spikes/drops, store alerts in `vendor_insights`, mood‑based support card trigger (3 consecutive “bad” days). *(≈1 h)*

### Frontend
- [ ] **Record screen** – MediaRecorder (16 kHz mono, WebM/Opus), full‑screen mic UI with live waveform (wavesurfer.js), 3 min auto‑stop, overlay “बोलते रहिए…”, upload to `/record`, show “सुन रहा हूं…”, “समझ रहा हूं…”, preview result. *(≈2 h)*
- [ ] **Today’s entry screen** – display extracted items as tappable chips (confidence‑colored), chip taps seek audio fragment, centered net profit, low‑confidence confirmation panel (single‑question flow), POST `/confirm`. *(≈2 h)*
- [ ] **Ledger / history screen** – default 7‑day card list, expandable day view, gray placeholders for missing days with “Add missing day?” prompt, monthly view with color‑coded days, weekly & monthly totals, comparative sentence. *(≈1 h)*
- [ ] **Home screen** – status card (earnings, expenses, profit, top item), big mic button (“आज का हिसाब बोलें”), secondary buttons (History, Stock suggestion, My score), bottom nav (Home/Record/Ledger/Me), streak counter, human‑readable “time since last entry”. *(≈1 h)*

---

## Phase 3 — Intelligence + PDF (14‑20 h)

### Backend
- [ ] **Loan readiness score** – compute 0‑100 score from 4 factors (income consistency, growth trend, expense control, data quality) using ≥ 14 days data, map to scheme thresholds (PM SVANidhi, MUDRA Shishu, state schemes). *(≈2 h)*
- [ ] **Scheme matcher rules engine** – hard‑code 6 schemes, eligibility rules against vendor profile, OpenStreetMap Nominatim for nearest bank/center (free), state from onboarding, manual quarterly updates. *(≈1 h)*
- [ ] **PDF data endpoint** – GET `/pdf` aggregates vendor’s `daily_entries`, returns structured JSON for frontend jsPDF, exclude flagged expenses, Indian number formatting. *(≈30 min)*

### Frontend
- [ ] **Insights screen** – three tabs (Patterns, Tomorrow, Alerts); Patterns show Claude‑generated Hindi sentences, Tomorrow shows stock suggestions with weather note, Alerts show anomaly cards with actions, mood‑based support message after 3 bad days. *(≈1 h)*
- [ ] **Loan score screen** – large 0‑100 number with color‑coded ring, Hindi status line, four sub‑score bars (with improvement tip), eligible scheme cards. *(≈1 h)*
- [ ] **PDF export screen** – HTML template for one‑page income statement, jsPDF + html2canvas rendering, preview, download & WhatsApp share button, Hindi disclaimer. *(≈2 h)*
- [ ] **Settings + profile** – language toggle, edit vendor name/type, WhatsApp number, daily reminder picker, data backup toggle, push‑notification permission, delete account, version display. *(≈30 min)*

---

## Phase 4 — Winning Features (20‑28 h)

### Backend
- [ ] **WhatsApp bot** – Twilio sandbox (free tier), FastAPI webhook, download audio from Twilio URL, run full pipeline (transcribe → extract → save), compose Hindi reply via Claude, end‑to‑end test on real phone. *(≈3 h)*
- [ ] **Audio timestamp storage** – store Whisper word‑level timestamps per `daily_entry`, map entities to timestamps, expose presigned URLs (90‑day expiry). *(≈1 h)*
- [ ] **Festival calendar data** – hard‑code 20 major Indian festivals, category‑specific multipliers, 3‑day advance trigger, state‑specific festivals from onboarding. *(≈30 min)*
- [ ] **Daily push reminder job** – store Web Push subscription per vendor, APScheduler job checks reminder time, sends push if today’s entry missing, updates streak counter. *(≈30 min)*

### Frontend
- [ ] **Audio playback UI** – tappable chips fetch presigned URL, set `audio.currentTime` using `start_ms/1000`, play until `end_ms`, waveform overlay, builds trust. *(≈2 h)*
- [ ] **Festival calendar card UI** – 3‑day advance card on home, days‑remaining, suggested stock boost, dismissible “क्या आप अतिरिक्त स्टॉक तैयार करना चाहेंगे?” prompt. *(≈30 min)*
- [ ] **Scheme card UI** – per‑eligible scheme badge, required documents list, Google Maps embed for nearest center, Hindi eligibility message, link to application form. *(≈1 h)*
- [ ] **Streak + push notification UI** – streak counter on home, ServiceWorker registration, gentle permission request, break‑streak message, feed streak into Loan‑Score data‑quality sub‑score. *(≈30 min)*

---

## Demo Prep (2 h, shared)
- [ ] Seed 7 days of realistic data for demo vendor “Raju Bhai”.
- [ ] Record a real Hindi voice note for live demo.
- [ ] Test WhatsApp bot end‑to‑end on a physical Android device.
- [ ] Generate a PDF and verify bank‑ready formatting.
- [ ] Rehearse 3‑minute demo story (problem → solution → impact → live demo → loan score reveal).

---

*All estimates are approximate. Adjust as needed during sprint planning.*
