# The Daily Drop · feed

Public quote feed for The Daily Drop Android app.

- `feed/v1/today.json` is what the app downloads. It holds the latest quote for every category.
- `feed/v1/history/` keeps past quotes so new ones never repeat.
- `.github/workflows/daily.yml` runs `scripts/generate.py` every day at 00:05 IST. It calls TokenHarbor (`deepseek-v4.1-flash:free`, with free fallbacks) once per category.
- `docs/` is the GitHub Pages site with the privacy policy.

## Setup

1. Add the secret `TOKENHARBOR_API_KEY` under Settings → Secrets and variables → Actions.
2. Optional: set a repository variable to change models. The script reads `TOKENHARBOR_MODELS` as a comma-separated list.
3. Enable Pages under Settings → Pages → Deploy from branch → `main` / `docs`.
4. Run the workflow once by hand from the Actions tab to check it.

To add a category, add it to `categories.json`. The app picks up new categories from `today.json` automatically.
