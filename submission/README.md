# Submission documents

File names from the official GitHub template (`SDC_Hackathon_Submission_Template`). Put each file in this folder:

- [ ] `SDC2026_VBall_Preliminary.pdf`: the completed submission template (text drafted outside the repo).
- [ ] `SDC2026_VBall_TechDeclaration.pdf`: the completed Technical Tools Declaration, listing every tool, API and AI assistant.
- [ ] `SDC2026_VBall_Replit_POU.pdf`: Replit proof of use (live deployment URL, project link with history, or credit screenshot, from a team member's own account).
- [ ] `SDC2026_VBall_Runpod_POU.pdf`: RunPod dashboard screenshot (Pod or Endpoint ID, GPU type, runtime, own account). Needed if the AI reader runs on RunPod.
- [ ] Pitch deck PDF and the YouTube demo link, added to the root `README.md`.

Before submitting: make the repository public, replace `TeamName` as above, confirm no secrets are committed, and verify the "How to run" steps.

## RunPod: decide before submitting

Handbook 9.4: "Teams must use RunPod for any work that needs a GPU", including running a model (inference) that needs a GPU. 10.7 requires a RunPod dashboard screenshot (Pod ID, GPU type, runtime, own account) in the Tools Declaration if RunPod was used.

What happened: the optional AI reader (Llama 3.1 8B via Ollama) was scored once (Run 3 in `docs/results.md`) on a laptop with an RTX 2050, partly on the GPU. The product itself runs without it (rules reader is the default, and the Replit app does not run a model).

Pick one and keep every document consistent with it:
- [ ] **Ask the organizers on Discord** whether a small local model run on a laptop counts, and keep their answer.
- [ ] **Recommended: put the AI reader on a RunPod serverless endpoint** following `runpod/README.md`, re-run `python src/evaluate.py --blind --ai` there, log it as a new run, and save the dashboard screenshot as `SDC2026_VBall_Runpod_POU.pdf`. This also makes the reader fast.
- [ ] **Drop the AI result** from the submission and describe the AI reader as planned only.

The Tools Declaration, proposal answers, README and deck currently disclose the local run.
