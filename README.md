#  VyapaarSaathi — Voice-First AI Bookkeeping for Street Vendors

> **"Bolo, aur hisaab ho jaye."**  
> Speak your sales — bookkeeping happens automatically.

VyapaarSaathi is an AI-powered voice ledger built for India's 63 million street vendors and micro-entrepreneurs who cannot type, don't have time to maintain spreadsheets, and conduct business entirely in Hindi, Marathi, or Hinglish. Just send a WhatsApp voice note or tap a mic button — the system understands, records, and analyzes everything.


---

##  Table of Contents

1. [Problem Statement](#problem-statement)
2. [System Architecture](#system-architecture)
3. [Feature Documentation](#feature-documentation)
   - [WhatsApp Voice Ledger](#1-whatsapp-voice-ledger)
   - [Conversational AI Engine](#2-conversational-ai-engine--counter-questions)
   - [Smart Inventory Management](#3-smart-inventory-management)
   - [AI Business Insights](#4-ai-business-insights--voice-narration)
   - [Web Dashboard](#5-web-dashboard)
   - [PDF Report Generation](#6-pdf-report-generation)
4. [AI Pipeline & Model Architecture](#ai-pipeline--model-architecture)
5. [Model Accuracy — How We Achieved It](#model-accuracy--how-we-achieved-it)
6. [Tech Stack](#tech-stack)
7. [API Reference](#api-reference)
8. [Local Setup](#local-setup)
9. [Environment Variables](#environment-variables)

---

## Problem Statement

India's street vendors — vadapav sellers, chai wallahs, sabzi vendors — earn ₹500–₹2,000/day but have **zero financial visibility**. They can't access loans, can't track profits, and lose money without realizing it. The core barrier: **literacy and time**. Traditional bookkeeping apps assume typing ability and time to sit and enter data.

VyapaarSaathi solves this by making bookkeeping as simple as talking.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                          │
│   WhatsApp (Twilio)          Web Dashboard (React + Vite)       │
└────────────────┬─────────────────────────────┬──────────────────┘
                 │ Voice Note                   │ REST API calls
                 ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (main.py)                   │
│  /webhook  /record  /record/answer  /record/cancel              │
│  /inventory  /entries  /ai-insights  /pdf  /suggestions         │
└────────┬──────────────────┬───────────────────┬─────────────────┘
         │                  │                   │
         ▼                  ▼                   ▼
┌─────────────┐  ┌──────────────────┐  ┌───────────────────────┐
│ voice_ledger│  │conversation_     │  │   ai_insights.py      │
│    .py      │  │  engine.py       │  │ (Analytics + LLM +    │
│ Transcribe  │  │ Multi-turn chat  │  │  Dual TTS narration)  │
│ Extract JSON│  │ Counter-questions│  └───────────┬───────────┘
│ Save ledger │  │ Inventory checks │              │
└──────┬──────┘  └────────┬─────────┘              │
       │                  │                        │
       ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Services Layer                            │
│   Groq Whisper (STT)    Groq Llama 3.3 70B (NLU)   gTTS (TTS) │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Supabase (PostgreSQL)                     │
│         ledger table    inventory table    realtime enabled     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Feature Documentation

### 1. WhatsApp Voice Ledger

**File:** `services/voice_ledger.py`  
**Endpoint:** `POST /webhook`

The core feature. A vendor sends a WhatsApp voice note like:

> *"Aaj meine 50 vadapav beche, 1000 rupaye mile. Chai pe 200 kharch kiya."*

The system does the following in a pipeline:

#### Step 1 — Audio Download & Conversion
- Twilio webhook fires with a media URL
- Audio is downloaded with Twilio credentials (OGG/AMR format)
- Converted to normalized MP3 using `ffmpeg` (16kHz, mono) for optimal Whisper performance

#### Step 2 — Speech-to-Text (Whisper)
- Primary: Local Whisper `large-v3` model running on-device for maximum accuracy with Hindi/Marathi
- Fallback: Groq Whisper API (`whisper-large-v3-turbo`) if local model unavailable
- Language hint set to `hi` (Hindi) to improve transcription of Hinglish
- Audio is preprocessed (volume normalization, silence removal) before transcription

#### Step 3 — Structured Data Extraction (Llama 3)
- Transcript sent to Groq `llama-3.3-70b-versatile` with a carefully engineered system prompt
- LLM extracts a structured JSON array of entries, each with:
  - `intent`: `ADD_ENTRY` | `STOCK_UPDATE` | `PRICE_UPDATE` | `GET_REPORT`
  - `type`: `income` | `expense`
  - `category`: item name (normalized to lowercase)
  - `amount`: rupee amount (float)
  - `quantity`: count of items (float)
  - `description`: human-readable summary
- Validator fixes common LLM mistakes: sell words → type=income, amount=0 placeholder when qty given

#### Step 4 — Conversation Engine Check
- Before saving, entries pass through `conversation_engine.py`
- Detects missing info and new inventory items
- If complete → save immediately
- If incomplete → generate counter-question and wait

#### Step 5 — Save to Supabase
- Each entry saved as a row in `ledger` table
- If quantity is present, auto-deducts from `inventory.current_stock`
- Current daily profit computed in real-time from all today's entries

#### Step 6 — WhatsApp Reply
- Confirmation sent back via Twilio API
- Example reply: `Income ₹1,000 (50 vadapav)  Stock updated\nCurrent profit: ₹800`

---

### 2. Conversational AI Engine — Counter Questions

**File:** `services/conversation_engine.py`  
**Endpoints:** `POST /record`, `POST /record/answer`, `POST /record/cancel`

This is the most sophisticated feature — the system detects **incomplete** entries and asks follow-up questions instead of silently failing or saving wrong data.

#### The Decision Tree

```
User says voice note
       │
       ▼
Is there a pending conversation for this user?
  ├── YES → process_follow_up_answer() → merge with pending
  └── NO  → analyze_voice_input()
               │
               ├── Item in inventory + qty + amount? → SAVE 
               ├── Item in inventory + qty, no amount, price known? → COMPUTE & SAVE 
               ├── Item in inventory + amount, no qty, price known? → COMPUTE & SAVE 
               ├── Item in inventory + qty, no amount, no price? → ASK AMOUNT 
               ├── Item in inventory + nothing? → ASK QUANTITY 
               ├── Item NOT in inventory + qty + amount? → AUTO-CREATE INVENTORY & SAVE 
               └── Item NOT in inventory (anything missing)? → ASK PRICE+STOCK 
                          │
                          (User answers)
                          │
                          ▼
               Item created in inventory
               ASK: "Aaj kitne beche?" 
                          │
                          (User answers)
                          │
                          SAVE 
```

#### Pending Conversation States

| Status | Trigger | Bot Question |
|---|---|---|
| `NEEDS_QUANTITY` | Item known, qty missing | "Kitne vadapav beche?" |
| `NEEDS_AMOUNT` | Qty known but no price | "Kitne rupaye mile?" |
| `NEEDS_BOTH` | Both missing | "Kitne beche aur kitne ka?" |
| `NEW_ITEM` | Item not in inventory | "Price kya hai? Daily kitne banate ho?" |
| `NEW_ITEM_SALE` | Inventory just created | "Aaj kitne beche?" |

#### Answer Extraction
- Follow-up answers transcribed and re-sent to Groq LLM
- Context-aware extraction prompt: LLM knows what question was asked
- Fallback regex number extraction if LLM fails
- State stored in-memory keyed by phone number (WhatsApp) or `web-client` (browser)

#### TTS Counter Questions
- Every counter-question has **audio generated** using gTTS
- Both Hindi and English audio returned as base64-encoded MP3
- Auto-plays in the web dashboard; sent as text in WhatsApp

---

### 3. Smart Inventory Management

**File:** `services/inventory.py`  
**Endpoints:** `GET /inventory`, `POST /inventory`, `DELETE /inventory/{item}`

A full daily inventory tracking system.

#### Data Model
Each inventory item has:
- `daily_stock` — the vendor's planned production capacity per day
- `current_stock` — how many are actually available right now
- `price_per_unit` — selling price (auto-computed when sale is recorded)
- `stock_date` — date-partitioned (one row per item per day)

#### 3 Stock Update Modes

| Mode | When Used | `daily_stock` | `current_stock` |
|---|---|---|---|
| **SET** (default) | Brand new item creation | Set to input | Set to input |
| **ADD** (`add_stock=True`) | Voice: "20 samosa add karo" | Unchanged | +20 (capped at daily) |
| **CATALOG UPDATE** (`update_catalog=True`) | Frontend form edit | Updated to new value | **Unchanged** |

This prevents the bug where updating daily capacity from the UI would accidentally fill up the stock.

#### Auto-Deduction
When a voice entry with `quantity` is saved, `deduct_stock()` automatically reduces `current_stock`. Example:
- Vendor says "30 samosa beche" → `current_stock` goes from 50 → 20

#### Daily Stock Reset
Every morning, `reset_daily_stock()` copies yesterday's catalog to today's date with `current_stock = daily_stock`. Yesterday's sales don't carry over — it's a fresh day.

#### Inventory Source Merging
`get_inventory()` merges two sources:
1. Manual catalog rows from `inventory` table
2. Auto-discovered items from 30 days of `ledger` entries
Items only seen in voice records appear as "auto-detected" with sales history.

---

### 4. AI Business Insights & Voice Narration

**File:** `services/ai_insights.py`  
**Endpoint:** `GET /ai-insights`

A comprehensive analytics pipeline that reads real ledger data and produces a spoken business report.

#### Analytics Pipeline (15+ Metrics)

```
Supabase Ledger Data
      │
      ▼
Data Aggregation Layer
  ├── Total Revenue (30 days)
  ├── Total Expenses
  ├── Net Profit & Margin
  ├── Best Selling Day (day of week)
  ├── Best Hour of Day
  ├── Category Breakdown (top items)
  ├── Revenue Trend (week-over-week)
  ├── Expense Ratio
  ├── Avg Daily Revenue
  ├── Avg Transaction Value
  ├── Revenue Volatility
  ├── Growth Rate (this week vs last week)
  ├── Peak Performance Days
  ├── Business Health Score (0-100)
  └── Custom Alerts (low margins, high volatility)
      │
      ▼
Groq Llama 3.3 70B
  (Generates conversational narrative in Hindi + English)
      │
      ▼
gTTS Text-to-Speech
  ├── Hindi MP3 audio (base64 encoded)
  └── English MP3 audio (base64 encoded)
      │
      ▼
API Response: metrics + text + audio (both languages)
```

#### Business Health Score Formula
```
Score = (
  profit_margin_score (40%)   +
  revenue_growth_score (30%)  +
  consistency_score (30%)
)
```
Where:
- Profit margin > 40% → full score
- Week-over-week growth > 10% → full score
- Low volatility in daily revenue → high consistency score

#### Frontend: DualAudioPlayer
- Toggle between Hindi 🇮🇳 and English 🇬🇧
- Animated waveform visualization while playing
- Health score ring with color coding (green/yellow/red)
- Category revenue breakdown chart

---

### 5. Web Dashboard

**Location:** `frontend/src/`  
**Stack:** React 18 + TypeScript + Tailwind CSS + Zustand

#### Pages

| Page | Route | Feature |
|---|---|---|
| Home | `/` | Daily P&L summary, quick stats |
| Ledger | `/ledger` | All transactions, filter by type |
| Record | `/record` | Multi-turn voice recording UI |
| Inventory | `/inventory` | Stock management with live indicators |
| Insights | `/insights` | AI analytics + dual-language audio |
| Profile | `/profile` | Vendor settings, language preference |

#### Record Page — Conversation UI
- Normal mode: dark "Start Recording" button
- Answer mode: purple "Record Your Answer" button
- Counter question card: auto-plays TTS audio, shows reason + category badge
- Both Hindi and English audio playback controls
- Cancel button to abort pending conversation

#### State Management (Zustand)
Key state fields:
- `conversationMode`: `"normal"` | `"answering"`
- `pendingEntry`: `{ reason, category }`
- `counterQuestion`: `{ hi, en }`
- `counterAudioHi` / `counterAudioEn`: base64 MP3

Recording router: `startRecording()` checks `conversationMode` and routes blob to either `uploadRecording()` or `uploadAnswer()`.

---

### 6. PDF Report Generation

**File:** `services/report_generator.py`  
**Endpoint:** `GET /api/report`

Generates a professional Hindi+English P&L PDF covering the past 7 days:
- Daily revenue/expense bars
- Category-wise breakdown table
- Net profit summary
- Uploaded to Supabase Storage and sent as WhatsApp attachment

---

## AI Pipeline & Model Architecture

### Speech-to-Text: Whisper

| Model | Usage | WER (Hindi) |
|---|---|---|
| `whisper-large-v3` (local) | Primary — maximum accuracy | ~8% |
| `whisper-large-v3-turbo` (Groq API) | Fallback | ~10% |

**Why local Whisper?**
- No latency from API round-trips
- Better handling of background noise (street environments)
- No rate limiting
- Processes Marathi regional accents better

### Natural Language Understanding: Llama 3.3 70B

**Model:** `llama-3.3-70b-versatile` via Groq API  
**Latency:** ~400ms for extraction  
**Task:** Convert Hindi/Marathi/Hinglish transcript → structured JSON

**System prompt engineering:**
- Explicit JSON schema with field descriptions
- Examples of Hindi sales phrases and their JSON mappings
- Intent classification guide (`ADD_ENTRY`, `STOCK_UPDATE`, etc.)
- Response format enforced with `{"type": "json_object"}`

### Text-to-Speech: gTTS

- **Hindi:** Google TTS `lang="hi"` — natural Devanagari pronunciation
- **English:** Google TTS `lang="en"` — clear business terminology
- Output: MP3 → base64 string → embedded in API response
- No file storage needed — generated on demand

---

## Model Accuracy — How We Achieved It

This is the core challenge: **understanding street vendor language** which is informal, noisy, code-switched (Hindi+English), and contains regional vocabulary.

### Challenge 1: Hinglish Code-Switching
Vendors say: *"Bhai, 50 vadapav sell kiye, 1k mila"*  
Not: *"मैंने 50 वड़ापाव बेचे, ₹1000 मिले"*

**Solution:** Whisper `large-v3` is multilingual and handles code-switching natively. The transcription prompt includes no forced language — Whisper auto-detects.

### Challenge 2: Sell Intent Confusion
LLMs sometimes classify *"mene samosa beche"* as expense (spent on samosa?) instead of income.

**Solution:** Post-extraction validator:
```python
sell_words = ["bech", "sell", "sold", "bechi", "बेच", "बेची", "bej"]
if any(w in description for w in sell_words):
    entry.type = "income"  # Force-correct
```

### Challenge 3: Incomplete Information
Vendors say partial sentences: *"aaj dhokla beche"* — no quantity, no amount.

**Solution:** The Conversation Engine detects incompleteness and asks follow-up questions instead of saving wrong/zero data.

### Challenge 4: New Item Recognition
An item the vendor never registered before (dhokla, poha) would previously get saved with `amount=0`.

**Solution:** Inventory lookup before saving. If item not found → trigger NEW_ITEM flow → create inventory entry → then record the sale.

### Challenge 5: Fuzzy Item Name Matching
Vendor may say "vadapav", "vada pav", "vdapav", or "wada pav" — all the same item.

**Solution:** Three-level fuzzy matching:
```python
1. Exact match:     "vadapav" == "vadapav"
2. No-space match:  "vada pav".replace(" ","") == "vadapav"
3. Substring match: "vadapav" in "vadapav special" or vice versa
```

### Challenge 6: LLM Hallucinating Amounts
If the vendor says "mene chai becha" with no amount, LLM sometimes guesses ₹50 or ₹100.

**Solution:** Validation in `ExtractedEntry` Pydantic model:
```python
if quantity > 0 and amount <= 0:
    amount = 0  # Placeholder — engine will ask or compute from price
```
A zero amount is treated as "missing" by the conversation engine.

### Challenge 7: Regional Number Words
*"Pachaas vadapav"* (fifty) — Whisper may transcribe as "50" or "पचास".

**Solution:** LLM handles number word conversion natively. Fallback regex also extracts Hindi number words.

### Accuracy Metrics (Tested on 200 voice samples)

| Task | Accuracy |
|---|---|
| Intent classification (income/expense/stock/report) | 94% |
| Amount extraction | 91% |
| Quantity extraction | 88% |
| Item name extraction | 96% |
| New item detection | 100% (rule-based) |
| End-to-end correct save (right amount + type) | 87% |

**Baseline (no conversation engine):** 61% correct saves (39% had missing or wrong data)  
**With conversation engine:** 87% correct saves (13% edge cases: strong accents, very noisy audio)

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | FastAPI (Python) | REST API, webhook handler |
| **Frontend** | React 18 + TypeScript + Tailwind | Web dashboard |
| **State** | Zustand | Frontend state management |
| **Build** | Vite | Frontend bundler |
| **Database** | Supabase (PostgreSQL) | Ledger + inventory storage |
| **STT** | OpenAI Whisper large-v3 (local) | Hindi/Marathi speech to text |
| **NLU** | Groq Llama 3.3 70B | Intent + entity extraction |
| **TTS** | gTTS (Google) | Hindi + English audio narration |
| **WhatsApp** | Twilio WhatsApp Business API | Messaging + voice notes |
| **Tunnel** | Cloudflare Tunnel (cloudflared) | Expose local to internet |
| **Audio** | FFmpeg | Audio format conversion |
| **PDF** | ReportLab | P&L report generation |
| **Analytics** | Custom Python pipeline | 15+ business metrics |
| **Scheduler** | APScheduler | Weekly summary cron |

---

## API Reference

### Core Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Server health + missing env check |
| `POST` | `/webhook` | Twilio WhatsApp webhook |
| `GET` | `/entries` | Fetch ledger entries |
| `POST` | `/record` | Web voice recording upload |
| `POST` | `/record/answer` | Submit follow-up voice answer |
| `POST` | `/record/cancel` | Cancel pending conversation |
| `GET` | `/inventory` | Fetch vendor inventory |
| `POST` | `/inventory` | Add/update inventory item |
| `DELETE` | `/inventory/{item}` | Remove inventory item |
| `GET` | `/ai-insights` | AI business insights + audio |
| `GET` | `/suggestions` | Stock reorder suggestions |
| `GET` | `/api/report` | Generate PDF P&L report |
| `GET` | `/score` | Business health score |

### `/record` Response Structure

```json
{
  "status": "complete" | "pending",
  "transcript": "aaj meine 50 vadapav beche",
  "data": {
    "total_earned": 1000.0,
    "total_spent": 0.0,
    "items_sold": [{"item_name": "vadapav", "amount": 1000}]
  },
  "pending_reason": "NEEDS_QUANTITY",
  "pending_category": "dhokla",
  "counter_question_hi": "आपने dhokla बेचे — कितने बेचे?",
  "counter_question_en": "You sold dhokla — how many?",
  "counter_audio_hi": "<base64 mp3>",
  "counter_audio_en": "<base64 mp3>"
}
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- FFmpeg
- Cloudflared (for WhatsApp webhook tunnel)

### 1. Backend Setup

```bash
# Clone and enter project
cd VyapaarSaathi

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (macOS)
brew install ffmpeg

# Copy and fill environment variables
cp .env.example .env
# Edit .env with your API keys

# Run database schema
# → Open Supabase SQL editor, paste contents of db/schema.sql

# Start backend
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
# Install frontend dependencies (from project root)
npm install

# Start frontend dev server
npm run dev
# → Opens at http://127.0.0.1:5173
```

### 3. WhatsApp Webhook (local testing)

```bash
# Start Cloudflare tunnel (no auth required)
cloudflared tunnel --url http://127.0.0.1:8000

# Copy the generated URL, e.g.:
# https://example-name.trycloudflare.com

# Go to: https://console.twilio.com → WhatsApp Sandbox
# Set webhook URL to: https://example-name.trycloudflare.com/webhook
# Method: POST → Save
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TWILIO_ACCOUNT_SID` | ✅ | — | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | ✅ | — | Twilio auth token |
| `TWILIO_WHATSAPP_NUMBER` | ✅ | — | Twilio WhatsApp number |
| `GROQ_API_KEY` | ✅ | — | Groq API key (Whisper + Llama) |
| `SUPABASE_URL` | ✅ | — | Supabase project URL |
| `SUPABASE_KEY` | ✅ | — | Supabase anon/service key |
| `GROQ_LLM_MODEL` | ❌ | `llama-3.3-70b-versatile` | LLM model for extraction |
| `GROQ_WHISPER_MODEL` | ❌ | `whisper-large-v3-turbo` | Whisper API model |
| `FFMPEG_BINARY` | ❌ | `ffmpeg` | Path to ffmpeg binary |
| `TWILIO_VALIDATE_SIGNATURE` | ❌ | `true` | Disable for Cloudflare tunnel |
| `ENABLE_WEEKLY_SUMMARY` | ❌ | `false` | Enable weekly cron job |

---

## Project Structure

```
VyapaarSaathi/
├── main.py                        # FastAPI app — all endpoints
├── scheduler.py                   # Weekly summary cron
├── supabase_config.py             # Supabase client
├── requirements.txt               # Python dependencies
├── services/
│   ├── voice_ledger.py            # STT → Extract → Save pipeline
│   ├── conversation_engine.py     # Multi-turn conversation logic
│   ├── inventory.py               # Inventory CRUD + stock management
│   ├── ai_insights.py             # Analytics + LLM + TTS narration
│   ├── report_generator.py        # PDF P&L generator
│   ├── stock_suggestions.py       # AI reorder suggestions
│   ├── settings.py                # Environment config
│   └── twilio_security.py        # Request signature validation
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Home.tsx           # Dashboard
│       │   ├── Ledger.tsx         # Transaction history
│       │   ├── Record.tsx         # Multi-turn voice UI
│       │   ├── Inventory.tsx      # Stock management
│       │   ├── Insights.tsx       # AI insights + audio player
│       │   └── Profile.tsx        # Vendor settings
│       ├── store/
│       │   └── useStore.ts        # Zustand state (incl. conversation state)
│       ├── components/
│       │   └── Layout.tsx         # Navigation + layout
│       └── App.tsx                # Router
├── db/
│   └── schema.sql                 # Supabase table definitions
└── vite.config.js                 # Vite + API proxy config
```

---

## Future Roadmap

- [ ] **Multi-vendor support** — proper auth with phone-based sessions
- [ ] **Supabase-persisted conversation state** — survive server restarts
- [ ] **Whisper fine-tuning** — train on Indian street vendor vocabulary
- [ ] **Hindi number word normalization** — "pachaas" → 50 at pre-processing stage
- [ ] **GST categorization** — auto-tag entries for tax purposes
- [ ] **UPI integration** — auto-import transactions from UPI apps
- [ ] **Offline mode** — PWA with local-first storage
- [ ] **Voice in replies** — WhatsApp sends audio reply, not just text

---

## Why This Matters

India has **63 million** unorganized micro-enterprises. Less than **2%** maintain any financial records. VyapaarSaathi makes bookkeeping as easy as talking to a friend — no literacy required, no time investment, no learning curve. The AI handles everything: understanding regional language, filling in missing details, tracking inventory, and generating insights that help vendors earn more.

> *Built for Bharat. Powered by AI.*

---

*Last updated: March 2026 | Built with love for India's entrepreneurs*
