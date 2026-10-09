# GENZLOG profile setup

This repository generates the README art for the `Anguharikarthick17` GitHub profile. GitHub uses the root `README.md` from a public repository named exactly `Anguharikarthick17`.

## Install on macOS

Run from the project directory:

```bash
cd /Users/angu/Documents/github
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use `.venv/bin/python` for the commands below. Update `data/profile.json` to change profile content. Keep `github_username` and `contribution_graph.username` equal. Confirm that the configured bio's "Second-year undergraduate student" detail is accurate before publishing.

## Generate the profile artwork

The original photo is `photos/portrait.jpg`, which is excluded from Git. The generator reads the local photo and creates a text-based SVG; it never copies or embeds the source image.

```bash
.venv/bin/python scripts/make_ascii_svg.py \
  --photo photos/portrait.jpg \
  --columns 160 \
  --brightness 1.0 \
  --contrast 1.15 \
  --crop subject
.venv/bin/python scripts/make_info_card.py
.venv/bin/python scripts/render_heatmap_svg.py
```

The portrait generator crops around darker foreground pixels with a default grayscale threshold of `232`. Use `--crop full` or adjust `--background-threshold` for a photo with a different background. Running the portrait generator without `--photo` deliberately writes a labeled placeholder, so do not omit the photo argument when keeping the current portrait.

## Fetch real GitHub contributions locally

`scripts/fetch_contributions.py` queries the public contribution calendar through `https://api.github.com/graphql`. It reads its authorization value only from `PROFILE_READ_TOKEN`, does not automatically use `gh` credentials, and never prints the token.

The fetcher requires a token that can read public profile data. A fine-grained or classic token with the minimum public-read access supported by GitHub is sufficient; it needs no repository write permission. For a classic token, select no scopes. If GitHub rejects the token, do not add repository write scopes: inspect the API access configuration instead.

To enter the token privately and pass it only to the fetcher process, run this from the project directory:

```bash
cd /Users/angu/Documents/github
set -e
python3 - <<'PY'
import getpass
import os
import subprocess

env = os.environ.copy()
env["PROFILE_READ_TOKEN"] = getpass.getpass("GitHub public-read token (input hidden): ")
subprocess.run(
    [".venv/bin/python", "scripts/fetch_contributions.py"],
    env=env,
    check=True,
)
PY
.venv/bin/python scripts/render_heatmap_svg.py
```

The fetcher validates the response, dates, contribution counts, contribution-level enum values, and calendar total before atomically replacing `data/contributions.json`. On failure, it leaves the last valid JSON unchanged. The heatmap uses GitHub's `NONE`, `FIRST_QUARTILE`, `SECOND_QUARTILE`, `THIRD_QUARTILE`, and `FOURTH_QUARTILE` levels; each SVG day title contains the date and exact count. The colors indicate levels, not exact counts. No sample data is presented as real activity.

## GitHub Actions

`.github/workflows/update-profile-art.yml` provides manual `workflow_dispatch` and a weekly Monday schedule (`06:23 UTC`). It uses Python 3.12. The fetch step receives the repository Actions secret `PROFILE_READ_TOKEN` as an environment variable. The workflow uses the built-in `GITHUB_TOKEN` only for checkout and repository updates; the update job asks for `contents: write` and commits only the contribution JSON and heatmap SVG when those files change.

Configure the profile repository:

1. Under **Settings → Secrets and variables → Actions**, add a repository secret named `PROFILE_READ_TOKEN`. Use a token with public profile read access only; never put it in source files, profile JSON, workflow YAML, or logs.
2. Under **Settings → Actions → General → Workflow permissions**, allow read and write permissions for `GITHUB_TOKEN`. The workflow requests only `contents: write`. Branch protection can still prevent its commit.
3. Ensure Actions are enabled. Open **Actions → Update profile contribution art → Run workflow** to run it manually.

If the secret is missing, the fetcher fails clearly without replacing the last valid contribution data or exposing credentials. The workflow does not change the local portrait or the information card.

## Preview and publish

Use VS Code's Markdown preview for `README.md`. The local artwork paths are `assets/ascii-portrait.svg`, `assets/info-card.svg`, and `assets/contrib-heatmap.svg`.

The profile repository must be named exactly `Anguharikarthick17`. This setup does not configure remotes or publish anything. Review changes locally; commit or push only when you choose to do so.

All configured project URLs match the repository names. Earlier anonymous checks found `EcoRoute`, `AudienceIQ`, and `BlackBox---Ai`; the other 16 URLs returned 404. A 404 may mean the repository is private or unavailable. The project names and configured URLs remain in the profile; verify visibility and existence in GitHub if a link is inaccessible.

## Troubleshooting

- **`PROFILE_READ_TOKEN` missing:** use the hidden-input command above locally, or add the Actions secret under repository settings.
- **401/403 or rate limit:** check token validity and retry after rate limits reset. Do not paste the token into logs, issues, or chat.
- **Unknown user/calendar:** confirm both configured usernames are `Anguharikarthick17`.
- **Fetch failure:** the previous contribution JSON is preserved. Fix the API/authentication problem and rerun the fetch before rendering.
- **Workflow cannot push:** enable Actions `GITHUB_TOKEN` read/write permissions and check branch protection; the workflow needs `contents: write`.
- **Profile card is stale:** run `.venv/bin/python scripts/make_info_card.py`.
- **Portrait is a placeholder:** provide a local photo with `--photo`; the source photo must remain under the ignored `photos/` folder and is never published by the generator.
