# Security Notes

- This repository is source code only.
- Do not commit vault data, `.msg` files, attachments, SQLite databases, logs, `.env`, tokens, SSH keys, or local config.
- Do not use `https://github.sec.samsung.net` or any GitHub repository as personal knowledge storage.
- GitHub tokens are not required by this project. Do not store `GITHUB_TOKEN` or GitHub credentials in local KB config files.
- Do not upload emails, notes, attachments, or retrieved context to external SaaS services.
- The API is read-only for AI consumers and should bind to `127.0.0.1` by default.
- Every non-health API call requires bearer-token authentication.
- Admin reindex uses a separate admin token.
- All committed fixtures must be synthetic.
