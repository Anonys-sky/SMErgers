# Running the AI reader on RunPod

The AI reader (`src/llm_extractor.py`) can call any OpenAI-compatible endpoint. On RunPod it uses a **Serverless vLLM endpoint**, so the model runs on a RunPod GPU and the web app (on Replit) only sends the chat text over HTTPS. No custom handler is needed: RunPod's vLLM worker already exposes the OpenAI-compatible API.

## Set up (about 10 minutes, a few cents)

1. In your own RunPod account: **Serverless → New Endpoint → vLLM** (quick deploy).
2. Model: `meta-llama/Llama-3.1-8B-Instruct`. This model is gated on Hugging Face: accept Meta's licence on the model page and add a Hugging Face read token as the worker's `HF_TOKEN`. (An ungated instruct model also works; set `SMERGERS_LLM_MODEL` to its name.)
3. GPU: 24 GB is plenty. Max workers 1 is enough.
4. Copy the **Endpoint ID** and create an **API key** in RunPod settings.
5. Put them in Replit **Secrets** (never in the repository):

   ```
   SMERGERS_READER=llm
   RUNPOD_ENDPOINT_ID=<your endpoint id>
   RUNPOD_API_KEY=<your api key>
   ```

   The reader then calls `https://api.runpod.ai/v2/<id>/openai/v1/chat/completions`. If the endpoint is unreachable the app falls back to the rules reader.

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
