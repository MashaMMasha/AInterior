-- Для уже существующей БД (volume до обновления init.sql)
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
