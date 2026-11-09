# Airtel Business — Project Udyam Digital

> **Enterprise B2B Conversational AI Discovery, Recommendation Engine, Smart Digital KYC & Order Lifecycle Platform**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](backend/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-Supabase%20PostgreSQL-3ECF8E.svg)](https://supabase.com/)
[![Authentication](https://img.shields.io/badge/Auth-Supabase%20Auth-3ECF8E.svg)](https://supabase.com/)
[![Compliance](https://img.shields.io/badge/Compliance-DPDP%20Act%202023-purple.svg)](docs/)

---

## 1. Project Overview

Project Udyam Digital is an AI-powered enterprise telecommunications advisory and onboarding system designed for Indian MSMEs and enterprise operations teams. It provides:

1. **Conversational AI Customer Discovery**: An 11-stage pipeline that ingests customer needs via text or voice, cleans inputs, extracts structured requirements, and detects readiness.
2. **Deterministic Recommendation Engine**: A 14-stage solution bundle builder providing eligibility checking, cohort matching, pricing deltas, dependency closure, and co-termination terms.
3. **Smart Digital KYC Verification**: Zero-retention document processing complying with the DPDP Act 2023, performing image quality checks, GSTIN Mod-36 checksum validation, official registry cross-referencing (3,534 GSTIN and 2,723 Udyam records), and AES-256-GCM encryption.
4. **Order Management & Live Provisioning (OMS)**: End-to-end lifecycle tracking across 4 key milestones from order creation to field dispatch and circuit activation.
5. **NOC Operations & Admin Console**: Real-time management interface to monitor orders, update milestone statuses, and review AI escalations.

---

## 2. Technologies Used

- **Backend**: Python 3.10+ with FastAPI, Pydantic v2, PyJWT, Cryptography, Pandas, OpenCV, RapidFuzz.
- **Frontend**: 
  - Production Single-Page Application (HTML5, Tailwind CSS, JavaScript) served natively by FastAPI.
  - Modern TanStack Start / React application located in `frontend/` (Vite, React 19, Tailwind CSS v4, Lucide).
- **Database**: Supabase PostgreSQL (Exclusive persistence layer) with Row Level Security (RLS).
- **Authentication**: Supabase Auth (Exclusive authentication provider) with token validation and role-based access control.
- **AI Integrations**: Sarvam AI (`sarvam-105b-conversations`, `saaras:v3`) and Google Gemini Vision (`gemini-2.5-flash`).

---

## 3. Project Structure

```text
.
├── backend/
│   ├── agent/                 # 11-Stage Conversational AI & Discovery Pipeline
│   ├── auth/                  # Supabase Auth service & token validation
│   ├── config/                # Telecom thresholds, weights, columns, and taxonomies
│   ├── data/                  # City tier mappings, business taxonomies, and stats
│   ├── database/              # Supabase database client and SQL migrations
│   ├── data_preprocessing/    # City tier classifier, business segment mapper, and ETL
│   ├── kyc_verification/      # Smart Digital KYC engine (Mod-36 checksum, AES-256 vault)
│   ├── order_tracking/        # Order Management System (OMS) & milestone lifecycle
│   ├── recommendation/        # 14-Stage Recommendation Engine & add-on toggles
│   ├── schema/                # Pydantic v2 data models & API schemas
│   ├── scripts/               # Supabase database seeding scripts
│   ├── YTL_TrackA_Udyam_Digital_Data/ # Official MSME registries & KYC documents
│   └── main.py                # Main FastAPI application server
├── frontend/                  # React & SPA User Interface
│   ├── index.html             # Production enterprise SPA served by FastAPI
│   ├── src/                   # React / TanStack Start source code
│   └── package.json           # Node.js dependencies and build scripts
├── docs/                      # Technical specifications and architectural documentation
├── .env.example               # Template for required environment variables
├── requirements.txt           # Python dependencies manifest
└── README.md                  # Project documentation
```

---

## 4. Native Setup & Installation (No Docker Required)

### Step 1: Clone and Set Up Environment

```bash
git clone <repository-url>
cd airtel_sync
```

### Step 2: Install Dependencies

#### Python Backend Dependencies
Ensure you have Python 3.10+ installed:
```bash
pip install -r requirements.txt
```

#### Frontend Dependencies (Optional, for building/testing React components)
Ensure you have Node.js 18+ installed:
```bash
cd frontend
npm install
cd ..
```

---

## 5. Configuration (.env)

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Key environment variables:
| Variable | Description | Required? |
|---|---|---|
| `PORT` | Application server port (default: `8000`) | Optional |
| `SUPABASE_URL` | Supabase Project URL (`https://<project-ref>.supabase.co`) | Required |
| `SUPABASE_ANON_KEY` | Supabase Publishable / Anon Key | Required |
| `SUPABASE_JWT_SECRET` | Supabase JWT Secret for token verification | Required |
| `SARVAM_API_KEY` | Sarvam AI API Key for Indic LLM chat & Speech-to-Text | Required for AI chat & STT |
| `ADMIN_EMAILS` | Comma-separated list of authorized administrator emails | Optional |

---

## 6. Running the Application

### Using Uvicorn Directly
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 7. Accessing Application Features

Once running, navigate to:
- **Enterprise Web Portal**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive OpenAPI / Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database Table Visualizer**: [http://localhost:8000/database](http://localhost:8000/database)
- **System Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
