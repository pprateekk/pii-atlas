CREATE SCHEMA IF NOT EXISTS maplecrm;

CREATE TABLE maplecrm.customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone VARCHAR(15),
    street_address TEXT, 
    city TEXT,
    province VARCHAR(2),
    postal_code VARCHAR(7),
    date_of_birth DATE,
    segment VARCHAR(30), -- "smb", or "mid-market", or "enterprise"
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE maplecrm.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES maplecrm.customers(customer_id),
    login_email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    last_login_ip INET,
    locale VARCHAR(5)
);

CREATE TABLE maplecrm.payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES maplecrm.customers(customer_id),
    amount_cad NUMERIC(10,2) NOT NULL CHECK (amount_cad >= 0),
    card_last4 VARCHAR(4),
    payment_token TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'settled'
           CHECK (status IN ('settled','pending','failed','refunded')),
    fraud_flag BOOLEAN NOT NULL DEFAULT FALSE,
    province VARCHAR(2),
    paid_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE maplecrm.support_tickets (
    ticket_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES maplecrm.customers(customer_id),
    subject TEXT NOT NULL,
    body TEXT,
    priority VARCHAR(10) NOT NULL DEFAULT 'medium'
            CHECK (priority IN ('low','medium','high','urgent')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE maplecrm.marketing_prefs (
    pref_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES maplecrm.customers(customer_id),
    email_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
    sms_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    campaign_source VARCHAR(50)
);

CREATE TABLE maplecrm.employees (
    employee_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    sin VARCHAR(11) NOT NULL,   -- '123-456-789' or '123456789'
    work_email TEXT NOT NULL UNIQUE,
    date_of_birth DATE,
    salary NUMERIC(10,2) CHECK (salary >= 0),
    home_address TEXT,
    emergency_contact_phone VARCHAR(20)
);

CREATE TABLE maplecrm.partenaires (
    partenaire_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom_complet TEXT NOT NULL,
    courriel TEXT NOT NULL,
    telephone VARCHAR(20),
    date_naissance DATE,
    ville TEXT
);

CREATE TABLE maplecrm.audit_stub (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event TEXT NOT NULL,
    actor TEXT NOT NULL, -- holds system identifiers, not people
    occurred_at TIMESTAMP NOT NULL DEFAULT NOW()
);
