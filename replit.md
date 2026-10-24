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
The role-workspace table filters are tested with
`node --test tests/workspace_filter.test.cjs`.

## Role workspaces

- `/workspace/project-manager`: chat imports, evidence review and pricing.
- `/workspace/project-director`: the existing owner-approval role, now labeled
  Project director; approval rules and thresholds are unchanged.
- `/workspace/client`: confirmation/dispute for one synthetic client's event. The
  sample-event selector, or opening a job's client link, changes that context.
- `/workspace/finance`: read-only billing, source evidence, CSV exports and history.
- `/imports` is the dedicated chat-import page; `/guide` explains the current role.
- Selecting a workspace changes a simulated role in the browser session. This is
  not authentication or a production authorization boundary.
- Finance export checklist state is session-based and applies only to the current
  version of each bill; later approval changes make a previous export out of date.

## AI reader

The rules reader runs by default and needs nothing else. The optional AI reader (`SMERGERS_READER=llm`) calls a RunPod Serverless vLLM endpoint when `RUNPOD_ENDPOINT_ID` and `RUNPOD_API_KEY` are set in Replit Secrets (steps in `runpod/README.md`); if it is unreachable the app falls back to the rules.

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
