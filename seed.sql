-- =========================================================
-- 1. Create database and enable extensions
-- =========================================================
CREATE DATABASE smb_banking;
\ c smb_banking;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- =========================================================
-- 2. Core reference tables
-- =========================================================
-- Customers (business owners / primary contacts)
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    -- e.g. 'CUST-1001'
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    segment TEXT -- MICRO_SMB, SMB, MIDMARKET, etc.
);
-- Businesses
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id TEXT REFERENCES customers(id),
    legal_name TEXT NOT NULL,
    trade_name TEXT,
    entity_type TEXT NOT NULL,
    -- SOLE_PROP, LLC, LLP, CORP, etc.
    tax_id TEXT,
    registration_number TEXT,
    industry_code TEXT,
    country TEXT NOT NULL,
    state TEXT,
    city TEXT,
    address TEXT,
    years_in_business INT
);
-- =========================================================
-- 3. Checking / deposit onboarding tables
-- =========================================================
-- Checking account applications
CREATE TABLE checking_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference TEXT UNIQUE NOT NULL,
    -- e.g. 'CHK-APP-001'
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_id TEXT REFERENCES customers(id),
    product_id TEXT NOT NULL,
    -- 'BUSINESS_CHECKING_STANDARD', etc.
    submitted_at TIMESTAMPTZ DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    -- RECEIVED, IN_REVIEW, DECIDED, etc.
    usage_profile JSONB,
    -- cashflow expectations, etc.
    funding_preferences JSONB -- initial funding prefs
);
-- Owners associated with a checking application (KYB/KYC)
CREATE TABLE checking_owners (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checking_application_id UUID NOT NULL REFERENCES checking_applications(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    dob DATE,
    national_id TEXT,
    ownership_percentage NUMERIC,
    address TEXT
);
-- Documents for checking applications
CREATE TABLE checking_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checking_application_id UUID NOT NULL REFERENCES checking_applications(id) ON DELETE CASCADE,
    doc_type TEXT NOT NULL,
    -- BUSINESS_REG_CERT, TAX_ID_PROOF, OWNER_ID_PROOF, etc.
    status TEXT NOT NULL,
    -- UPLOADED, VALIDATED, REJECTED
    reason_codes TEXT [] DEFAULT '{}',
    uploaded_at TIMESTAMPTZ DEFAULT now()
);
-- Risk scores for checking (if you run risk on deposit onboarding)
CREATE TABLE checking_risk_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checking_application_id UUID NOT NULL REFERENCES checking_applications(id) ON DELETE CASCADE,
    risk_score INT NOT NULL,
    risk_band TEXT NOT NULL,
    -- LOW, MEDIUM, HIGH
    driver_codes TEXT [] NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
-- Checking accounts (core deposit account)
CREATE TABLE checking_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checking_application_id UUID NOT NULL REFERENCES checking_applications(id) ON DELETE CASCADE,
    account_number TEXT NOT NULL,
    routing_number TEXT,
    status TEXT NOT NULL,
    -- ACTIVE, PENDING_FUNDING, CLOSED, etc.
    created_at TIMESTAMPTZ DEFAULT now()
);
-- =========================================================
-- 4. Lending / credit-line tables
-- =========================================================
-- Lending applications (credit-card / line-of-credit / term-loan)
CREATE TABLE lending_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference TEXT UNIQUE NOT NULL,
    -- e.g. 'LEND-APP-001'
    customer_id TEXT REFERENCES customers(id),
    business_id UUID REFERENCES businesses(id),
    checking_account_id UUID REFERENCES checking_accounts(id),
    product_type TEXT NOT NULL,
    -- CREDIT_CARD, REVOLVING_LOC, TERM_LOAN
    requested_amount NUMERIC,
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    submitted_at TIMESTAMPTZ DEFAULT now()
);
-- Transaction summary features derived from checking account for lending
CREATE TABLE lending_transaction_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lending_application_id UUID NOT NULL REFERENCES lending_applications(id) ON DELETE CASCADE,
    checking_account_id UUID NOT NULL REFERENCES checking_accounts(id),
    lookback_months INT NOT NULL,
    period_start DATE,
    period_end DATE,
    total_credits NUMERIC,
    total_debits NUMERIC,
    avg_monthly_revenue NUMERIC,
    revenue_volatility NUMERIC,
    max_single_month_revenue NUMERIC,
    months_with_negative_end_balance INT,
    avg_end_of_month_balance NUMERIC,
    overdraft_count INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
