# Rule Configuration

Rule thresholds are stored in `config/rules.json`.

Default profile:

```text
enterprise_flow_review
```

Switch profile before starting the app:

```powershell
$env:RULE_PROFILE="audit_review"
python app.py
```

Use another config file:

```powershell
$env:RULE_CONFIG_PATH="C:\\path\\to\\rules.json"
python app.py
```

Built-in profiles:

- `enterprise_flow_review`
- `personal_loan_review`
- `audit_review`

Configurable sections:

- `balance_continuity.tolerance`
- `duplicates.enabled`
- `low_confidence.threshold`
- `sensitive_keywords.keywords`
- `large_round_amount.min_amount`
- `large_round_amount.round_base`
- `same_day_in_out.min_income`
- `same_day_in_out.expense_income_ratio`
- `counterparty_concentration.max_ratio`

Each section can also set `enabled` to `true` or `false`.
