import time
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
    Retries: timeouts and 5xx. Everything else fails on the first attempt.
    """

    max_attempts: int = 3
    base_delay_s: float = 0.2
    # 429 is NOT retried here: rate limits reset over seconds, so short
    # in-request retries only burn quota (review finding R1).
    retry_statuses: frozenset = frozenset(range(500, 600))

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

    def push_lead(self, payload: dict, idempotency_key: str) -> dict:
        """Create the contact, retrying transient failures only.

        `idempotency_key` identifies ONE submission. It is sent unchanged on
        every attempt, so a retry after a lost response returns the existing
        contact instead of a duplicate. It is required on purpose: any caller
        that retries at a higher level (e.g. a queue) must reuse the same key
        (review finding R2).
        """
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        headers = {"Idempotency-Key": idempotency_key}
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return self.transport.post("/contacts", json=payload, headers=headers)
            except (CRMTimeout, CRMHTTPError) as exc:
                last_attempt = attempt == self.policy.max_attempts
                if not self.policy.is_transient(exc) or last_attempt:
                    raise CRMError(f"CRM push failed on attempt {attempt}: {exc}") from exc
                self.sleep(self.policy.delay_before_retry(attempt))