-- External business credit reports (Experian, etc.)
CREATE TABLE business_credit_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lending_application_id UUID NOT NULL REFERENCES lending_applications(id) ON DELETE CASCADE,
    bureau TEXT NOT NULL,
    -- EXPERIAN, EQUIFAX, DNB, etc.
    score INT,
    score_band TEXT,
    delinquencies_count INT,
    delinquencies_last_24m INT,
    bankruptcies_count INT,
    public_records_count INT,
    utilization_ratio NUMERIC,
    last_updated_at TIMESTAMPTZ
);
-- Underwriting results for lending
CREATE TABLE lending_underwriting (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lending_application_id UUID NOT NULL REFERENCES lending_applications(id) ON DELETE CASCADE,
    risk_grade TEXT,
    -- A, B, C, D, E
    pd_estimate NUMERIC,
    -- probability of default
    lgd_estimate NUMERIC,
    -- loss given default
    recommended_max_exposure NUMERIC,
    affordability_band TEXT,
    -- LOW, MEDIUM, HIGH
    key_risk_drivers TEXT [],
    dscr NUMERIC,
    -- debt service coverage ratio
    debt_to_revenue_ratio NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now()
);
-- Offers generated for lending applications
CREATE TABLE lending_offers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lending_application_id UUID NOT NULL REFERENCES lending_applications(id) ON DELETE CASCADE,
    offer_code TEXT UNIQUE NOT NULL,
    -- e.g. 'OFFER-LOC-80K'
    product_type TEXT NOT NULL,
    -- CREDIT_CARD, REVOLVING_LOC, TERM_LOAN
    credit_limit NUMERIC NOT NULL,
    min_credit_limit NUMERIC,
    max_credit_limit NUMERIC,
    apr NUMERIC,
    annual_fee NUMERIC,
    origination_fee NUMERIC,
    tenor_months INT,
    repayment_terms TEXT,
    -- REVOLVING, NET_30, NET_60, etc.
    collateral_required BOOLEAN,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
-- Credit facilities (actual credit-line / card / term-loan accounts)
CREATE TABLE credit_facilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lending_application_id UUID NOT NULL REFERENCES lending_applications(id) ON DELETE CASCADE,
    customer_id TEXT REFERENCES customers(id),
    business_id UUID REFERENCES businesses(id),
    facility_type TEXT NOT NULL,
    -- CARD_ACCOUNT, REVOLVING_LOC, TERM_LOAN
    account_number TEXT NOT NULL,
    credit_limit NUMERIC NOT NULL,
    apr NUMERIC,
    status TEXT NOT NULL,
    -- ACTIVE, PENDING_ACTIVATION, CLOSED
    billing_cycle_day INT,
    drawdown_terms TEXT,
    -- e.g. 'REVOLVING_NET_30'
    created_at TIMESTAMPTZ DEFAULT now()
);
-- =========================================================
-- 5. Generic notifications table (for both checking & lending)
-- =========================================================
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    context_type TEXT NOT NULL,
    -- CHECKING_APPLICATION, LENDING_APPLICATION, CREDIT_FACILITY
    context_id UUID NOT NULL,
    channel TEXT NOT NULL,
    -- EMAIL, SMS, APP
    decision TEXT NOT NULL,
    -- APPROVED, REJECTED
    reason_codes TEXT [] NOT NULL,
    delivery_status TEXT NOT NULL DEFAULT 'SENT',
    created_at TIMESTAMPTZ DEFAULT now()
);
-- =========================================================
-- 6. Seed data
-- =========================================================
-- 6.1 Seed one customer
INSERT INTO customers (id, name, email, phone, segment)
VALUES (
        'CUST-1001',
        'Acme Owner',
        'owner@acme.com',
        '+1-555-123-4567',
        'MICRO_SMB'
    );
-- 6.2 Seed one business (Acme Inc) linked to that customer
INSERT INTO businesses (
        id,
        customer_id,
        legal_name,
        trade_name,
        entity_type,
        tax_id,
        registration_number,
        industry_code,
        country,
        state,
        city,
        address,
        years_in_business
    )
