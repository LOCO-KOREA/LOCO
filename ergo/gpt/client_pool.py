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
    from ergo.ai_config import REQUEST_POLICY
    # The SDK/HTTPX timeout is the 'no answer yet' limit (create_response sends again); zero disables the SDK's own retries.
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
    """responses.create with the resend rule: a request that times out is sent again (same input) until REQUEST_ATTEMPTS sends were made.
    Any other error is raised at once, and after the last timeout the timeout itself is raised so the caller reports TIMEOUT."""
    from ergo.ai_config import REQUEST_ATTEMPTS
    sent = 0
    while True:
        sent += 1
        try:
            return get_client(api_key).responses.create(**request)
        except Exception as error:
            if "Timeout" not in type(error).__name__ or sent >= REQUEST_ATTEMPTS:
                raise


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
