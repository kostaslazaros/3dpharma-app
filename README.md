### backend
 pip install -r requirements.txt |
 python main.py

### frontend 

npm install
| npm run dev
| npm run build

---

## Clinical co-administration ("συγχορήγηση") feature

A galinos.gr-style clinical checker: enter one or more active substances plus
optional patient context (sex, age, and conditions such as pregnancy, lactation,
renal/hepatic impairment, alcohol, G6PD deficiency, myelosuppression, driving,
plus free-text diseases) and get three severity-graded buckets — **contraindications**,
**drug-drug interactions**, and **adverse effects**.

- **UI:** the "Co-administration" tab (`frontend/src/components/CoAdministration.tsx`).
- **API:** `POST /coadministration/check`, `GET /coadministration/conditions`.
- **AI agent:** `POST /chat/coadmin` — a tool-using, grounded clinical assistant
  (provider-agnostic; defaults to the cheap `gpt-4o-mini`, configurable via
  `COADMIN_LLM_PROVIDER` / `COADMIN_LLM_MODEL`).

### Data
Condition data comes from **free openFDA drug labels** (contraindications,
pregnancy, use-in-specific-populations, drug interactions, adverse reactions).
Drug-drug interactions reuse the existing DrugBank-derived database.

A curated seed file ships in `backend/data/condition_labels.json` (~100 common
drugs) so the feature works out of the box. To expand or refresh it:

```
cd backend
python scripts/build_condition_labels.py                 # curated seed list
python scripts/build_condition_labels.py --from-db comprehensive_drug_database_compact.json --limit 2000
```

Set `OPENFDA_API_KEY` to raise the rate limit. The script is resumable.

> **Disclaimer:** This is a decision-support aid, not a substitute for the
> clinical judgement of a qualified healthcare professional. Always verify against
> the approved product information (SmPC) before prescribing or dispensing.
