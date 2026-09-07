-- ==============================================================================
-- Plutio / Insights PostgreSQL Schema for Supabase
-- Paste and execute this entire script in Supabase SQL Editor
-- ==============================================================================

-- 1. Feeds
CREATE TABLE IF NOT EXISTS feeds (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    feed_type TEXT,
    last_post TEXT,
    item_count INTEGER,
    last_checked TEXT
);

-- 2. Episodes / Sources
CREATE TABLE IF NOT EXISTS episodes (
    id SERIAL PRIMARY KEY,
    feed_id INTEGER REFERENCES feeds(id) ON DELETE SET NULL,
    url TEXT UNIQUE,
    title TEXT,
    transcript TEXT,
    summary TEXT,
    action_items TEXT,
    status TEXT,
    published TEXT,
    processed_at TEXT,
    channel TEXT
);

-- 3. JIRA Tickets
CREATE TABLE IF NOT EXISTS jira_tickets (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL,
    action_item TEXT,
    ticket_key TEXT,
    ticket_url TEXT
);

-- 4. Articles
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL,
    topic TEXT,
    style TEXT,
    content TEXT,
    created_at TEXT,
    brief_id INTEGER,
    brief_run_id INTEGER,
    source_type TEXT
);

-- 5. Social Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    platform TEXT,
    content TEXT,
    image_url TEXT,
    created_at TEXT,
    used INTEGER DEFAULT 0
);

-- 6. Social Accounts (Multi-login per platform)
CREATE TABLE IF NOT EXISTS social_accounts (
    id SERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    external_id TEXT,
    label TEXT,
    handle TEXT,
    display_name TEXT,
    avatar_url TEXT,
    is_default INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    updated_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_accounts_identity ON social_accounts(platform, external_id);
CREATE INDEX IF NOT EXISTS idx_social_accounts_platform ON social_accounts(platform, is_default DESC, id);

-- 7. Platform Tokens
CREATE TABLE IF NOT EXISTS linkedin_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT,
    refresh_token TEXT,
    expires_at TEXT,
    member_id TEXT,
    user_urn TEXT,
    display_name TEXT,
    email TEXT,
    created_at TEXT,
    updated_at TEXT,
    account_id INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS threads_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT,
    expires_at TEXT,
    user_id TEXT,
    username TEXT,
    display_name TEXT,
    profile_picture_url TEXT,
    created_at TEXT,
    updated_at TEXT,
    account_id INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS facebook_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT,
    expires_at TEXT,
    user_id TEXT,
    user_name TEXT,
    page_id TEXT,
    page_name TEXT,
    page_access_token TEXT,
    group_ids TEXT,
    created_at TEXT,
    updated_at TEXT,
    account_id INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS twitter_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT,
    refresh_token TEXT,
    expires_at TEXT,
    user_id TEXT,
    username TEXT,
    display_name TEXT,
    created_at TEXT,
    updated_at TEXT,
    account_id INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS instagram_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT,
    expires_at TEXT,
    user_id TEXT,
    ig_user_id TEXT,
    username TEXT,
    display_name TEXT,
    profile_picture_url TEXT,
    account_type TEXT,
    created_at TEXT,
    updated_at TEXT,
    account_id INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL
);

-- 8. Standalone Posts (Command Center)
CREATE TABLE IF NOT EXISTS standalone_posts (
    id SERIAL PRIMARY KEY,
    source_type TEXT,
    source_content TEXT,
    platform TEXT,
    content TEXT,
    image_url TEXT,
    created_at TEXT,
    used INTEGER DEFAULT 0,
    repost INTEGER DEFAULT 0,
    ig_post_type TEXT,
    media_items TEXT,
    ig_user_tags TEXT,
    brief_id INTEGER,
    brief_run_id INTEGER,
    account_id INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL
);

-- 9. Scheduled Posts Queue
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id SERIAL PRIMARY KEY,
    social_post_id INTEGER REFERENCES social_posts(id) ON DELETE CASCADE,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    standalone_post_id INTEGER REFERENCES standalone_posts(id) ON DELETE CASCADE,
    post_type TEXT,
    platform TEXT DEFAULT 'linkedin',
    scheduled_for TEXT,
    status TEXT DEFAULT 'pending',
    linkedin_post_urn TEXT,
    error_message TEXT,
    created_at TEXT,
    posted_at TEXT,
    retry_count INTEGER DEFAULT 0,
    account_id INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL
);

