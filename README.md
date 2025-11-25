# Cosine Similarity API

API servis za računanje semantičke sličnosti između članaka i target stranica.
Dizajniran za integraciju s n8n webhookovima.

## 🚀 Quick Start

### 1. Google Service Account Setup

Budući da API radi na serveru (bez browsera), treba ti **Service Account** umjesto OAuth:

1. Idi na [Google Cloud Console](https://console.cloud.google.com/)
2. Kreiraj novi projekt ili koristi postojeći
3. Uključi **Google Sheets API**:
   - APIs & Services → Library → traži "Google Sheets API" → Enable
4. Kreiraj Service Account:
   - APIs & Services → Credentials → Create Credentials → Service Account
   - Daj ime (npr. "cosine-calculator")
   - Klikni "Done"
5. Generiraj JSON key:
   - Klikni na kreirani service account
   - Keys tab → Add Key → Create new key → JSON
   - Preuzmi JSON file
6. **VAŽNO**: Podijeli spreadsheet sa service accountom:
   - Otvori svoj Google Sheet
   - Share → dodaj email service accounta (izgleda kao `name@project.iam.gserviceaccount.com`)
   - Daj "Editor" permisije

### 2. Railway Deployment

```bash
# 1. Instaliraj Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Kreiraj novi projekt
railway init

# 4. Dodaj environment varijablu
# Otvori JSON key file i kopiraj CIJELI sadržaj
railway variables set GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'

# 5. Deploy
railway up
```

Alternativno preko Railway Dashboard:
1. New Project → Deploy from GitHub repo
2. Settings → Variables → dodaj `GOOGLE_CREDENTIALS_JSON`
3. Zalijepi cijeli JSON content (s navodnicima)

### 3. n8n Webhook Setup

#### Workflow 1: Pokreni Job

```
[Webhook Trigger] → [HTTP Request: POST /webhook] → [Respond]
```

HTTP Request node:
- Method: POST
- URL: `https://your-app.railway.app/webhook`
- Body (JSON):
```json
{
  "spreadsheet_id": "{{$json.spreadsheet_id}}",
  "sheet_name": "{{$json.sheet_name}}",
  "article_column": "A",
  "target_column": "B",
  "output_column": "C"
}
```

#### Workflow 2: Poll Status (Loop)

```
[Webhook/Trigger] → [HTTP Request: GET /status/{job_id}] → [IF status=completed] → [Done]
                                   ↑                              ↓ (else)
                                   └──────── [Wait 10s] ←─────────┘
```

## 📡 API Endpoints

### `POST /webhook`
Pokreni novi job.

**Request:**
```json
{
  "spreadsheet_id": "1L7Kbc7Ye_DBOTFaiU3cnY-lVCBRilFxc0bkLKALvsRA",
  "sheet_name": "Sheet1",
  "article_column": "A",
  "target_column": "B", 
  "output_column": "C",
  "threshold_column": "D"  // optional, default: next to output
}
```

**Response:**
```json
{
  "job_id": "a1b2c3d4",
  "status": "queued",
  "message": "Job created. Poll /status/a1b2c3d4 for progress."
}
```

### `GET /status/{job_id}`
Provjeri status joba.

**Response (processing):**
```json
{
  "job_id": "a1b2c3d4",
  "status": "processing",
  "progress": {
    "stage": "processing",
    "total": 50,
    "current": 12,
    "message": "Processing row 13 (12/50)"
  }
}
```

**Response (completed):**
```json
{
  "job_id": "a1b2c3d4", 
  "status": "completed",
  "result": {
    "processed": 50,
    "success": 45,
    "failed": 5
  }
}
```

### `GET /health`
Health check endpoint.

### `GET /jobs`
Lista svih jobova (za debugging).

## 🎯 Threshold Levels

| Score | Label | Meaning |
|-------|-------|---------|
| 0.6+ | 🟢 Excellent | Visoka semantička relevantnost |
| 0.4-0.59 | 🟡 Good | Dobra relevantnost |
| 0.3-0.39 | 🟠 Acceptable | Prihvatljiva relevantnost |
| <0.3 | 🔴 Poor | Niska relevantnost |

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CREDENTIALS_JSON` | ✅ | Service account JSON (cijeli content) |
| `MODEL_NAME` | ❌ | Sentence transformer model (default: `all-MiniLM-L6-v2`) |
| `PORT` | ❌ | Server port (default: 8080) |

## 🧪 Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export GOOGLE_CREDENTIALS_JSON='...'

# Run server
uvicorn app.main:app --reload --port 8080
```

## 📁 Project Structure

```
cosine-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app & endpoints
│   ├── calculator.py    # Core similarity logic
│   └── job_store.py     # In-memory job tracking
├── Dockerfile
├── railway.json
├── requirements.txt
└── README.md
```

## ⚠️ Limitations

- **In-memory job store**: Jobovi se gube pri restartu. Za produkciju dodaj Redis.
- **Single worker**: Railway free tier ima 1 worker. Za više konkurentnih jobova treba upgrade.
- **Scraping**: Neke stranice blokiraju requests. Originalni kod s Playwrightom je robusniji ali težak za deployment.

## 🔧 Troubleshooting

**"GOOGLE_CREDENTIALS_JSON not set"**
- Provjeri da je varijabla postavljena u Railway dashboard
- JSON mora biti validan (testiraj s `echo $GOOGLE_CREDENTIALS_JSON | jq .`)

**"Permission denied" na spreadsheet**
- Jesi li podijelio spreadsheet sa service account emailom?
- Provjeri da ima Editor permisije

**Scraping failures**
- Neke stranice blokiraju bots
- Provjeri da URL-ovi počinju s `https://`
- Za zahtjevnije stranice treba Playwright (kompleksnije za deploy)
