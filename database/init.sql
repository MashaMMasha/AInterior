CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS furniture;
CREATE SCHEMA IF NOT EXISTS interior;
CREATE SCHEMA IF NOT EXISTS chat;

CREATE TABLE IF NOT EXISTS users.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users.verification_codes (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_verification_codes_email ON users.verification_codes(email);

CREATE TABLE IF NOT EXISTS furniture.catalog (
    id SERIAL PRIMARY KEY,
    type VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    size_x FLOAT NOT NULL,
    size_y FLOAT NOT NULL,
    size_z FLOAT NOT NULL,
    default_color_r FLOAT NOT NULL,
    default_color_g FLOAT NOT NULL,
    default_color_b FLOAT NOT NULL,
    tags TEXT[] NOT NULL,
    price_category VARCHAR(50) NOT NULL,
    model_path VARCHAR(500),
    thumbnail_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE IF NOT EXISTS interior.rooms (
    id SERIAL PRIMARY KEY,
    room_id VARCHAR(100) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    room_type VARCHAR(100) NOT NULL,
    dimension_length FLOAT NOT NULL,
    dimension_width FLOAT NOT NULL,
    dimension_height FLOAT NOT NULL,
    style VARCHAR(100) NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interior.furniture_items (
    id SERIAL PRIMARY KEY,
    room_id INTEGER REFERENCES interior.rooms(id) ON DELETE CASCADE,
    furniture_type VARCHAR(100) REFERENCES furniture.catalog(type) ON DELETE CASCADE,
    position_x FLOAT NOT NULL,
    position_y FLOAT NOT NULL,
    position_z FLOAT NOT NULL,
    rotation_x FLOAT DEFAULT 0.0,
    rotation_y FLOAT DEFAULT 0.0,
    rotation_z FLOAT DEFAULT 0.0,
    scale_x FLOAT DEFAULT 1.0,
    scale_y FLOAT DEFAULT 1.0,
    scale_z FLOAT DEFAULT 1.0,
    color_r FLOAT NOT NULL,
    color_g FLOAT NOT NULL,
    color_b FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interior.room_history (
    id SERIAL PRIMARY KEY,
    room_id INTEGER REFERENCES interior.rooms(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users.users(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    changes JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interior.generation_progress (
    id SERIAL PRIMARY KEY,
    generation_id UUID UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users.users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    current_step VARCHAR(100),
    total_steps INTEGER DEFAULT 8,
    completed_steps INTEGER DEFAULT 0,
    scene_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_generation_progress_generation_id ON interior.generation_progress(generation_id);
CREATE INDEX IF NOT EXISTS idx_generation_progress_user_id ON interior.generation_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_generation_progress_status ON interior.generation_progress(status);

-- Chat schema tables
CREATE TABLE IF NOT EXISTS chat.sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER REFERENCES users.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat.interactions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) REFERENCES chat.sessions(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    query TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_chat_interactions_session_sequence UNIQUE (session_id, sequence)
);

CREATE TABLE IF NOT EXISTS chat.stages (
    id SERIAL PRIMARY KEY,
    interaction_id INTEGER REFERENCES chat.interactions(id) ON DELETE CASCADE,
    stage_name VARCHAR(255) NOT NULL,
    scene_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_scene_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_interactions_session_id ON chat.interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_stages_interaction_id ON chat.stages(interaction_id);

-- Projects table
CREATE TABLE IF NOT EXISTS interior.projects (
    id SERIAL PRIMARY KEY,
    project_id UUID UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    scene_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON interior.projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_project_id ON interior.projects(project_id);

-- Проекты UI (backend-service): id строкой, сцена JSON, привязка к чату
CREATE TABLE IF NOT EXISTS interior.app_projects (
    id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    objects JSONB NOT NULL DEFAULT '[]'::jsonb,
    conversation_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_projects_user_id ON interior.app_projects(user_id);

