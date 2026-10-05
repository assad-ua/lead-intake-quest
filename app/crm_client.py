import time


class CRMError(Exception):
    """Raised when the lead could not be written to the CRM."""


class CRMTimeout(Exception):
    """Transport-level timeout talking to the CRM."""


class CRMHTTPError(Exception):
    def __init__(self, status: int, body: str = ""):
        super().__init__(f"CRM returned HTTP {status}: {body}")
        self.status = status


class CRMClient:
    """Thin client for the CRM 'create contact' endpoint.

    `transport` is anything with `post(path, json, headers) -> dict` that
    raises CRMTimeout or CRMHTTPError on failure (see app/fake_crm.py).
    """

    def __init__(self, transport, sleep=time.sleep):
        self.transport = transport
        self.sleep = sleep

    def push_lead(self, payload: dict) -> dict:
        # DEFECT-1 (deliberate, labelled for the Quest): unreliable retries.
        #  - retries on EVERY error, including permanent 4xx rejections
        #  - 8 attempts with a fixed 0.5 s sleep, no backoff
        #  - no idempotency key, so a timeout that happens AFTER the CRM
        #    created the contact makes the retry create a duplicate
        for attempt in range(8):
            try:
                return self.transport.post("/contacts", json=payload, headers={})
            except Exception:
                self.sleep(0.5)
        raise CRMError("CRM push failed after retries")
