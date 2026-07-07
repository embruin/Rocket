# Construction Cash Forecasting MVP

This is a starter Streamlit app for a construction company cash forecasting tool.

## What it does

- Uploads bank transaction CSVs
- Uploads AR and AP schedules
- Adds a recurring payment item such as payroll
- Creates a daily and weekly cash forecast
- Flags unknown or unaccounted-for bank transactions
- Exports the forecast to Excel

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Expected CSV formats

### Bank transactions

```csv
date,description,amount,category,status
2026-07-01,ABC Customer Deposit,18000,Customer deposit,posted
2026-07-02,Unknown ACH Debit,-1395,Uncategorized,posted
```

Required columns: `date`, `description`, `amount`.

### AR/AP schedules

```csv
name,due_date,amount,probability
ABC Customer,2026-07-12,42000,0.95
```

Required columns: `name`, `due_date`, `amount`.

## Free deployment option

1. Create a GitHub repository.
2. Upload these files to the repository.
3. Go to Streamlit Community Cloud.
4. Select the repository and set the main file as `app.py`.
5. Deploy.

## Next planned upgrades

- Store forecasts in Supabase
- Add login by company/user
- Add project-level cash flow categories
- Add Plaid bank connections
- Add QuickBooks Online integration
- Add variance analysis: forecasted vs actual transactions
- Add alerts when projected cash drops below a minimum threshold

## Data security warning

Do not upload real bank data to a public demo app. Use a private GitHub repo and environment secrets before testing with sensitive client data.
