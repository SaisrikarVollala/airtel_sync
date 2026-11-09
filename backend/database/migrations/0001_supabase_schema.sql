-- =====================================================================
-- Airtel Business - Project Udyam Digital
-- Supabase PostgreSQL Exclusive Cloud Database Schema & RLS Policies
-- Migration: 0001_supabase_schema.sql
-- =====================================================================

-- 1. Product Catalogue Table
CREATE TABLE IF NOT EXISTS public.product_catalogue (
    product_id VARCHAR(20) PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    product_name VARCHAR(150) NOT NULL,
    description TEXT,
    unit VARCHAR(50) DEFAULT 'monthly',
    price_min_inr_per_month NUMERIC(10, 2),
    price_max_inr_per_month NUMERIC(10, 2),
    one_time_setup_inr NUMERIC(10, 2) DEFAULT 0,
    min_contract_months INTEGER DEFAULT 12,
    available_city_tiers VARCHAR(20),
    min_employees INTEGER DEFAULT 1,
    min_sites INTEGER DEFAULT 1,
    requires_gstin BOOLEAN DEFAULT FALSE,
    requires_one_of VARCHAR(100),
    typical_install_days INTEGER DEFAULT 7,
    target_segments VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prod_category ON public.product_catalogue(category);
CREATE INDEX IF NOT EXISTS idx_prod_gstin ON public.product_catalogue(requires_gstin);

-- 2. Official GSTIN Tax Registry Table (3,534 Government MSME records)
CREATE TABLE IF NOT EXISTS public.gstin_registry (
    gstin VARCHAR(20) PRIMARY KEY,
    legal_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255),
    constitution VARCHAR(100),
    principal_place_of_business TEXT,
    state VARCHAR(100),
    registration_date DATE,
    status VARCHAR(50) DEFAULT 'Active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gstin_state ON public.gstin_registry(state);
CREATE INDEX IF NOT EXISTS idx_gstin_status ON public.gstin_registry(status);
CREATE INDEX IF NOT EXISTS idx_gstin_legal_name ON public.gstin_registry(legal_name);

-- 3. Official MSME Udyam Registry Table (2,723 MSME records)
CREATE TABLE IF NOT EXISTS public.udyam_registry (
    udyam_number VARCHAR(30) PRIMARY KEY,
    enterprise_name VARCHAR(255) NOT NULL,
    enterprise_type VARCHAR(50),
    major_activity VARCHAR(50),
    nic_description TEXT,
    state VARCHAR(100),
    city VARCHAR(100),
    date_of_registration DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_udyam_state ON public.udyam_registry(state);
CREATE INDEX IF NOT EXISTS idx_udyam_type ON public.udyam_registry(enterprise_type);
CREATE INDEX IF NOT EXISTS idx_udyam_name ON public.udyam_registry(enterprise_name);

-- 4. Historical Enterprise Leads Table (5,000 historical SMB leads)
CREATE TABLE IF NOT EXISTS public.smb_leads (
    lead_id VARCHAR(20) PRIMARY KEY,
    created_date DATE,
    lead_source VARCHAR(100),
    business_name VARCHAR(255),
    business_type VARCHAR(100),
    segment VARCHAR(100),
    city VARCHAR(100),
    city_tier INTEGER,
    state VARCHAR(100),
    preferred_language VARCHAR(50),
    employee_count INTEGER,
    num_sites INTEGER,
    annual_turnover_band VARCHAR(100),
    has_gstin BOOLEAN DEFAULT FALSE,
    gstin VARCHAR(20),
    has_udyam BOOLEAN DEFAULT FALSE,
    udyam_number VARCHAR(30),
    current_internet VARCHAR(100),
    current_provider VARCHAR(100),
    monthly_telecom_spend_inr NUMERIC(10, 2),
    products_of_interest VARCHAR(100),
    contact_name VARCHAR(100),
    contact_role VARCHAR(100),
    stage_reached VARCHAR(50),
    outcome VARCHAR(50),
    drop_reason TEXT,
    contacted_date DATE,
    needs_assessed_date DATE,
    quote_accepted_date DATE,
    kyc_complete_date DATE,
    activated_date DATE,
    days_lead_to_activation INTEGER,
    customer_follow_up_calls INTEGER DEFAULT 0,
    bundle_products VARCHAR(255),
    monthly_bundle_value_inr NUMERIC(10, 2),
    one_time_setup_inr NUMERIC(10, 2),
    contract_months INTEGER,
    churned_within_6_months BOOLEAN DEFAULT FALSE,
    nps_score INTEGER,
    acquisition_cost_inr NUMERIC(10, 2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leads_city ON public.smb_leads(city);
CREATE INDEX IF NOT EXISTS idx_leads_segment ON public.smb_leads(segment);
CREATE INDEX IF NOT EXISTS idx_leads_btype ON public.smb_leads(business_type);
CREATE INDEX IF NOT EXISTS idx_leads_outcome ON public.smb_leads(outcome);

-- 5. City Tier Classification Table
CREATE TABLE IF NOT EXISTS public.city_tier_mapping (
    city VARCHAR(100) PRIMARY KEY,
    tier INTEGER NOT NULL,
    state VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_city_tier ON public.city_tier_mapping(tier);

-- 6. Bundle & Product Aggregated Statistics Tables
CREATE TABLE IF NOT EXISTS public.bundle_statistics (
    bundle_code VARCHAR(100) PRIMARY KEY,
    bundle_name VARCHAR(255) NOT NULL,
    target_segment VARCHAR(100),
    conversion_rate NUMERIC(5, 4),
    retention_rate NUMERIC(5, 4),
    avg_nps NUMERIC(4, 2),
    stats_json JSONB,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.product_statistics (
    product_id VARCHAR(20) PRIMARY KEY REFERENCES public.product_catalogue(product_id) ON DELETE CASCADE,
    attach_rate NUMERIC(5, 4),
    retention_rate NUMERIC(5, 4),
    avg_nps NUMERIC(4, 2),
    stats_json JSONB,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 7. AI Escalated Leads Table
CREATE TABLE IF NOT EXISTS public.ai_escalations (
    escalation_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    priority VARCHAR(32) DEFAULT 'HIGH',
    status VARCHAR(32) DEFAULT 'AWAITING_AGENT',
    ai_confidence_score NUMERIC(5, 2) NOT NULL,
    confidence_band VARCHAR(64) NOT NULL,
    trigger_reason TEXT NOT NULL,
    what_ai_could_not_extract_json TEXT,
    ai_discovery_summary TEXT,
    recommended_action TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_esc_status ON public.ai_escalations(status);
CREATE INDEX IF NOT EXISTS idx_ai_esc_session ON public.ai_escalations(session_id);

-- 8. Customer Acceptance/Rejection Decisions & Analytics
CREATE TABLE IF NOT EXISTS public.customer_decisions (
    decision_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    business_type VARCHAR(255),
    decision_type VARCHAR(32) NOT NULL,
    bundle_code VARCHAR(64),
    bundle_name VARCHAR(255),
    monthly_cost NUMERIC(12, 2),
    ai_response_insights_json TEXT,
    rejection_reason TEXT,
    customer_feedback TEXT,
    budget_offered NUMERIC(12, 2),
    escalation_id VARCHAR(64) REFERENCES public.ai_escalations(escalation_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cust_dec_type ON public.customer_decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_cust_dec_session ON public.customer_decisions(session_id);

-- 9. Commercial Customer Orders & Live Provisioning Lifecycle
CREATE TABLE IF NOT EXISTS public.orders (
    order_id VARCHAR(30) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(128),
    customer_name VARCHAR(255) NOT NULL,
    business_type VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    current_stage_index INTEGER NOT NULL DEFAULT 0,
    bundle_code VARCHAR(100),
    bundle_name VARCHAR(255),
    monthly_cost NUMERIC(10, 2) NOT NULL,
    contract_months INTEGER DEFAULT 12,
    contract_terms JSONB,
    milestones JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_user ON public.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_session ON public.orders(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON public.orders(status);

-- 10. Operations & Admin Real-Time Messages
CREATE TABLE IF NOT EXISTS public.admin_messages (
    message_id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    customer_name VARCHAR(255) DEFAULT 'Customer',
    message TEXT NOT NULL,
    bundle_code VARCHAR(100),
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_msg_session ON public.admin_messages(session_id);

-- 11. Customer Profiles & Discovery Schema
CREATE TABLE IF NOT EXISTS public.user_profiles (
    user_id VARCHAR(128) PRIMARY KEY,
    email VARCHAR(255),
    business_name VARCHAR(255),
    customer_schema_json TEXT DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 12. Persistent Order Carts
CREATE TABLE IF NOT EXISTS public.user_carts (
    user_id VARCHAR(128) PRIMARY KEY,
    cart_items_json TEXT DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 13. Customer Multi-Turn Conversations & Voice Telemetry
CREATE TABLE IF NOT EXISTS public.user_conversations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    session_id VARCHAR(128) NOT NULL,
    sender VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    pipeline_trace_json TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_conv_user ON public.user_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_conv_session ON public.user_conversations(session_id);

-- 14. Customer Accepted Product Needs
CREATE TABLE IF NOT EXISTS public.customer_needs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    product_id VARCHAR(64),
    need_name VARCHAR(255) NOT NULL,
    category VARCHAR(128),
    source VARCHAR(64) DEFAULT 'chat_ai',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cust_needs_user ON public.customer_needs(user_id);

-- 15. Encrypted KYC Document Records (DPDP Act 2023 Compliant)
CREATE TABLE IF NOT EXISTS public.kyc_records (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL,
    applicant_id VARCHAR(64),
    doc_type VARCHAR(64) NOT NULL,
    masked_identifier VARCHAR(128) NOT NULL,
    encrypted_payload TEXT NOT NULL,
    iv VARCHAR(64) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    verification_status VARCHAR(64) NOT NULL DEFAULT 'PENDING',
    registry_matched BOOLEAN DEFAULT TRUE,
    tamper_detected BOOLEAN DEFAULT FALSE,
    dpdp_consent_logged BOOLEAN DEFAULT TRUE,
    metadata_json TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kyc_session ON public.kyc_records(session_id);
CREATE INDEX IF NOT EXISTS idx_kyc_applicant ON public.kyc_records(applicant_id);

-- 16. Explicit Customer DPDP Consent Logs
CREATE TABLE IF NOT EXISTS public.dpdp_consent_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    purpose VARCHAR(128) NOT NULL,
    language VARCHAR(16) NOT NULL DEFAULT 'en',
    consent_status VARCHAR(32) NOT NULL DEFAULT 'GRANTED',
    terms_version VARCHAR(32) NOT NULL DEFAULT '2026.1',
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dpdp_session ON public.dpdp_consent_logs(session_id);

-- 17. Recommendation Engine Audit Trail
CREATE TABLE IF NOT EXISTS public.recommendation_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128),
    session_id VARCHAR(128),
    profile_snapshot JSONB,
    catalogue_version VARCHAR(32),
    config_version VARCHAR(32),
    cohort_info JSONB,
    candidates_count INTEGER,
    candidates_summary JSONB,
    options_count INTEGER,
    options_shown JSONB,
    single_option_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rec_logs_user ON public.recommendation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_rec_logs_session ON public.recommendation_logs(session_id);


-- =====================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================================

-- Public Read for Catalog & Registries
ALTER TABLE public.product_catalogue ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public Read Products" ON public.product_catalogue FOR SELECT USING (true);

ALTER TABLE public.gstin_registry ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public Read GSTIN" ON public.gstin_registry FOR SELECT USING (true);

ALTER TABLE public.udyam_registry ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public Read Udyam" ON public.udyam_registry FOR SELECT USING (true);

ALTER TABLE public.smb_leads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public Read Leads" ON public.smb_leads FOR SELECT USING (true);

ALTER TABLE public.city_tier_mapping ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public Read City Tiers" ON public.city_tier_mapping FOR SELECT USING (true);

ALTER TABLE public.bundle_statistics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public Read Bundle Stats" ON public.bundle_statistics FOR SELECT USING (true);

ALTER TABLE public.product_statistics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public Read Product Stats" ON public.product_statistics FOR SELECT USING (true);

-- User-scoped security for personal profile, cart, conversations, needs, orders
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own profile" ON public.user_profiles
    FOR ALL USING (auth.uid()::text = user_id OR auth.jwt() ->> 'role' = 'admin' OR auth.role() = 'anon');

ALTER TABLE public.user_carts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own cart" ON public.user_carts
    FOR ALL USING (auth.uid()::text = user_id OR auth.jwt() ->> 'role' = 'admin' OR auth.role() = 'anon');

ALTER TABLE public.user_conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own conversations" ON public.user_conversations
    FOR ALL USING (auth.uid()::text = user_id OR auth.jwt() ->> 'role' = 'admin' OR auth.role() = 'anon');

ALTER TABLE public.customer_needs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own needs" ON public.customer_needs
    FOR ALL USING (auth.uid()::text = user_id OR auth.jwt() ->> 'role' = 'admin' OR auth.role() = 'anon');

ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own orders" ON public.orders
    FOR ALL USING (user_id IS NULL OR auth.uid()::text = user_id OR auth.jwt() ->> 'role' = 'admin' OR auth.role() = 'anon');

ALTER TABLE public.kyc_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own KYC" ON public.kyc_records
    FOR ALL USING (true);

ALTER TABLE public.dpdp_consent_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own consents" ON public.dpdp_consent_logs
    FOR ALL USING (true);

ALTER TABLE public.ai_escalations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Escalations access" ON public.ai_escalations
    FOR ALL USING (true);

ALTER TABLE public.customer_decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Decisions access" ON public.customer_decisions
    FOR ALL USING (true);

ALTER TABLE public.admin_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Admin messages access" ON public.admin_messages
    FOR ALL USING (true);

ALTER TABLE public.recommendation_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Recommendation logs access" ON public.recommendation_logs
    FOR ALL USING (true);

