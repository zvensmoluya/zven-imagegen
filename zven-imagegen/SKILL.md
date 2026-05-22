---
name: zven-imagegen
description: Generate or edit raster images through an OpenAI-compatible image endpoint with dedicated IMAGEGEN_* credentials and streamed partial-image progress. Use when Codex needs image generation behind a custom base_url, reverse proxy, Cloudflare-protected endpoint, or separate image API key instead of the built-in imagegen path.
---

# Zven Imagegen

Use this skill when image generation should go through a dedicated endpoint or
base URL instead of Codex's default image tool. The bundled wrapper keeps
`IMAGEGEN_OPENAI_API_KEY` and `IMAGEGEN_OPENAI_BASE_URL` separate from normal
OpenAI/Codex settings, and the Python helper streams progress to keep long image
requests active through proxies that dislike quiet connections.

## Quick Start

Run the PowerShell wrapper from any project:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.agents\skills\zven-imagegen\scripts\invoke-imagegen.ps1" generate `
  --prompt "A clean product cutout of a ceramic mug, no text, no logo" `
  --size 1024x1024 `
  --quality low `
  --out output\imagegen\mug.png
```

Or run the streamed helper directly:

```powershell
python "$HOME\.agents\skills\zven-imagegen\scripts\imagegen_stream.py" generate `
  --prompt "A clean product cutout of a ceramic mug, no text, no logo" `
  --out output\imagegen\mug.png
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
2. Use `generate`, `edit`, or `generate-batch` on
   `scripts/imagegen_stream.py` for streamed requests.
3. Prefer `IMAGEGEN_OPENAI_API_KEY` and `IMAGEGEN_OPENAI_BASE_URL` when the
   image endpoint differs from the rest of Codex.
4. Add `.agentonlyenv`, `.imagegen.env`, or `.env.imagegen` to the project root
   for repo-local private settings; keep real credentials out of git.
5. Keep prompts original and avoid requesting copied game, movie, brand, or
   copyrighted UI assets.

## Wrapper Behavior

`scripts/invoke-imagegen.ps1` forwards all CLI arguments. It uses:

1. A repo-local `scripts/imagegen_stream.py` if the current project provides one
2. This skill's bundled `scripts/imagegen_stream.py`
3. The installed `imagegen` skill CLI only when a forwarded option is not
   supported by the streamed helper

The streamed helper supports `generate`, `edit`, and `generate-batch`.
Generation and editing default to `--stream`; use `--no-stream` only when a
provider does not support streaming.

Calls using original imagegen-only prompt-augmentation or downscaling flags fall
back to the installed imagegen CLI when available.

For Python, the wrapper prefers the current project's `.venv`, then `python` on
`PATH`. Codex may already have Python because bundled skills use it, but the
`openai` package is not guaranteed in the chosen environment. If a live call
reports a missing dependency, install it with `python -m pip install openai` in
that environment.

## Common Commands

Dry-run without a network call:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.agents\skills\zven-imagegen\scripts\invoke-imagegen.ps1" generate `
  --prompt "Test image" `
  --out output\imagegen\test.png `
  --dry-run
```

Generate with streamed progress:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.agents\skills\zven-imagegen\scripts\invoke-imagegen.ps1" generate `
  --prompt "A polished landing-page hero image of a matte ceramic mug" `
  --size 1536x1024 `
  --quality medium `
  --partial-images 1 `
  --out output\imagegen\mug-hero.png
```

Edit an existing image:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.agents\skills\zven-imagegen\scripts\invoke-imagegen.ps1" edit `
  --image input.png `
  --prompt "Replace only the background with a warm studio backdrop" `
  --out output\imagegen\edited.png
```

Generate from JSONL:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.agents\skills\zven-imagegen\scripts\invoke-imagegen.ps1" generate-batch `
  --input tmp\imagegen\prompts.jsonl `
  --out-dir output\imagegen\batch
```

## Notes

- The helper requires the Python `openai` package for live calls.
- `--partial-images` must be between `0` and `3`.
- `--output-format` may be `png`, `jpeg`, `jpg`, or `webp`.
- `--force` is required before overwriting an existing output.
- The streamed helper intentionally avoids Codex system-skill patches, so it is
  stable across Codex updates.
