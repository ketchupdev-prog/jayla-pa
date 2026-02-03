# Configuration for Jayla PA. See PERSONAL_ASSISTANT_PATTERNS.md C.1.

import os
from dataclasses import dataclass, fields
from typing import Any, Optional
from langchain_core.runnables import RunnableConfig


@dataclass(kw_only=True)
class Configuration:
    user_id: str = "default-user"
    thread_id: str = "default"
    todo_category: str = "general"
    jayla_role: str = "You are Jayla, a personal assistant. You help with Gmail, Calendar, and projects/tasks."

    @classmethod
    def from_runnable_config(cls, config: Optional[RunnableConfig] = None) -> "Configuration":
        configurable = config.get("configurable", {}) if config else {}
        values = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls) if f.init
        }
        return cls(**{k: v for k, v in values.items() if v is not None})
