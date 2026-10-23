# Submission documents

Add these before submitting (from the official template):

- [ ] `REPLIT PROOF OF USE.pdf`: live deployment URL, project link with history, or finished credit, from a team member's own Replit account.
- [ ] `Submission Template SDC Hackathon.pdf`: the completed proposal.
- [ ] Technical Tools Declaration: list every tool, API and AI assistant used, including AI coding assistants.

## RunPod: decide before submitting

Handbook 9.4: "Teams must use RunPod for any work that needs a GPU", including running a model (inference) that needs a GPU. 10.7 requires a RunPod dashboard screenshot (Pod ID, GPU type, runtime, own account) in the Tools Declaration if RunPod was used.

What happened: the optional AI reader (Llama 3.1 8B via Ollama) was scored once (Run 3 in `docs/results.md`) on a laptop with an RTX 2050, partly on the GPU. The product itself runs without it (rules reader is the default, and the Replit app does not run a model).

Pick one and keep every document consistent with it:
- [ ] **Ask the organizers on Discord** whether a small local model run on a laptop counts, and keep their answer.
- [ ] **Re-run Run 3 on RunPod** (start a pod with Ollama, `ollama pull llama3.1:8b`, `python src/evaluate.py --blind --ai`), take the dashboard screenshot, and add it to the Tools Declaration.
- [ ] **Drop the AI result** from the submission and describe the AI reader as planned only.

The Tools Declaration, proposal answers, README and deck currently disclose the local run.
