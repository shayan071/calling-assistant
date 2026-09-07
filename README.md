#Voice AI Patient Registration Agent

A voice-based AI agent accessible via a real U.S. phone number that collects patient demographic information through natural conversation, persists it to a database, and exposes it through a REST API.

---

## Live Demo


| **Phone Number** | +1 (346) 344 1213 |
| **API Base URL** | https://jubilant-imagination-production-2af4.up.railway.app |
| **API Docs** | https://jubilant-imagination-production-2af4.up.railway.app/docs |

Call the number and speak naturally — the agent will register you as a new patient. When you call back, your record will still be there.

---

## Architecture

```
Caller (phone)
    ↓ voice
Vapi (telephony + STT + TTS + LLM orchestration)
    ↓ tool calls (POST /webhook)
FastAPI Backend (Railway)
    ├── /webhook   — handles Vapi tool calls (save_patient, lookup_patient)
    ├── /patients  — REST CRUD endpoints
    └── /health    — health check
         ↓
Supabase (PostgreSQL)
    └── patients table
```

**Call flow:**
1. Caller dials the Vapi phone number
2. Vapi runs the LLM (GPT-5-mini) with the system prompt
3. Agent silently calls `lookup_patient` to check for existing records
4. Agent collects required fields conversationally, then offers optional fields
5. Agent reads everything back and asks for confirmation
6. On confirmation, Vapi calls `save_patient` → FastAPI → Supabase
7. Agent confirms registration with patient ID and ends gracefully

---

## Tech Stack & Justification

| Layer | Choice | Why |
|---|---|---|
| **Telephony + Voice AI** | Vapi | Handles phone number, STT, TTS, and LLM orchestration in one platform — no audio streaming code needed |
| **LLM** | GPT-5-mini (via Vapi) | Cost-efficient, capable model; handles natural language and tool calling reliably |
| **Backend** | Python + FastAPI | Fast to write, async-ready, auto-generates `/docs`, excellent Pydantic integration |
| **Database** | PostgreSQL via Supabase | Free hosted Postgres, survives server restarts, connection pooler for reliability |
| **Hosting** | Railway | One-click GitHub deploy, auto-deploys on push, free trial tier |

**Key trade-off:** Using Vapi instead of building STT/TTS/LLM orchestration from scratch saved significant time and let us focus on prompt engineering, data validation, and API design — exactly what the assessment evaluates.

---

## Project Structure

```
calling-assistant/
├── main.py          # FastAPI app — all REST endpoints + startup lifecycle
├── database.py      # SQLAlchemy Patient model + Supabase engine config
├── schemas.py       # Pydantic schemas — request validation + response serialization
├── webhook.py       # Vapi webhook handler — save_patient + lookup_patient tools
├── system_prompt.txt # Full documented voice agent system prompt
├── requirements.txt
└── README.md
```

---

##Environment Variables

```bash
# Supabase Postgres connection string (pooler URL, port 6543)
postgresql://postgres.mjiycguxwomolvrwjues:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# Vapi API key (for reference — used in Vapi dashboard, not in code directly)
VAPI_API_KEY=081e3122-17ff-42c0-8961-835a774030bf

#Railway deployment link
https://jubilant-imagination-production-2af4.up.railway.app/
```

> **Note:** API keys are never hardcoded. The backend uses only `DATABASE_URL` at runtime. Vapi keys are configured in the Vapi dashboard and never pass through our server.

---

```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/patients` | List all patients. Filters: `?last_name=`, `?date_of_birth=`, `?phone_number=` |
| GET | `/patients/{id}` | Get single patient by UUID |
| POST | `/patients` | Create new patient |
| PUT | `/patients/{id}` | Partial update |
| DELETE | `/patients/{id}` | Soft delete (sets `deleted_at`, does not hard delete) |

All responses use the envelope:
```json
{ "data": {...}, "error": null }
```

---

## Vapi Configuration

### Assistant Settings
- **Model:** GPT-5-mini
- **Voice:** Vapi default
- **First Message:** "Hello! Thank you for calling. I am here to help register you as a new patient. May I start with your full name?"
- **Server URL:** `https://jubilant-imagination-production-2af4.up.railway.app`

