# GENZLOG profile setup

This project generates the README art for the `Anguharikarthick17` GitHub profile. GitHub displays the root `README.md` from a public repository named exactly `Anguharikarthick17`.

## Install on macOS

Run from the project directory:

```bash
cd /Users/angu/Documents/github
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use `.venv/bin/python` for the commands below. The configured profile data is in `data/profile.json`; its `github_username` and `contribution_graph.username` are both `Anguharikarthick17`. Keep them equal if you edit the configuration.

## Generate profile artwork

Regenerate the information card:

```bash
.venv/bin/python scripts/make_info_card.py
```

To generate a personal ASCII portrait, pass a photo stored locally. The script reads but does not copy the photo:

```bash
.venv/bin/python scripts/make_ascii_svg.py --photo "/absolute/path/to/your/portrait.jpg"
```

Do not run the portrait command without `--photo` if you already have a real portrait asset: without a photo, it deliberately replaces the art with a clearly labeled placeholder. This project does not include a portrait photo.

## Fetch real GitHub contributions locally

`scripts/fetch_contributions.py` sends a `POST` to `https://api.github.com/graphql` and queries the configured user's contribution calendar. It authenticates with an HTTP `Authorization: Bearer ...` header whose value comes only from the `PROFILE_READ_TOKEN` environment variable. It does not automatically use `gh` credentials.

### Minimum token access

Create a short-lived **personal access token (classic)** with **no scopes selected**. GitHub documents that a classic token with no scopes can read public information. This fetch is for the public calendar; it needs no repository, organization, or write access. Do not use your broad GitHub CLI credential for this task. If GitHub returns a permissions error, leave `data/contributions.json` unchanged and investigate the API response instead of adding broad scopes.

### Exact macOS fetch commands

After creating the token, run the following from the project directory. The prompt is hidden. The token is passed to the fetcher process in the expected environment variable and is not saved to shell history, a file, or logs:

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

The fetcher only writes `data/contributions.json` after a successful and validated response. If the username is unavailable, authentication fails, the API rate limit is hit, or the response shape changes, it reports an error and leaves existing contribution JSON untouched. The SVG encodes GitHub's `NONE`, `FIRST_QUARTILE`, `SECOND_QUARTILE`, `THIRD_QUARTILE`, and `FOURTH_QUARTILE` contribution levels; hover a day for its date and exact count. No sample data is used as actual activity.

## GitHub Actions configuration

The workflow is `.github/workflows/update-profile-art.yml`:

- Manual trigger: **workflow_dispatch**.
- Schedule: Mondays at `06:23 UTC` (`23 6 * * 1`).
- Python: `3.12`.
- API credential: Actions repository secret `PROFILE_READ_TOKEN`, injected into the fetch step as environment variable `PROFILE_READ_TOKEN`.
- Commit credential: the built-in `GITHUB_TOKEN` provided by `actions/checkout`; it is not the profile-read secret.
- Workflow permission: `contents: write` only, for committing the generated JSON and heatmap SVG.

Set it up in the profile repository:

1. Go to **Settings → Secrets and variables → Actions → New repository secret**. Name it `PROFILE_READ_TOKEN` and paste the short-lived no-scope classic token. Do not put it in the repository, profile JSON, workflow, or README.
2. Go to **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions**. The workflow still requests only `contents: write`; without repository write permission, its commit/push step cannot update generated art.
3. Ensure Actions are enabled. Open **Actions → Update profile contribution art → Run workflow** for a manual run. Review the run logs if it fails; secrets are not echoed by the workflow.

The API secret can only read public data; the repository-scoped `GITHUB_TOKEN` separately writes the generated files. Do not grant the API token repository write permissions.

## Preview and publish

Preview the root `README.md` with VS Code's Markdown preview. The README refers to `assets/ascii-portrait.svg`, `assets/info-card.svg`, and `assets/contrib-heatmap.svg` using relative paths.

The profile repository has to be named exactly `Anguharikarthick17`. This project does not configure remotes or publish changes. Do not run `git push` until you explicitly decide to publish.

The configured project URLs match their configured repository names. In an anonymous GitHub API check, `EcoRoute`, `AudienceIQ`, and `BlackBox---Ai` were publicly available; `CHESS-GAME`, `AHK-MINI`, `AHK-DYNAMIC-ISLAND`, and `AHK-RESUME` returned 404. A 404 can mean a repository is private or does not exist at that URL. Verify those four in your GitHub account and make them public or remove/update their profile links before expecting visitors to open them.

## Troubleshooting

- **`PROFILE_READ_TOKEN` missing:** create the no-scope classic token, then use the hidden-prompt command above. The fetcher changes no data without it.
- **401/403 or rate limit:** verify the token is valid and retry after rate limits reset. Do not paste the token into a log, issue, or chat.
- **Unknown GraphQL user/calendar:** check that `github_username` and `contribution_graph.username` both identify `Anguharikarthick17`.
- **Heatmap says data unavailable:** run the authenticated fetch successfully, then run `scripts/render_heatmap_svg.py`. Never substitute synthetic data as actual activity.
- **Workflow cannot push:** enable Actions read/write workflow permissions and check branch protections; the workflow requires `contents: write`.
- **Changed profile card is not reflected:** run `.venv/bin/python scripts/make_info_card.py`.
- **Portrait placeholder:** provide your own local photo using the portrait command above; the original photo is not part of the repository.
