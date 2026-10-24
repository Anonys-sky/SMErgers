# Running the AI reader on RunPod

The AI reader (`src/llm_extractor.py`) can call any OpenAI-compatible endpoint. On RunPod it uses a **Serverless vLLM endpoint**, so the model runs on a RunPod GPU and the web app (on Replit) only sends the chat text over HTTPS. No custom handler is needed: RunPod's vLLM worker already exposes the OpenAI-compatible API.

## Set up (about 10 minutes, a few cents)

1. In your own RunPod account: **Serverless → New Endpoint → vLLM** (quick deploy).
2. Model: `meta-llama/Llama-3.1-8B-Instruct`. This model is gated on Hugging Face: accept Meta's licence on the model page and add a Hugging Face read token as the worker's `HF_TOKEN`. (An ungated instruct model also works; set `SMERGERS_LLM_MODEL` to its name.)
3. GPU: 24 GB is plenty (we used an RTX 4090, pool `ADA_24`, about US$1.10 an hour while a worker runs). Set **min workers 0, max workers 1, idle timeout 30 s** and a **120 s job timeout**, so the endpoint costs nothing when idle and one stuck job cannot run up the bill. Context length: `MAX_MODEL_LEN=8192`.
4. Copy the **Endpoint ID** and create an **API key** in RunPod settings.
5. Put them in Replit **Secrets** (never in the repository):

   ```
   RUNPOD_ENDPOINT_ID=<your endpoint id>
   RUNPOD_API_KEY=<your api key>
   ```

   The reader then calls `https://api.runpod.ai/v2/<id>/openai/v1/chat/completions` whenever a chat is imported with **Read with the AI reader** ticked. If the endpoint is unreachable the app falls back to the rules reader and says so.

### Lessons from our own setup
- **Hugging Face approval comes first.** Meta approves access by hand (minutes to hours). Until then the worker answers every job with a "gated" error (403 on the model check); it fails in about half a second and costs almost nothing, but it stays in that state until a fresh worker starts, so scale the endpoint to 0 workers and back to 1 after approval.
- **Image tag.** We used `runpod/worker-v1-vllm:v2.30.1` (`latest` does not exist). Pick the newest release tag from Docker Hub.
- **Cold start.** The first request after a quiet period waits 2 to 3 minutes while a worker starts and loads the model; after that a chat takes seconds. Warm it a few minutes before a demo, and do not leave a minimum worker on (about US$26 a day).
- **Cost.** A full blind-set run (3 chats) is a few cents. Check RunPod Billing after a test; it lags by up to an hour.
- **Keys.** Use a Restricted API key (Serverless only), keep it in Replit Secrets, and revoke it when you are done.

## Check it and score it

```bash
curl -X POST https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/openai/v1/chat/completions \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" \
  -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "messages": [{"role": "user", "content": "Say hi"}]}'

RUNPOD_ENDPOINT_ID=... RUNPOD_API_KEY=... python src/evaluate.py --blind --ai
```

Log the result in `docs/results.md` as a new run (note the model and that it ran on RunPod).

## Proof of use

Screenshot the RunPod dashboard from the team's own account showing the Pod or Endpoint ID, the GPU type and the runtime, and save it as `submission/SDC2026_VBall_Runpod_POU.pdf`.