### Tools
Two custom function tools are registered in Vapi:

**`lookup_patient`** — called silently at the start of every call
- Parameter: `phone_number` (string)
- Returns: `"not_found"` or `"found:FirstName:LastName:uuid"`

**`save_patient`** — called after caller confirms all information
- Required: `first_name`, `last_name`, `date_of_birth`, `sex`, `phone_number`, `address_line_1`, `city`, `state`, `zip_code`
- Optional: `email`, `address_line_2`, `insurance_provider`, `insurance_member_id`, `preferred_language`, `emergency_contact_name`, `emergency_contact_phone`

The full system prompt is documented in `system_prompt.txt`.

---

## Data Model

| Field | Type | Required | Notes |
|---|---|---|---|
| `patient_id` | UUID | Auto | Primary key |
| `first_name` | String(50) | Yes | Letters, hyphens, apostrophes |
| `last_name` | String(50) | Yes | Letters, hyphens, apostrophes |
| `date_of_birth` | Date | Yes | Not in future, MM/DD/YYYY |
| `sex` | Enum | Yes | Male/Female/Other/Decline to Answer |
| `phone_number` | String(10) | Yes | 10 digits, normalized |
| `email` | String(254) | No | Valid email format |
| `address_line_1` | String(200) | Yes | Street address |
| `address_line_2` | String(200) | No | Apt/Suite/Unit |
| `city` | String(100) | Yes | |
| `state` | String(2) | Yes | Valid U.S. state code |
| `zip_code` | String(10) | Yes | 5-digit or ZIP+4 |
| `insurance_provider` | String(100) | No | |
| `insurance_member_id` | String(50) | No | |
| `preferred_language` | String(50) | No | Default: English |
| `emergency_contact_name` | String(100) | No | |
| `emergency_contact_phone` | String(10) | No | |
| `created_at` | DateTime | Auto | UTC |
| `updated_at` | DateTime | Auto | UTC |
| `deleted_at` | DateTime | Auto | Null unless soft-deleted |

---

## Known Limitations & Trade-offs

- **ZIP code validation:** Accepts any 5-digit ZIP — does not verify against a real ZIP code database. A production system would validate against USPS data.
- **State validation:** Accepts valid 2-letter abbreviations only, but does not cross-check city/state combinations.
- **No authentication on API:** The REST API has no auth layer. In production, endpoints would require API keys or OAuth tokens.
- **Vapi uses 0.0.0.0 as caller phone number on web calls:** `lookup_patient` uses the caller's phone number from Vapi's `{{customer.number}}` variable. Web-based test calls return `0000000000`, so duplicate detection only works reliably on real phone calls.
- **No HIPAA compliance:** This is a technical assessment. Do not use real patient data.
- **Single-region deployment:** Railway deploys to a single region. A production system would use multi-region with a CDN.

---

## Bonus Features Implemented

- ✅ **Duplicate detection** — agent recognizes returning callers by phone number and offers to update instead of create
- ✅ **Call recording** — Vapi automatically records all calls (available in Vapi dashboard)

---

## Next Steps (if more time)

- Add `PUT` support through the voice agent (currently only creates new records)
- Multi-language support — detect "Hablo español" and switch agent language
- Appointment scheduling after registration (mock data)
- Simple web dashboard to view registered patients
- Unit and integration tests for the API layer
- Rate limiting and API authentication
- Webhook signature verification to ensure requests come from Vapi only

---

## Observability

All agent interactions are logged to stdout. On Railway, logs are visible under the service **Logs tab** in real time.

On every successful patient registration, the following is logged:
```
INFO - Patient registration completed: name=James May | dob=1998-01-15 |
phone=4155551212 | address=2 Main Street, Austin TX 54321 |
insurance=N/A | emergency=N/A | id=39bbcfa2-xxxx
```

Errors are also logged with tracebacks:
``` 
ERROR - Supabase PostgreSQL write failed: ...
```
