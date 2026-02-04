# RAG tools: explicit search over uploaded documents. See ONBOARDING_PLAN.md Phase 3.

import os
from langchain_core.tools import tool

from rag import retrieve as rag_retrieve


def _get_user_id() -> str:
    return os.environ.get("USER_ID") or os.environ.get("EMAIL", "default-user")


@tool
def search_my_documents(query: str, limit: int = 5) -> str:
    """Search the user's uploaded documents (contracts, compliance, company docs) by meaning.
    Call this when the user asks to search their documents, find something in their docs, or look up a policy/contract/clause."""
    user_id = _get_user_id()
    chunks = rag_retrieve(query.strip(), user_id=user_id, limit=max(1, min(limit, 10)))
    if not chunks:
        return "No matching passages found in your documents. Try different keywords or upload more documents."
    return "Relevant passages from your documents:\n\n" + "\n\n---\n\n".join(chunks)


@tool
def suggest_email_body_from_context(purpose: str, recipient: str = "") -> str:
    """Suggest an email body from the user's document context (RAG). Call when the user wants to draft an email and you have or can retrieve relevant context. Returns suggested bullet points; use them in Gmail draft tools."""
    user_id = _get_user_id()
    chunks = rag_retrieve(purpose.strip(), user_id=user_id, limit=3)
    if not chunks:
        return "No relevant document context. Compose the email from scratch."
    return "Suggested points from your documents:\n\n" + "\n\n".join(f"• {c}" for c in chunks)


def get_rag_tools():
    """Return list of RAG tools for the agent."""
    return [search_my_documents, suggest_email_body_from_context]
