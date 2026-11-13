# Contributing to MANJU STUDIO

Thanks for wanting to improve 漫构. This is a local-first project, so the most
important rule is: **do not commit model weights, API keys, local logs, or the
`.tools/` / `.venv/` directories.**

## Development setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8787
```

Open <http://127.0.0.1:8787>. The built-in art engine and sample work without
Ollama or ComfyUI.

Optional AI services:

```bash
./scripts/setup_ollama.sh      # script model, ~2GB
./scripts/setup_comfyui.sh     # ComfyUI + SD1.5 + IP-Adapter, ~7GB
```

## Checks

```bash
python3 -m compileall -q app scripts
node --check web/app.js
bash -n start.sh scripts/*.sh
```

No test suite exists yet; a manual render with the sample project is the
current smoke test.

## Code layout

| Path | Responsibility |
|---|---|
| `app/director.py` | story generation, deterministic fallback, Ollama rewrite |
| `app/art.py` | built-in procedural manga panels |
| `app/comfy.py` | ComfyUI HTTP client + API-format workflows |
| `app/illustrator.py` | character references, IP-Adapter shots, fallback |
| `app/audio.py` | timeline, procedural score, sound design, mix |
| `app/render.py` | bubbles, camera moves, MP4 encoding, covers |
| `app/main.py` | FastAPI endpoints and render jobs |
| `web/` | zero-build dashboard / studio |
| `skills/` | optional agent skill |

## Pull requests

- Keep the default experience zero-key: AI services must stay optional and
  fail soft.
- Do not add a hard dependency on a paid API.
- Do not commit generated projects or large media from your own runs.
- For UI changes, include a screenshot at desktop and mobile widths.
- For AI changes, mention which model/checkpoint and steps you tested.

## License

By contributing you agree that your contribution is licensed under the MIT
License in [LICENSE](LICENSE). Third-party components keep their own licenses.
