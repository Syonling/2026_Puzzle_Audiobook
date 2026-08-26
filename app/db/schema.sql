CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,  -- 不允许重复
    password_hash TEXT NOT NULL,
    participant_id TEXT UNIQUE,
    pair_id TEXT,
    condition TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stories(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    -- title TEXT NOT NULL,
    -- description TEXT NOT NULL DEFAULT '',
    thumbnail_url TEXT
);

CREATE TABLE IF NOT EXISTS story_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id)
        REFERENCES stories(id)
        ON DELETE CASCADE,
    UNIQUE (story_id, language)
);

CREATE TABLE IF NOT EXISTS story_steps(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    step_order INTEGER NOT NULL,
    step_type TEXT NOT NULL DEFAULT 'story'
        CHECK (step_type IN ('story', 'free_creation')),
    -- sentence TEXT NOT NULL,
    FOREIGN KEY (story_id)
        REFERENCES stories(id)
        ON DELETE CASCADE,
    UNIQUE (story_id, step_order)
);

CREATE TABLE IF NOT EXISTS story_step_translations (
    story_step_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    sentence TEXT NOT NULL,
    audio_url TEXT,
    FOREIGN KEY (story_step_id)
        REFERENCES story_steps(id)
        ON DELETE CASCADE,
    UNIQUE (story_step_id, language)
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_key TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    image_url TEXT NOT NULL,
    audio_url TEXT
);

CREATE TABLE IF NOT EXISTS assets_translations (
    asset_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    name TEXT NOT NULL,
    category_translation TEXT NOT NULL,
    FOREIGN KEY (asset_id)
        REFERENCES assets(id)
        ON DELETE CASCADE,
    UNIQUE (asset_id, language)
);

-- icon 和 background 的可选音频。
CREATE TABLE IF NOT EXISTS asset_audio_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    audio_key TEXT NOT NULL UNIQUE,
    audio_url TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0
        CHECK (is_default IN (0, 1)),
    sort_order INTEGER NOT NULL DEFAULT 0
        CHECK (sort_order >= 0),
    FOREIGN KEY (asset_id)
        REFERENCES assets(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_asset_audio_options_asset_id
ON asset_audio_options(asset_id);

-- 一个素材最多只能有一个默认音频。
CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_audio_options_one_default
ON asset_audio_options(asset_id)
WHERE is_default = 1;

-- 暂时不写入名称；保留此表供以后增加多语言音频名称。
CREATE TABLE IF NOT EXISTS asset_audio_option_translations (
    audio_option_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (audio_option_id)
        REFERENCES asset_audio_options(id)
        ON DELETE CASCADE,
    UNIQUE (audio_option_id, language)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    story_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '未命名作品',
    current_step INTEGER NOT NULL DEFAULT 1,
    -- canvas_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    FOREIGN KEY (story_id)
        REFERENCES stories(id),
    UNIQUE (user_id, story_id)
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id
ON projects(user_id);

CREATE INDEX IF NOT EXISTS idx_story_steps_story_id
ON story_steps(story_id);

CREATE TABLE IF NOT EXISTS project_canvases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    story_step_id INTEGER NOT NULL,
    canvas_json TEXT NOT NULL DEFAULT '{}',
    audio_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE,

    FOREIGN KEY (story_step_id)
        REFERENCES story_steps(id)
        ON DELETE CASCADE,

    UNIQUE (project_id, story_step_id)
);

CREATE INDEX IF NOT EXISTS idx_project_canvases_project_id
ON project_canvases(project_id);

-- 增加预设AI对话
CREATE TABLE IF NOT EXISTS questions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_key TEXT NOT NULL UNIQUE
    -- question TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS question_translations (
    question_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    question TEXT NOT NULL,
    FOREIGN KEY (question_id)
        REFERENCES questions(id)
        ON DELETE CASCADE,
    UNIQUE (question_id, language)
);

-- 前端原始交互事件。user_id 用于数据归属，participant_id 用于实验分析。
CREATE TABLE IF NOT EXISTS interaction_events (
    event_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    suggestion_id TEXT,
    pair_id TEXT,
    participant_id TEXT NOT NULL,
    condition TEXT,
    story_id INTEGER,
    page_id INTEGER,
    client_timestamp TEXT NOT NULL,
    received_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    source TEXT,
    action_origin TEXT,
    event_data_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_interaction_events_user_id
ON interaction_events(user_id);

CREATE INDEX IF NOT EXISTS idx_interaction_events_session_id
ON interaction_events(session_id);

CREATE INDEX IF NOT EXISTS idx_interaction_events_event_type
ON interaction_events(event_type);

CREATE INDEX IF NOT EXISTS idx_interaction_events_story_page
ON interaction_events(story_id, page_id);

CREATE INDEX IF NOT EXISTS idx_interaction_events_suggestion_id
ON interaction_events(suggestion_id);

-- canvas_snapshot 事件的查询友好副本；原始 event_data 仍完整保留。
CREATE TABLE IF NOT EXISTS canvas_snapshots (
    event_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    story_id INTEGER,
    page_id INTEGER,
    snapshot_type TEXT NOT NULL,
    snapshot_timestamp TEXT NOT NULL,
    icons_json TEXT NOT NULL DEFAULT '[]',
    audio_clips_json TEXT NOT NULL DEFAULT '[]',
    canvas_json TEXT NOT NULL DEFAULT '{}',
    audio_json TEXT NOT NULL DEFAULT '{}',
    received_at TEXT NOT NULL,
    FOREIGN KEY (event_id)
        REFERENCES interaction_events(event_id)
        ON DELETE CASCADE,
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_canvas_snapshots_user_page
ON canvas_snapshots(user_id, story_id, page_id);

-- 后端 LLM 调用日志，通过 suggestion_id 与前端后续事件关联。
CREATE TABLE IF NOT EXISTS ai_suggestions (
    suggestion_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT,
    story_id INTEGER,
    page_id INTEGER,
    request_timestamp TEXT NOT NULL,
    response_timestamp TEXT,
    display_timestamp TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'failed')),
    mode TEXT,
    ai_input_json TEXT NOT NULL,
    ai_output_json TEXT,
    suggested_icons_json TEXT,
    suggested_positions_json TEXT,
    suggested_audio_json TEXT,
    error_message TEXT,
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_suggestions_user_id
ON ai_suggestions(user_id);

CREATE INDEX IF NOT EXISTS idx_ai_suggestions_session_id
ON ai_suggestions(session_id);