VALUES (
        '11111111-1111-1111-1111-111111111111',
        'CUST-1001',
        'Acme Incorporated',
        'Acme Inc',
        'LLC',
        '99-1234567',
        'REG-ACME-001',
        '5415',
        -- e.g. Computer Systems Design
        'US',
        'CA',
        'San Francisco',
        '123 Market Street, San Francisco, CA 94105',
        3
    );
-- 6.3 Seed one checking application for Acme
INSERT INTO checking_applications (
        id,
        reference,
        business_id,
        customer_id,
        product_id,
        status,
        usage_profile,
        funding_preferences
    )
VALUES (
        '22222222-2222-2222-2222-222222222222',
        'CHK-APP-001',
        '11111111-1111-1111-1111-111111111111',
        'CUST-1001',
        'BUSINESS_CHECKING_STANDARD',
        'DECIDED',
        '{
        "expected_monthly_credits": 45000,
        "expected_monthly_debits": 40000,
        "cash_deposit_volume_per_month": 5000,
        "digital_payment_share": 0.8,
        "minimum_balance_comfort": 10000
     }'::jsonb,
        '{
        "method": "INTERNAL_TRANSFER",
        "amount": 15000
     }'::jsonb
    );
-- 6.4 Seed checking owners
INSERT INTO checking_owners (
        id,
        checking_application_id,
        full_name,
        dob,
        national_id,
        ownership_percentage,
        address
    )
VALUES (
        '33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222',
        'Alice Founder',
        '1985-07-10',
        'ID-AF-12345',
        70,
        '123 Market Street, San Francisco, CA 94105'
    ),
    (
        '33333333-3333-3333-3333-333333333334',
        '22222222-2222-2222-2222-222222222222',
        'Bob CoFounder',
        '1987-03-22',
        'ID-BC-67890',
        30,
        '456 Mission Street, San Francisco, CA 94105'
    );
-- 6.5 Seed checking documents (all validated)
INSERT INTO checking_documents (
        id,
        checking_application_id,
        doc_type,
        status,
        reason_codes
    )
VALUES (
        '44444444-4444-4444-4444-444444444441',
        '22222222-2222-2222-2222-222222222222',
        'BUSINESS_REG_CERT',
        'VALIDATED',
        '{}'
    ),
    (
        '44444444-4444-4444-4444-444444444442',
        '22222222-2222-2222-2222-222222222222',
        'TAX_ID_PROOF',
        'VALIDATED',
        '{}'
    ),
    (
        '44444444-4444-4444-4444-444444444443',
        '22222222-2222-2222-2222-222222222222',
        'OWNER_ID_PROOF',
        'VALIDATED',
        '{}'
    );
-- 6.6 Seed one checking account as if it was opened
INSERT INTO checking_accounts (
        id,
        checking_application_id,
        account_number,
        routing_number,
        status
    )
VALUES (
        '55555555-5555-5555-5555-555555555555',
        '22222222-2222-2222-2222-222222222222',
        '1000000001',
        '011000015',
        'ACTIVE'
    );
-- Optional: a risk score for checking
INSERT INTO checking_risk_scores (
        id,
        checking_application_id,
        risk_score,
        risk_band,
        driver_codes
    )
VALUES (
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        '22222222-2222-2222-2222-222222222222',
        25,
        'LOW',
        ARRAY ['GOOD_KYC', 'LOW_RISK_INDUSTRY']
    );
-- =========================================================
-- 6.7 Seed lending side for the same business & customer
-- =========================================================
-- Lending application referencing the same business, customer, and checking account
INSERT INTO lending_applications (
        id,
        reference,
        customer_id,
        business_id,
        checking_account_id,
        product_type,
        requested_amount,
        status
    )
VALUES (
        '66666666-6666-6666-6666-666666666666',
        'LEND-APP-001',
        'CUST-1001',
        '11111111-1111-1111-1111-111111111111',
        '55555555-5555-5555-5555-555555555555',
        'REVOLVING_LOC',
        80000,
        'IN_REVIEW'
    );
