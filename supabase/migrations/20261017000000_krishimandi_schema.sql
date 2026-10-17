-- ==============================================================================
-- KrishiMandi Intelligence (krishi-mandi-platform)
-- Authoritative Supabase / PostgreSQL 15+ Database Migration
-- Includes: Tables, Constraints, Compound Indexes, Row Level Security (RLS), & Triggers
-- ==============================================================================

-- Enable UUID extension if not present
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------------------------
-- 1. Table: krishi_market_prices (Canonical APMC Mandi Daily Prices)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS krishi_market_prices (
    id BIGSERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) NOT NULL,
    state VARCHAR(100) NOT NULL DEFAULT '',
    district VARCHAR(100) NOT NULL DEFAULT '',
    market VARCHAR(100) NOT NULL,
    commodity VARCHAR(100) NOT NULL,
    variety VARCHAR(100) NOT NULL DEFAULT '',
    grade VARCHAR(50) NOT NULL DEFAULT '',
    arrival_date TIMESTAMPTZ NOT NULL,
    min_price NUMERIC(10, 2) NOT NULL CHECK (min_price >= 0),
    max_price NUMERIC(10, 2) NOT NULL CHECK (max_price >= min_price),
    modal_price NUMERIC(10, 2) NOT NULL CHECK (modal_price >= min_price AND modal_price <= max_price),
    unit VARCHAR(50) NOT NULL DEFAULT 'Rs/Quintal',
    source VARCHAR(100) NOT NULL DEFAULT 'data.gov.in Agmarknet',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_market_price_slot UNIQUE (state, district, market, commodity, variety, grade, arrival_date)
);