-- 10. Scheduling & Slots
CREATE TABLE IF NOT EXISTS schedule_settings (
    id SERIAL PRIMARY KEY,
    setting_key TEXT UNIQUE,
    setting_value TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS schedule_time_slots (
    id SERIAL PRIMARY KEY,
    day_of_week INTEGER,
    time_slot TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS time_slot_platforms (
    slot_id INTEGER NOT NULL REFERENCES schedule_time_slots(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    PRIMARY KEY (slot_id, platform)
);

CREATE TABLE IF NOT EXISTS platform_daily_limits (
    platform TEXT PRIMARY KEY,
    max_posts_per_day INTEGER DEFAULT 0
);

-- 11. URL Sources
CREATE TABLE IF NOT EXISTS url_sources (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    description TEXT,
    content TEXT,
    og_image TEXT,
    created_at TEXT,
    last_used_at TEXT
);

-- 12. Media Uploads & Prompt Library
CREATE TABLE IF NOT EXISTS uploaded_images (
    id SERIAL PRIMARY KEY,
    filename TEXT,
    url TEXT UNIQUE,
    storage TEXT,
    size INTEGER,
    created_at TEXT,
    media_type TEXT DEFAULT 'image'
);

CREATE TABLE IF NOT EXISTS prompt_library (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS generated_thumbnails (
    id SERIAL PRIMARY KEY,
    youtube_url TEXT,
    video_id TEXT,
    title TEXT,
    channel TEXT,
    aspect TEXT,
    style TEXT,
    prompt TEXT,
    image_relpath TEXT,
    created_at TEXT
);

-- 13. Users & Authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    google_id TEXT,
    avatar_url TEXT,
    auth_provider TEXT DEFAULT 'local',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 14. Activity Log & Usage Events
CREATE TABLE IF NOT EXISTS activity_log (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT,
    action TEXT NOT NULL,
    method TEXT,
    path TEXT,
    endpoint TEXT,
    target TEXT,
    status_code INTEGER,
    ip TEXT,
    user_agent TEXT,
    duration_ms INTEGER,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_activity_log_ts ON activity_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_user ON activity_log(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_action ON activity_log(action, ts DESC);

CREATE TABLE IF NOT EXISTS usage_events (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mode TEXT NOT NULL,
    category TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    audio_seconds REAL NOT NULL DEFAULT 0,
    images INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_events_ts ON usage_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_mode ON usage_events(mode, ts DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_category ON usage_events(category, ts DESC);

-- 15. Content Agent Briefs & Runs
CREATE TABLE IF NOT EXISTS content_briefs (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    instructions TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'posts',
    platforms TEXT,
    tone TEXT DEFAULT 'professional',
    posts_per_platform INTEGER DEFAULT 3,
    article_count INTEGER DEFAULT 0,
    article_style TEXT DEFAULT 'blog',
    focus_sources TEXT,
    must_include_keywords TEXT,
    audience_persona TEXT,
    use_web_search INTEGER DEFAULT 1,
    use_saved_sources INTEGER DEFAULT 1,
    cadence TEXT NOT NULL DEFAULT 'manual',
    run_time TEXT,
    run_days TEXT,
    next_run_at TEXT,
    enabled INTEGER DEFAULT 1,
    auto_queue INTEGER DEFAULT 0,
    review_window_hours INTEGER DEFAULT 24,
    max_sources_per_run INTEGER DEFAULT 5,
    max_cost_usd REAL DEFAULT 0.5,
    max_drafts_per_run INTEGER DEFAULT 30,
    last_run_at TEXT,
    last_run_status TEXT,
    created_at TEXT,
    updated_at TEXT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS content_brief_runs (
    id SERIAL PRIMARY KEY,
    brief_id INTEGER NOT NULL REFERENCES content_briefs(id) ON DELETE CASCADE,
    trigger TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT,
    finished_at TEXT,
    sources_found INTEGER DEFAULT 0,
    sources_used INTEGER DEFAULT 0,
    posts_created INTEGER DEFAULT 0,
    articles_created INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    error_message TEXT,
    log TEXT
);
CREATE INDEX IF NOT EXISTS idx_brief_runs_brief ON content_brief_runs(brief_id, started_at DESC);

-- 16. Content Library
CREATE TABLE IF NOT EXISTS library_roots (
    id SERIAL PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    label TEXT,
    role TEXT NOT NULL DEFAULT 'source',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS library_scans (
    id SERIAL PRIMARY KEY,
    root_id INTEGER NOT NULL REFERENCES library_roots(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'scanning',
    phase TEXT,
    files_total INTEGER DEFAULT 0,
    events_total INTEGER DEFAULT 0,
    events_done INTEGER DEFAULT 0,
    bytes_downloaded INTEGER DEFAULT 0,
    stats TEXT,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS library_files (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES library_scans(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    rel_path TEXT,
    name TEXT,
    ext TEXT,
    kind TEXT,
    size INTEGER DEFAULT 0,
    mtime REAL,
    materialized INTEGER DEFAULT 0,
    captured_at TEXT,
    date_source TEXT,
    year INTEGER,
    month INTEGER,
    event_key TEXT,
    dup_group INTEGER DEFAULT 1,
    category TEXT,
    subcategory TEXT,
    confidence REAL DEFAULT 0,
    classified_by TEXT,
    caption TEXT,
    notes TEXT,
    previous_category TEXT,
    pinned INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_lib_files_scan ON library_files(scan_id);
CREATE INDEX IF NOT EXISTS idx_lib_files_cat ON library_files(scan_id, category);
CREATE INDEX IF NOT EXISTS idx_lib_files_year ON library_files(scan_id, year);
CREATE INDEX IF NOT EXISTS idx_lib_files_event ON library_files(scan_id, event_key);
CREATE INDEX IF NOT EXISTS idx_lib_files_dup ON library_files(scan_id, dup_group);

CREATE TABLE IF NOT EXISTS library_events (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES library_scans(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    directory TEXT,
    file_count INTEGER DEFAULT 0,
    total_bytes INTEGER DEFAULT 0,
    year INTEGER,
    date_start TEXT,
    date_end TEXT,
    category TEXT,
    confidence REAL DEFAULT 0,
    classified_by TEXT,
    reason TEXT,
    captions TEXT,
    transcript TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_lib_events_key ON library_events(scan_id, event_key);

CREATE TABLE IF NOT EXISTS library_categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    subcategories TEXT,
    keywords TEXT,
    example_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'learned',
    active INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS library_plan_items (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES library_scans(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES library_files(id) ON DELETE CASCADE,
    dest_rel TEXT NOT NULL,
    size INTEGER DEFAULT 0,
    category TEXT,
    year INTEGER,
    confidence REAL DEFAULT 0,
    collision INTEGER DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'proposed',
    applied_at TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_lib_plan_scan ON library_plan_items(scan_id, state);
CREATE INDEX IF NOT EXISTS idx_lib_plan_file ON library_plan_items(file_id);
