# QuickBooks Online API Skill

Interact with QuickBooks Online for invoicing, customers, payments, and accounting.

## Setup

1. Create an app at https://developer.intuit.com
2. Get OAuth credentials (Client ID, Client Secret)
3. Store credentials:
```bash
pass insert quickbooks/client_id
pass insert quickbooks/client_secret
pass insert quickbooks/refresh_token
pass insert quickbooks/company_id
```

## CLI Usage

```bash
# Run with uv (auto-installs dependencies)
cd ~/clawdbot/skills/quickbooks

# List customers
uv run qb.py customers

# Search customers
~/clawdbot/skills/quickbooks/qb.py customers --search "Smith"

# Get specific customer
~/clawdbot/skills/quickbooks/qb.py customer <id>

# List invoices
~/clawdbot/skills/quickbooks/qb.py invoices

# Get invoice
~/clawdbot/skills/quickbooks/qb.py invoice <id>

# Create invoice
~/clawdbot/skills/quickbooks/qb.py create-invoice --customer <id> --line "Service:100.00"

# List accounts
~/clawdbot/skills/quickbooks/qb.py accounts

# Query (raw)
~/clawdbot/skills/quickbooks/qb.py query "SELECT * FROM Customer WHERE Active = true"

# Auth flow (get initial tokens)
~/clawdbot/skills/quickbooks/qb.py auth
```

## Available Entities

- **Customer** - clients/customers
- **Invoice** - sales invoices
- **Payment** - customer payments
- **Bill** - vendor bills
- **Vendor** - suppliers
- **Account** - chart of accounts
- **Item** - products/services
- **Estimate** - quotes
- **SalesReceipt** - point of sale
- **CreditMemo** - credits
- **JournalEntry** - manual entries
- **Purchase** - expenses
- **Transfer** - bank transfers

## Environment

Uses sandbox by default. Set `QB_ENVIRONMENT=production` for live data.

## Token Refresh

Tokens auto-refresh when expired. The CLI updates stored refresh_token automatically.

## Rate Limits

- 500 requests per minute per realm (company)
- Batch operations available for bulk updates

## References

- API Docs: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
- Python SDK: https://github.com/ej2/python-quickbooks
- OAuth Guide: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
