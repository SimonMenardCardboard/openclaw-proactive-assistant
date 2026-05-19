# Transmogrifier OAuth Configuration

This directory contains OAuth tokens for Transmogrifier (product version).

## Token Files

- `credentials.json` - OAuth 2.0 client credentials (from Google Cloud Console)
- `default_google_personal.json` - Personal Gmail/Calendar token
- `default_google_work.json` - Work Gmail/Calendar token
- `default_google_sigmasight.json` - Sigmasight Gmail/Calendar token
- `default_google_school.json` - Tulane Gmail/Calendar token

## Setup

1. Place `credentials.json` in this directory (from Google Cloud Console)
2. Run: `python3 ../setup/authorize_accounts.py`
3. Authorize each account when prompted

## Difference from COS

- **COS tokens:** `~/.openclaw/workspace/integrations/intelligence/config/`
- **Transmogrifier tokens:** `~/.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config/`

Both use the same OAuth flow but different client IDs (COS vs Transmogrifier app).
