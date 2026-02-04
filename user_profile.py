# User profile (name, role, company) per thread for Jayla to address the user. See PERSONAL_ASSISTANT_PATTERNS.md.

import os
import json

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    _HAS_PG = True
except ImportError:
    _HAS_PG = False


def _get_conn():
    if not _HAS_PG:
        return None
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        return psycopg2.connect(url, cursor_factory=RealDictCursor)
    except Exception:
        return None


def load_user_profile(thread_id: str) -> dict:
    """Load profile for thread_id. Returns dict with name, role, company, key_dates, communication_preferences, current_work_context, onboarding_step (empty string / 0 if missing)."""
    out = {
        "name": "",
        "role": "",
        "company": "",
        "key_dates": "",
        "communication_preferences": "",
        "current_work_context": "",
        "onboarding_step": 0,
    }
    conn = _get_conn()
    if not conn:
        return out
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT name, role, company, key_dates, communication_preferences, current_work_context, onboarding_step
                   FROM user_profiles WHERE thread_id = %s""",
                (thread_id,),
            )
            row = cur.fetchone()
        if row:
            out["name"] = (row.get("name") or "").strip()
            out["role"] = (row.get("role") or "").strip()
            out["company"] = (row.get("company") or "").strip()
            out["key_dates"] = (row.get("key_dates") or "").strip()
            out["communication_preferences"] = (row.get("communication_preferences") or "").strip()
            out["current_work_context"] = (row.get("current_work_context") or "").strip()
            out["onboarding_step"] = int(row.get("onboarding_step") or 0)
    except Exception as e:
        print(f"[user_profile] load error: {e}", flush=True)
    finally:
        conn.close()
    return out


def save_user_profile(
    thread_id: str,
    name: str = "",
    role: str = "",
    company: str = "",
    key_dates: str | None = None,
    communication_preferences: str | None = None,
    current_work_context: str | None = None,
    onboarding_step: int | None = None,
    onboarding_completed_at: bool = False,
) -> bool:
    """Upsert user profile for thread_id. Pass only fields to update; None means leave unchanged. onboarding_completed_at=True sets column to NOW(). Returns True if saved."""
    conn = _get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_profiles (thread_id, name, role, company, updated_at)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (thread_id) DO UPDATE SET
                     name = COALESCE(NULLIF(TRIM(EXCLUDED.name), ''), user_profiles.name),
                     role = COALESCE(NULLIF(TRIM(EXCLUDED.role), ''), user_profiles.role),
                     company = COALESCE(NULLIF(TRIM(EXCLUDED.company), ''), user_profiles.company),
                     updated_at = NOW()""",
                (thread_id, (name or "").strip(), (role or "").strip(), (company or "").strip()),
            )
        conn.commit()
        # Apply onboarding fields if provided (separate update so we don't overwrite with empty on legacy rows)
        updates = []
        params = []
        if key_dates is not None:
            updates.append("key_dates = %s")
            params.append((key_dates or "").strip())
        if communication_preferences is not None:
            updates.append("communication_preferences = %s")
            params.append((communication_preferences or "").strip())
        if current_work_context is not None:
            updates.append("current_work_context = %s")
            params.append((current_work_context or "").strip())
        if onboarding_step is not None:
            updates.append("onboarding_step = %s")
            params.append(int(onboarding_step))
        if onboarding_completed_at:
            updates.append("onboarding_completed_at = NOW()")
        if updates:
            params.append(thread_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_profiles SET " + ", ".join(updates) + " WHERE thread_id = %s",
                    params,
                )
            conn.commit()
        return True
    except Exception as e:
        print(f"[user_profile] save error: {e}", flush=True)
        return False
    finally:
        conn.close()


def extract_profile_from_message(message: str) -> dict[str, str] | None:
    """Use LLM to extract name, role, company from a short user message. Returns dict or None."""
    if not (message and len(message.strip()) < 500):
        return None
    text = message.strip().lower()
    if not any(
        phrase in text
        for phrase in ("i'm", "i am", "my name", "call me", "i work", "at ", "role", "company")
    ):
        return None
    try:
        if os.environ.get("DEEPSEEK_API_KEY"):
            from langchain_deepseek import ChatDeepSeek
            model = ChatDeepSeek(
                model=os.environ.get("LLM_MODEL", "deepseek-chat"),
                api_key=os.environ["DEEPSEEK_API_KEY"],
                temperature=0,
            )
        else:
            from langchain_groq import ChatGroq
            model = ChatGroq(
                model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
                api_key=os.environ["GROQ_API_KEY"],
                temperature=0,
            )
        prompt = """From this message extract the person's name, job role, and company/organization if mentioned.
Reply with ONLY a JSON object, no other text. Use empty string "" for any not mentioned.
Example: {"name": "Jero", "role": "MD", "company": "Ketchup Software Solutions"}
Message: """
        response = model.invoke(prompt + message.strip()[:400])
        content = (response.content or "").strip()
        if not content:
            return None
        # Strip markdown code block if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
        name = (data.get("name") or "").strip()
        role = (data.get("role") or "").strip()
        company = (data.get("company") or "").strip()
        if name or role or company:
            return {"name": name, "role": role, "company": company}
    except Exception as e:
        print(f"[user_profile] extract error: {e}", flush=True)
    return None
