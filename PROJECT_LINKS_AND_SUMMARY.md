# KrishiMandi Intelligence (कृषि मंडी / ಕೃಷಿ ಮಂಡಿ)
**Real-Time Agricultural Commodity Price Intelligence, Market Analytics & AI Farmer Copilot Platform**

---

## 📌 Project Links & Endpoints

### 1. Source Code & Version Control
* **GitHub Repository**: [https://github.com/naveenhosamath49-hash/simple.git](https://github.com/naveenhosamath49-hash/simple.git)
* **Default Branch**: `main`

### 2. Local Operational Services
* **Frontend Web Application (Next.js PWA)**: [http://localhost:3000](http://localhost:3000)
* **Backend API Root (FastAPI)**: [http://localhost:8000](http://localhost:8000)
* **Interactive Swagger API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **System Health Check Endpoint**: [http://localhost:8000/healthz](http://localhost:8000/healthz)

### 3. Key API Endpoints
* **Current Market Prices**: `GET http://localhost:8000/api/v1/market-prices?limit=50&includeTrend=true`
* **Price History & Volatility**: `GET http://localhost:8000/api/v1/market-prices/history?commodity=Tomato&days=30`
* **Price Trends Summary**: `GET http://localhost:8000/api/v1/market-prices/trends?commodity=Tomato&days=7`
* **Commodity Master List**: `GET http://localhost:8000/api/v1/commodities`
* **Mandi Markets Directory**: `GET http://localhost:8000/api/v1/markets`
* **Hyperlocal Agromet Weather**: `GET http://localhost:8000/api/v1/weather?district=mysuru`
* **Farmer Threshold Alerts**: `GET/POST http://localhost:8000/api/v1/alerts`
* **NVIDIA NIM AI Copilot**: `POST http://localhost:8000/api/v1/ai/chat`

### 4. Authoritative External Data & AI Partners
* **APMC Mandi Wholesale Prices**: [Open Government Data (OGD) Platform India / Agmarknet](https://data.gov.in)
* **Hyperlocal Agricultural Weather**: [Open-Meteo Agromet API](https://open-meteo.com/en/docs)
* **AI Mandi Advisory Engine**: [NVIDIA NIM Foundation Models](https://integrate.api.nvidia.com/v1) (`meta/llama-3.3-70b-instruct` / `nvidia/nemotron-3.5-lightning-30b-a3b`)

---

## 🌾 Core System Capabilities

1. **Canonical APMC Mandi Price Intelligence**:
   * Minimum, Maximum, and Modal wholesale prices (₹/Quintal) from official Agmarknet sources.
   * Multi-state tracking across Karnataka, Maharashtra, Uttar Pradesh, Punjab, Delhi, and Gujarat.
   * Resilient fallback snapshots with local caching for uninterrupted offline usage.

2. **Visual Farmers Working in Land Backdrop**:
   * High-resolution photographic hero backdrop featuring Indian farmers working in agricultural land.
   * Interactive theme switcher between real paddy field photography, agricultural landscape, and sunrise illustration.
   * Ambient land background with frosted glass (`backdrop-blur-md bg-white/95`) cards for high-contrast sunlight readability.

3. **7-Day & 30-Day Velocity & Volatility Analytics**:
   * Recharts visualization modal rendering historical modal price trends, min/max price spreads, price velocity percentage, and volatility index.
   * Trend direction classification: **Rising** 📈, **Steady** ➖, **Falling** 📉.

4. **Trilingual Regional Voice Search**:
   * Voice recognition via Web Speech API in **Hindi** (`hi-IN`), **Kannada** (`kn-IN`), and **English** (`en-IN`).
   * AI crop and mandi entity extraction and normalization.

5. **Multi-Channel Price Alerts**:
   * Automated evaluation of farmer threshold subscriptions (above/below target rate).
   * Delivery channels: In-App notifications, Web Push, and SMS.
   * Automated background evaluation engine powered by APScheduler.

6. **Hyperlocal Weather Risk Advisory**:
   * Hyperlocal agromet conditions (temperature, humidity, precipitation, wind speed) from Open-Meteo.
   * Tailored agricultural harvest, spraying, and market transport advisories.

7. **NVIDIA NIM Grounded AI Mandi Copilot**:
   * Conversational market intelligence drawer powered by NVIDIA NIM LLMs.
   * Grounded with live APMC rates to provide negotiation advice and optimal harvest dispatch timing.

8. **Sunlight-Readable Mode & Offline PWA**:
   * One-click high-contrast mode for outdoor readability in bright sunlight.
   * Progressive Web App with service worker caching (`sw.js`) and Web App Manifest (`manifest.json`).

---

## 🚀 How to Run the Project Locally

### Prerequisites
* Python 3.8+ or 3.10+
* Node.js 18+ & npm

### Backend Setup (FastAPI)
```bash
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate   # On Windows
# source venv/bin/activate # On Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start FastAPI server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup (Next.js)
```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
# App will run at http://localhost:3000
```

### Docker Compose (All-in-One)
```bash
docker-compose up --build
```
