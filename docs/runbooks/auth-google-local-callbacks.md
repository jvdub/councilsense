# Google Auth Local Callback/Logout Values

Use these values in the managed auth app client configuration for local development.

## Local (localhost)

- Callback URL: `http://localhost:3000/auth/callback`
- Logout URL: `http://localhost:3000/`

## Dev

- Callback URL: `https://dev.councilsense.app/auth/callback`
- Logout URL: `https://dev.councilsense.app/`

## Validation

Run auth config validation with env wiring checks:

```bash
set -a
source .env.auth.example
set +a
python scripts/validate_auth_config.py
```

If you only want static config checks (without env vars), run:

```bash
python scripts/validate_auth_config.py --skip-env-check
```