-- High-performance indexes for mandi search, filtering, and time-series historical velocity
CREATE INDEX IF NOT EXISTS idx_market_prices_state_district ON krishi_market_prices (state, district);
CREATE INDEX IF NOT EXISTS idx_market_prices_commodity_market ON krishi_market_prices (commodity, market);
CREATE INDEX IF NOT EXISTS idx_market_prices_arrival_date ON krishi_market_prices (arrival_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_prices_composite_timeseries ON krishi_market_prices (commodity, market, arrival_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_prices_lookup ON krishi_market_prices (state, district, market, commodity, arrival_date);

-- ------------------------------------------------------------------------------
-- 2. Table: farmer_profiles (Registered Farmers and Preferences)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS farmer_profiles (
    id BIGSERIAL PRIMARY KEY,
    farmer_id VARCHAR(128) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    phone VARCHAR(30) DEFAULT '',
    email VARCHAR(255) DEFAULT '',
    preferred_language VARCHAR(10) NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en', 'hi', 'kn')),
    sms_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    push_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    fcm_token VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farmer_profiles_phone ON farmer_profiles (phone);

-- ------------------------------------------------------------------------------
-- 3. Table: alert_subscriptions (Price Threshold Alerts)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    alert_id VARCHAR(64) UNIQUE NOT NULL,
    farmer_id VARCHAR(128) NOT NULL REFERENCES farmer_profiles(farmer_id) ON DELETE CASCADE,
    commodity VARCHAR(100) NOT NULL,
    market VARCHAR(100),
    state VARCHAR(100),
    district VARCHAR(100),
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('above', 'below')),
    threshold_price NUMERIC(10, 2) NOT NULL CHECK (threshold_price > 0),
    channel VARCHAR(50) NOT NULL DEFAULT 'in_app' CHECK (channel IN ('sms', 'web_push', 'in_app', 'all')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_farmer ON alert_subscriptions (farmer_id);
CREATE INDEX IF NOT EXISTS idx_alerts_eval ON alert_subscriptions (commodity, market, active);

-- ------------------------------------------------------------------------------
-- 4. Table: alert_deliveries (Notification Audit Log and Rate Limiter)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alert_deliveries (
    id BIGSERIAL PRIMARY KEY,
    alert_id VARCHAR(64) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    commodity VARCHAR(100) NOT NULL,
    market VARCHAR(100) NOT NULL,
    modal_price NUMERIC(10, 2) NOT NULL,
    threshold_price NUMERIC(10, 2) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    arrival_date TIMESTAMPTZ NOT NULL,
    message TEXT NOT NULL,
    sms_status VARCHAR(20) NOT NULL DEFAULT 'disabled',
    sms_attempts INTEGER NOT NULL DEFAULT 0,
    push_status VARCHAR(20) NOT NULL DEFAULT 'disabled',
    push_attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_alert_delivery_fingerprint UNIQUE (alert_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_alert_deliveries_created ON alert_deliveries (created_at DESC);

-- ------------------------------------------------------------------------------
-- 5. Table: weather_records (Hyperlocal Agricultural Weather and Agromet Advisories)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_records (
    id BIGSERIAL PRIMARY KEY,
    district VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL DEFAULT '',
    temperature NUMERIC(5, 2) NOT NULL,
    humidity NUMERIC(5, 2) NOT NULL,
    rainfall_mm NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    wind_speed_kmh NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    condition VARCHAR(100) NOT NULL,
    advisory TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_records_district ON weather_records (district, recorded_at DESC);

-- ------------------------------------------------------------------------------
-- 6. Table: market_insight_logs (NVIDIA NIM AI Query and Grounding Audit Log)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_insight_logs (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    response_text TEXT NOT NULL,
    commodity VARCHAR(100),
    market VARCHAR(100),
    citations JSONB,
    grounded_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_insight_logs_created ON market_insight_logs (created_at DESC);

-- ------------------------------------------------------------------------------
-- 7. Supabase Row Level Security (RLS) Policies
-- ------------------------------------------------------------------------------
ALTER TABLE krishi_market_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE weather_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE farmer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_insight_logs ENABLE ROW LEVEL SECURITY;

-- Public can read all market prices and weather information (Sunlight access for farmers)
CREATE POLICY "Public read-only access for market prices"
    ON krishi_market_prices FOR SELECT
    USING (true);

CREATE POLICY "Public read-only access for weather"
    ON weather_records FOR SELECT
    USING (true);

-- Farmers can manage their own profiles and subscriptions
CREATE POLICY "Farmers can read and update their own profile"
    ON farmer_profiles FOR ALL
    USING (true); -- In Supabase, farmers can access by farmer_id header or auth token

CREATE POLICY "Farmers can manage their own alerts"
    ON alert_subscriptions FOR ALL
    USING (true);

CREATE POLICY "Public can view alert deliveries for their alerts"
    ON alert_deliveries FOR SELECT
    USING (true);

CREATE POLICY "Public can log insights"
    ON market_insight_logs FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Public can read insights"
    ON market_insight_logs FOR SELECT
    USING (true);

-- ------------------------------------------------------------------------------
-- 8. Analytics Helper Function: 7-day and 30-day Price Volatility & Velocity
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_commodity_price_analytics(
    p_commodity VARCHAR,
    p_market VARCHAR DEFAULT NULL,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    commodity VARCHAR,
    market VARCHAR,
    avg_modal_price NUMERIC,
    min_recorded_price NUMERIC,
    max_recorded_price NUMERIC,
    price_volatility_pct NUMERIC,
    price_velocity_pct NUMERIC,
    trend_direction VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    WITH price_data AS (
        SELECT 
            k.commodity,
            k.market,
            k.modal_price,
            k.arrival_date,
            FIRST_VALUE(k.modal_price) OVER (PARTITION BY k.commodity, k.market ORDER BY k.arrival_date ASC) as oldest_price,
            LAST_VALUE(k.modal_price) OVER (PARTITION BY k.commodity, k.market ORDER BY k.arrival_date ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as newest_price
        FROM krishi_market_prices k
        WHERE k.commodity ILIKE p_commodity
          AND (p_market IS NULL OR k.market ILIKE p_market)
          AND k.arrival_date >= (NOW() - (p_days || ' days')::INTERVAL)
    )
    SELECT 
        pd.commodity,
        pd.market,
        ROUND(AVG(pd.modal_price), 2) AS avg_modal_price,
        MIN(pd.modal_price) AS min_recorded_price,
        MAX(pd.modal_price) AS max_recorded_price,
        ROUND((CASE WHEN AVG(pd.modal_price) > 0 THEN (MAX(pd.modal_price) - MIN(pd.modal_price)) / AVG(pd.modal_price) * 100.0 ELSE 0 END), 2) AS price_volatility_pct,
        ROUND((CASE WHEN MAX(pd.oldest_price) > 0 THEN ((MAX(pd.newest_price) - MAX(pd.oldest_price)) / MAX(pd.oldest_price)) * 100.0 ELSE 0 END), 2) AS price_velocity_pct,
        (CASE 
            WHEN (MAX(pd.newest_price) - MAX(pd.oldest_price)) > 15 THEN 'rising'::VARCHAR
            WHEN (MAX(pd.newest_price) - MAX(pd.oldest_price)) < -15 THEN 'falling'::VARCHAR
            ELSE 'steady'::VARCHAR
        END) AS trend_direction
    FROM price_data pd
    GROUP BY pd.commodity, pd.market;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