-- Transaction summary for lending (derived from checking account)
INSERT INTO lending_transaction_summaries (
        id,
        lending_application_id,
        checking_account_id,
        lookback_months,
        period_start,
        period_end,
        total_credits,
        total_debits,
        avg_monthly_revenue,
        revenue_volatility,
        max_single_month_revenue,
        months_with_negative_end_balance,
        avg_end_of_month_balance,
        overdraft_count
    )
VALUES (
        '77777777-7777-7777-7777-777777777777',
        '66666666-6666-6666-6666-666666666666',
        '55555555-5555-5555-5555-555555555555',
        12,
        '2024-11-01',
        '2025-10-31',
        450000,
        420000,
        37500,
        0.22,
        60000,
        1,
        18000,
        1
    );
-- Business credit report (Experian) for lending
INSERT INTO business_credit_reports (
        id,
        lending_application_id,
        bureau,
        score,
        score_band,
        delinquencies_count,
        delinquencies_last_24m,
        bankruptcies_count,
        public_records_count,
        utilization_ratio,
        last_updated_at
    )
VALUES (
        '88888888-8888-8888-8888-888888888888',
        '66666666-6666-6666-6666-666666666666',
        'EXPERIAN',
        80,
        'GOOD',
        0,
        0,
        0,
        0,
        0.32,
        now()
    );
-- Underwriting result for lending
INSERT INTO lending_underwriting (
        id,
        lending_application_id,
        risk_grade,
        pd_estimate,
        lgd_estimate,
        recommended_max_exposure,
        affordability_band,
        key_risk_drivers,
        dscr,
        debt_to_revenue_ratio
    )
VALUES (
        '99999999-9999-9999-9999-999999999999',
        '66666666-6666-6666-6666-666666666666',
        'B',
        0.03,
        0.45,
        100000,
        'MEDIUM',
        ARRAY ['GOOD_BUREAU_SCORE', 'HEALTHY_REVENUE', 'LOW_DELINQUENCIES'],
        1.8,
        0.25
    );
-- Offer generated based on underwriting
INSERT INTO lending_offers (
        id,
        lending_application_id,
        offer_code,
        product_type,
        credit_limit,
        min_credit_limit,
        max_credit_limit,
        apr,
        annual_fee,
        origination_fee,
        tenor_months,
        repayment_terms,
        collateral_required,
        notes
    )
VALUES (
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        '66666666-6666-6666-6666-666666666666',
        'OFFER-LOC-80K',
        'REVOLVING_LOC',
        80000,
        50000,
        100000,
        0.14,
        0,
        0.01,
        NULL,
        'REVOLVING',
        FALSE,
        'Based on your stable revenue and good Experian score.'
    );
-- Credit facility opened from that lending application
INSERT INTO credit_facilities (
        id,
        lending_application_id,
        customer_id,
        business_id,
        facility_type,
        account_number,
        credit_limit,
        apr,
        status,
        billing_cycle_day,
        drawdown_terms
    )
VALUES (
        'cccccccc-cccc-cccc-cccc-cccccccccccc',
        '66666666-6666-6666-6666-666666666666',
        'CUST-1001',
        '11111111-1111-1111-1111-111111111111',
        'REVOLVING_LOC',
        '2000000001',
        80000,
        0.14,
        'ACTIVE',
        15,
        'REVOLVING_NET_30'
    );
-- =========================================================
-- 6.8 Seed notifications for both checking and lending
-- =========================================================
-- Checking application approved
INSERT INTO notifications (
        id,
        context_type,
        context_id,
        channel,
        decision,
        reason_codes,
        delivery_status
    )
VALUES (
        'dddddddd-dddd-dddd-dddd-dddddddddddd',
        'CHECKING_APPLICATION',
        '22222222-2222-2222-2222-222222222222',
        'EMAIL',
        'APPROVED',
        ARRAY []::TEXT [],
        'SENT'
    );
-- Lending application approved with reasons (if any)
INSERT INTO notifications (
        id,
        context_type,
        context_id,
        channel,
        decision,
        reason_codes,
        delivery_status
    )
VALUES (
        'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
        'LENDING_APPLICATION',
        '66666666-6666-6666-6666-666666666666',
        'EMAIL',
        'APPROVED',
        ARRAY ['GOOD_BUREAU_SCORE', 'HEALTHY_CASHFLOW'],
        'SENT'
    );