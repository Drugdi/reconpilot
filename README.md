
# ReconPilot sellable validation MVP v0.5

## Goal
Validate willingness-to-pay before building a full SaaS.

Flow:
1. Upload supplier statement + AP ledger (CSV/XLS/XLSX).
2. Confirm column mapping.
3. Run reconciliation.
4. Show metrics + first 8 exceptions free.
5. CTA: unlock full workpaper for €49.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Paid validation
Create a legitimate payment/checkout page for the report you can actually deliver.
Set its URL as `PAYMENT_URL` in Streamlit secrets. Until then the app stays in test mode
and permits workpaper download.

## Deployment
Put these files in a GitHub repository and deploy `app.py` on Streamlit Community Cloud.
Do not upload real confidential accounting data to a public test environment without an
appropriate privacy/security setup and customer authorization.

## Current limitations
- CSV/XLS/XLSX only
- grouped 1:N / N:1 matches are review-only
- no ERP/payment writes
- no PDF extraction yet
