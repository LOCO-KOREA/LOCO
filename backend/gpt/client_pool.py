"""Process-wide synchronous OpenAI client and HTTP connection-pool reuse."""
import atexit
import hashlib
import os
import threading

_clients = {}
_lock = threading.Lock()


def _identity(api_key):
    # Keep credentials out of cache keys while respecting provider endpoint changes.
    credential = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return (credential, os.environ.get("OPENAI_BASE_URL"), os.environ.get("OPENAI_ORG_ID"),
            os.environ.get("OPENAI_PROJECT_ID"), os.environ.get("OPENAI_CUSTOM_HEADERS"))


def _new_client(api_key):
    from openai import OpenAI
    from backend.ai_config import REQUEST_POLICY
    # None disables all HTTPX timeout phases; zero disables SDK retries.
    return OpenAI(api_key=api_key, **REQUEST_POLICY)


def get_client(api_key):
    """Return the shared client for this credential and provider configuration."""
    key = _identity(api_key)
    with _lock:
        client = _clients.get(key)
        if client is None:
            client = _new_client(api_key)
            _clients[key] = client
        return client


def create_response(api_key, **request):
    """Send once and wait; provider errors are handled by the calling AI path."""
    return get_client(api_key).responses.create(**request)


def close_clients():
    """Close shared HTTP pools during process shutdown (or test cleanup)."""
    with _lock:
        clients = list(_clients.values())
        _clients.clear()
    for client in clients:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


atexit.register(close_clients)
