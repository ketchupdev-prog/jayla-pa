-- User profile per thread (name, role, company) so Jayla can address the user. See PERSONAL_ASSISTANT_PATTERNS.md.
CREATE TABLE IF NOT EXISTS user_profiles (
  thread_id TEXT PRIMARY KEY,
  name TEXT,
  role TEXT,
  company TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
