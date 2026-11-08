-- =====================================================================
-- Airtel Business - Project Udyam Digital Cloud PostgreSQL Schema
-- Tables: product_catalogue, gstin_registry, udyam_registry, smb_leads, orders, admin_messages
-- =====================================================================

-- 1. Product Catalogue
CREATE TABLE IF NOT EXISTS product_catalogue (
    product_id VARCHAR(20) PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    product_name VARCHAR(150) NOT NULL,
    description TEXT,
    unit VARCHAR(50),
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_product_category ON product_catalogue(category);
CREATE INDEX IF NOT EXISTS idx_product_min_emp ON product_catalogue(min_employees);

-- 2. Mock GSTIN Registry (3,534 records)
CREATE TABLE IF NOT EXISTS gstin_registry (
    gstin VARCHAR(20) PRIMARY KEY,
    legal_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255),
    constitution VARCHAR(100),
    principal_place_of_business TEXT,
    state VARCHAR(100),
    registration_date DATE,
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gstin_state ON gstin_registry(state);
CREATE INDEX IF NOT EXISTS idx_gstin_status ON gstin_registry(status);
CREATE INDEX IF NOT EXISTS idx_gstin_trade_name ON gstin_registry(trade_name);

-- 3. Mock Udyam Registry (2,723 records)
CREATE TABLE IF NOT EXISTS udyam_registry (
    udyam_number VARCHAR(30) PRIMARY KEY,
    enterprise_name VARCHAR(255) NOT NULL,
    enterprise_type VARCHAR(50),
    major_activity VARCHAR(50),
    nic_description TEXT,
    state VARCHAR(100),
    city VARCHAR(100),
    date_of_registration DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_udyam_state ON udyam_registry(state);
CREATE INDEX IF NOT EXISTS idx_udyam_city ON udyam_registry(city);
CREATE INDEX IF NOT EXISTS idx_udyam_type ON udyam_registry(enterprise_type);
CREATE INDEX IF NOT EXISTS idx_udyam_activity ON udyam_registry(major_activity);

-- 4. SMB Leads (5,000 historical enterprise leads)
CREATE TABLE IF NOT EXISTS smb_leads (
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leads_city ON smb_leads(city);
CREATE INDEX IF NOT EXISTS idx_leads_btype ON smb_leads(business_type);
CREATE INDEX IF NOT EXISTS idx_leads_gstin ON smb_leads(gstin);
CREATE INDEX IF NOT EXISTS idx_leads_udyam ON smb_leads(udyam_number);
CREATE INDEX IF NOT EXISTS idx_leads_outcome ON smb_leads(outcome);

-- 5. Customer Orders & Milestones (Post-Discovery Journey)
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(30) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- 6. Operations & Admin Real-Time Messages
CREATE TABLE IF NOT EXISTS admin_messages (
    message_id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    customer_name VARCHAR(255) DEFAULT 'Customer',
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_msg_session ON admin_messages(session_id);
