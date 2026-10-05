import time
import uuid
from dataclasses import dataclass


class CRMError(Exception):
    """Raised when the lead could not be written to the CRM."""


class CRMTimeout(Exception):
    """Transport-level timeout talking to the CRM."""


class CRMHTTPError(Exception):
    def __init__(self, status: int, body: str = ""):
        super().__init__(f"CRM returned HTTP {status}: {body}")
        self.status = status


@dataclass(frozen=True)
class RetryPolicy:
    """When and how often to retry a CRM write. Change retries here only.

    Worst-case wait = sum(base_delay_s * 2**i for i in range(max_attempts - 1)).
    Defaults: 3 attempts, waits 0.2 s then 0.4 s (0.6 s total).
    """

    max_attempts: int = 3
    base_delay_s: float = 0.2
    retry_statuses: frozenset = frozenset({429, *range(500, 600)})

    def is_transient(self, exc: Exception) -> bool:
        if isinstance(exc, CRMTimeout):
            return True
        if isinstance(exc, CRMHTTPError):
            return exc.status in self.retry_statuses
        return False

    def delay_before_retry(self, attempt: int) -> float:
        """Delay after failed attempt number `attempt` (1-based)."""
        return self.base_delay_s * 2 ** (attempt - 1)


class CRMClient:
    """Thin client for the CRM 'create contact' endpoint.

    `transport` is anything with `post(path, json, headers) -> dict` that
    raises CRMTimeout or CRMHTTPError on failure (see app/fake_crm.py).
    """

    def __init__(self, transport, sleep=time.sleep, policy: RetryPolicy = RetryPolicy()):
        self.transport = transport
        self.sleep = sleep
        self.policy = policy

    def push_lead(self, payload: dict, idempotency_key: str | None = None) -> dict:
        """Create the contact, retrying transient failures only.

        The same Idempotency-Key is sent on every attempt, so a retry after
        a lost response returns the existing contact instead of a duplicate.
        Pass your own key if the caller may retry at a higher level.
        """
        headers = {"Idempotency-Key": idempotency_key or str(uuid.uuid4())}
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return self.transport.post("/contacts", json=payload, headers=headers)
            except (CRMTimeout, CRMHTTPError) as exc:
                last_attempt = attempt == self.policy.max_attempts
                if not self.policy.is_transient(exc) or last_attempt:
                    raise CRMError(f"CRM push failed on attempt {attempt}: {exc}") from exc
                self.sleep(self.policy.delay_before_retry(attempt))
