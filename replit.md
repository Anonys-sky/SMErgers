# SMErgers

## Run on Replit

- Keep the existing Python/Flask app and server-rendered Jinja templates.
- Click Run to start the `Start application` workflow (`python src/main.py`).
- The app listens on `0.0.0.0:5000` by default; `PORT` can override it.
- Python dependencies are pinned in `requirements.txt`.
- The session signing key uses `SECRET_KEY`, then the existing Replit
  `SESSION_SECRET`. With neither set, the original random-key fallback applies.
  Never commit secret values.

## Verify

Run `python -m pytest` for the Python tests and `python src/evaluate.py` for
the extraction accuracy report. The bridge conversion tests use `npm test`.

## Prototype limitations

- Demo jobs load at startup. Jobs, imports, and approvals are in memory and
  are lost on restart.
- The role switcher is a demo feature, not user authentication. Do not use
  this setup for private customer chats on a public deployment.
- Demo data and WhatsApp text-export imports work without external services.
- Live WhatsApp syncing is optional and is not started by the web workflow.
  It requires the Node dependencies in `package.json`, a compatible Chromium
  installation for Puppeteer, and `npm run whatsapp` as a separate local service
  on port 3001. Pair an account from `/whatsapp` after starting that service.
  Keep the bridge bound to loopback; do not expose its API publicly.
