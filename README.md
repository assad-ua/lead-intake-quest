# lead-intake-quest

Synthetic FastAPI sample for a hiring Quest. One flow: website form → `POST /leads` → score → push to a (fake) CRM.

Start with [`intent.md`](intent.md) (why this problem) and [`directive.md`](directive.md) (what was done, results, handoff).

```bash
pip install -r requirements.txt
python -m pytest -q
PYTHONPATH=. python scripts/measure.py after
```

All data is synthetic. Deliberate defects are labelled `DEFECT-1..3` in the code; DEFECT-1 is fixed, 2 and 3 are left in place on purpose.
