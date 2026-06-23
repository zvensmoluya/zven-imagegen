---
name: zven-imagegen
description: Generate or edit raster images through an OpenAI-compatible image endpoint with dedicated IMAGEGEN_* credentials and streamed partial-image progress. Use when Codex needs image generation behind a custom base_url, reverse proxy, Cloudflare-protected endpoint, or separate image API key instead of the built-in imagegen path.
---

# Zven Imagegen

Use this skill when image generation should go through a dedicated endpoint or
base URL instead of Codex's default image tool. Always invoke the bundled
cross-platform Python wrapper; do not search the current project for image
helper scripts or use Codex's default image tool for this skill. The wrapper keeps
`IMAGEGEN_OPENAI_API_KEY` and `IMAGEGEN_OPENAI_BASE_URL` separate from normal
OpenAI/Codex settings, calls this skill's bundled helper, and streams progress
by default to keep long image requests active through proxies that dislike quiet
connections.

## Quick Start

Run the Python wrapper from any project:

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" generate \
  --prompt "A clean product cutout of a ceramic mug, no text, no logo" \
  --size 1024x1024 \
  --quality low \
  --out output/imagegen/mug.png
```

## Credential Precedence

The wrapper resolves settings in this order:

1. `IMAGEGEN_OPENAI_API_KEY`
2. `IMAGEGEN_OPENAI_BASE_URL`
3. Project config found by walking upward from the current directory:
   `.agentonlyenv`, `.imagegen.env`, or `.env.imagegen`
4. Fallback API key from `$CODEX_HOME/auth.json` or `$HOME/.codex/auth.json`
5. Fallback base URL from `$CODEX_HOME/config.toml` or `$HOME/.codex/config.toml`

Only the child image-generation process receives `OPENAI_API_KEY` and
`OPENAI_BASE_URL`. Never ask the user to paste keys in chat, and never print key
values.

For project-local config, create one of these ignored files:

```dotenv
IMAGEGEN_OPENAI_BASE_URL=https://your-image-endpoint.example/v1
IMAGEGEN_OPENAI_API_KEY=your-image-api-key
```

## Workflow

1. Write final image assets under `output/imagegen/` unless the user asks for
   another path.
2. Run `scripts/invoke_imagegen.py` with `generate`, `edit`, or
   `generate-batch`. The wrapper calls the bundled helper from this skill.
3. Prefer `IMAGEGEN_OPENAI_API_KEY` and `IMAGEGEN_OPENAI_BASE_URL` when the
   image endpoint differs from the rest of Codex.
4. Add `.agentonlyenv`, `.imagegen.env`, or `.env.imagegen` to the project root
   for repo-local private settings; keep real credentials out of git.
5. Keep prompts original and avoid requesting copied game, movie, brand, or
   copyrighted UI assets.

## Wrapper Behavior

`scripts/invoke_imagegen.py` forwards all CLI arguments to this skill's bundled
`scripts/imagegen_stream.py`. It intentionally does not auto-discover
`scripts/imagegen_stream.py` in the current project; normal user projects should
not have this helper.

`scripts/invoke-imagegen.ps1` is a Windows PowerShell compatibility wrapper, not
the default skill entrypoint.

The streamed helper supports `generate`, `edit`, and `generate-batch`.
Generation and editing default to `--stream`; use `--no-stream` only when a
provider does not support streaming.
For OpenAI-compatible endpoints that stream partial images but omit a completed
event, the helper treats the latest partial image only as a candidate. Some
providers also accept `stream=true` but return a final `application/json`
payload instead of SSE; the helper detects that shape and reads the final image
from the same response without sending a second request. It validates image
bytes before writing files; if the streamed candidate is missing, interrupted,
or invalid, it retries once without streaming and writes the first valid
`b64_json`, data URI, or image URL returned by the endpoint.

The wrapper uses a managed `.venv` inside the skill folder and installs
`openai>=2.0.0` there on first live use if needed. Dry-runs skip the managed
environment and dependency install. Do not ask the user to manage Python
packages for this skill unless environment creation or package installation
fails. Set `IMAGEGEN_PYTHON` only when the wrapper cannot find Python 3.10+
automatically.

## Common Commands

Dry-run without a network call:

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" generate --prompt "Test image" --out output/imagegen/test.png --dry-run
```

Generate with streamed progress:

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" generate --prompt "A polished landing-page hero image of a matte ceramic mug" --size 1536x1024 --quality medium --partial-images 1 --out output/imagegen/mug-hero.png
```

Edit an existing image:

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" edit --image input.png --prompt "Replace only the background with a warm studio backdrop" --out output/imagegen/edited.png
```

Generate from JSONL:

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" generate-batch --input tmp/imagegen/prompts.jsonl --out-dir output/imagegen/batch
```

## Notes

- The wrapper prepares the Python `openai` package for live calls.
- `--partial-images` must be between `0` and `3`.
- `--output-format` may be `png`, `jpeg`, `jpg`, or `webp`.
- `--force` is required before overwriting an existing output.
- The helper defaults to streamed generation and editing.
