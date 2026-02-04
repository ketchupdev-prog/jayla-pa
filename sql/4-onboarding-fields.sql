-- Onboarding fields for user_profiles. See ONBOARDING_PLAN.md.
-- key_dates, communication_preferences, current_work_context (projects, deadlines, tasks, reminders); onboarding step tracking.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS key_dates TEXT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS communication_preferences TEXT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS current_work_context TEXT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS onboarding_step INT DEFAULT 0;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;
