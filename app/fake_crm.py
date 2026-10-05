"""In-process fake CRM used by tests and the measurement script.

SYNTHETIC: this stands in for a real CRM API (HubSpot/Pipedrive style).
No network calls are made. Behaviour is driven by a script of outcomes so
every run is reproducible.

Outcomes:
  "ok"                    create the contact, return it
  "timeout_before_commit" raise CRMTimeout, nothing stored
  "timeout_after_commit"  store the contact, then raise CRMTimeout
                          (the response was lost on the way back)
  "500" / "503"           raise CRMHTTPError, nothing stored
  "429"                   raise CRMHTTPError(429), nothing stored
  "400"                   raise CRMHTTPError(400) - permanent rejection
When the script runs out, the last outcome repeats.

Idempotency: if a request carries an `Idempotency-Key` header that was
already used for a stored contact, the fake returns that contact instead
of creating a new one (the common behaviour of CRM/payment APIs that
support idempotency keys).
"""

from app.crm_client import CRMHTTPError, CRMTimeout


class FakeCRM:
    def __init__(self, script=None):
        self.script = list(script or ["ok"])
        self.requests = 0
        self.contacts = []
        self._by_key = {}

    def _next_outcome(self):
        if len(self.script) > 1:
            return self.script.pop(0)
        return self.script[0]

    def _store(self, json, key):
        if key and key in self._by_key:
            return self._by_key[key]
        contact = {"id": len(self.contacts) + 1, **json}
        self.contacts.append(contact)
        if key:
            self._by_key[key] = contact
        return contact

    def post(self, path, json, headers):
        self.requests += 1
        key = (headers or {}).get("Idempotency-Key")
        outcome = self._next_outcome()
        if outcome == "ok":
            return self._store(json, key)
        if outcome == "timeout_after_commit":
            self._store(json, key)
            raise CRMTimeout("read timeout")
        if outcome == "timeout_before_commit":
            raise CRMTimeout("connect timeout")
        if outcome in {"400", "429", "500", "503"}:
            raise CRMHTTPError(int(outcome))
        raise ValueError(f"unknown outcome {outcome!r}")

    def contacts_for(self, email):
        return [c for c in self.contacts if c.get("email") == email]
