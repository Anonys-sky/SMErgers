# Deploy the web prototype on Vercel

The repository includes a Flask entry point (`app.py`), a Python 3.12 pin,
Vercel configuration and a build step that copies `src/static/` into
`public/static/` for CDN delivery. Templates and synthetic data are included in
the function bundle. The existing Replit launcher is not used by Vercel.

## Project settings

1. Push these files to the GitHub branch connected to Vercel.
2. Set Root Directory to the repository root and Framework Preset to **Flask**.
3. Turn off dashboard command overrides so `vercel.json` supplies the commands:
   - Install: `pip install -r requirements.txt`
   - Build: `python scripts/build-vercel.py`
   - Output directory: leave unset (Flask preset).
   - Development command: leave the default.
4. Add `SECRET_KEY` in Vercel Environment Variables, for Production and Preview.
   Generate a value locally with `python -c "import secrets; print(secrets.token_hex(32))"`.
   Keep it stable across deployments and do not commit it.
5. For AI imports, also set `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID` and
   `SMERGERS_LLM_TIMEOUT=240`. The function allows up to 300 seconds; AI calls
   still fall back to rules if the endpoint cannot respond. Avoid pointing to a
   local Ollama URL, which is unreachable from the hosted function.
6. Deploy, then check the overview, a sample job, chat import, client confirmation,
   draft bill, CSV download, styles and tutorial in the deployed preview.

Vercel settings or organization policies can impose additional limits. No live
deployment is performed by adding these files.

## Scope of this deployment

This configuration hosts the web prototype: sample jobs, text imports, optional
RunPod reads, review pages and draft billing. Project state is still **in memory**.
An instance restart resets it, and separate instances do not share changes.
Do not rely on this deployment to retain approvals or use it for real jobs until
the store has been migrated to a shared database.

The optional Node/Chromium WhatsApp bridge and its continuous polling are not
started on Vercel. Use text import here. Full live syncing needs a separately
hosted, authenticated bridge and durable job state; setting `WHATSAPP_BRIDGE_URL`
alone does not provide those pieces.

References: [Flask on Vercel](https://vercel.com/docs/frameworks/backend/flask).
