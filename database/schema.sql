-- =========================================================
-- AI Business HQ — Reference Schema
-- Actual execution happens automatically at API startup (CREATE TABLE IF NOT EXISTS),
-- this file is for documentation, audits, and any future manual rollout.
-- =========================================================

-- Registered departments (latest registration from the code matches the API gateway)
CREATE TABLE IF NOT EXISTS departments (
    dept_id      BIGSERIAL PRIMARY KEY,
    key          TEXT UNIQUE NOT NULL,
    title_ar     TEXT,
    title_en     TEXT,
    policy       TEXT DEFAULT 'none',
    workspace_id TEXT DEFAULT 'default',
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- Agents within each department (for reference seeding)
CREATE TABLE IF NOT EXISTS agents (
    agent_id     BIGSERIAL PRIMARY KEY,
    dept_key     TEXT NOT NULL,
    name         TEXT NOT NULL,
    model        TEXT,
    version      TEXT DEFAULT '1.0.0',
    workspace_id TEXT DEFAULT 'default'
);

-- Tasks + their executions
CREATE TABLE IF NOT EXISTS tasks (
    task_id      BIGSERIAL PRIMARY KEY,
    type         TEXT NOT NULL,           -- e.g. run | create_story | build_book | manual
    domain       TEXT NOT NULL,           -- books.content | affiliate | qa | ...
    ref          TEXT,
    input_text   TEXT,
    detail       TEXT,
    status       TEXT DEFAULT 'running',  -- running | success | failed
    created_at   TIMESTAMPTZ DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    workspace_id TEXT DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS task_executions (
    exec_id      BIGSERIAL PRIMARY KEY,
    task_id      BIGINT NOT NULL REFERENCES tasks(task_id),
    agent        TEXT,
    started_at   TIMESTAMPTZ DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    status       TEXT DEFAULT 'running',  -- running | success | failed | needs_approval
    tokens_used  INTEGER DEFAULT 0,
    detail       TEXT,
    workspace_id TEXT DEFAULT 'default'
);

-- Opportunities logged from intelligence/affiliate
CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id BIGSERIAL PRIMARY KEY,
    sector       TEXT NOT NULL,           -- intelligence | affiliate | books
    title        TEXT NOT NULL,
    niche        TEXT,
    score        DOUBLE PRECISION,
    status       TEXT DEFAULT 'new',      -- new | watching | pursuing | archived
    payload      TEXT,                    -- full JSON
    workspace_id TEXT DEFAULT 'default',
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Product/book lifecycle (opportunity → candidate → story → pdf → qa → approved → published)
CREATE TABLE IF NOT EXISTS products (
    product_id   BIGSERIAL PRIMARY KEY,
    slug         TEXT UNIQUE NOT NULL,
    title        TEXT NOT NULL,
    status       TEXT DEFAULT 'story',    -- candidate|story|images|pdf|qa|approved|published
    pdf_path     TEXT,
    cover_path   TEXT,
    final_file   TEXT,
    workspace_id TEXT DEFAULT 'default',
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- Reports (PDF/MD)
CREATE TABLE IF NOT EXISTS reports (
    report_id    BIGSERIAL PRIMARY KEY,
    kind         TEXT DEFAULT 'md',
    path         TEXT,
    title        TEXT,
    content      TEXT,
    workspace_id TEXT DEFAULT 'default',
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Human approval gates
CREATE TABLE IF NOT EXISTS approvals (
    approval_id  BIGSERIAL PRIMARY KEY,
    kind         TEXT NOT NULL,           -- e.g. etsy_publish
    ref          TEXT NOT NULL,
    status       TEXT DEFAULT 'pending',  -- pending | approved | rejected
    note         TEXT,
    decided_at   TIMESTAMPTZ,
    workspace_id TEXT DEFAULT 'default',
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Audit log: every significant action in the company
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id       BIGSERIAL PRIMARY KEY,
    task_id      BIGINT,
    actor        TEXT NOT NULL,           -- ceo | qa | books.content | scheduler | founder …
    action       TEXT NOT NULL,
    detail       TEXT,
    workspace_id TEXT DEFAULT 'default',
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- Budget and autonomy
CREATE TABLE IF NOT EXISTS budgets (
    budget_id    BIGSERIAL PRIMARY KEY,
    workspace_id TEXT UNIQUE DEFAULT 'default',
    monthly_limit_usd DOUBLE PRECISION DEFAULT 50.0,
    used_usd     DOUBLE PRECISION DEFAULT 0.0
);

-- System settings (autonomy_level …)
CREATE TABLE IF NOT EXISTS settings (
    key          TEXT PRIMARY KEY,
    value        TEXT,
    updated_at   TIMESTAMPTZ DEFAULT now()
);
