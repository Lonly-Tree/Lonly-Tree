# Install the profile

This package updates the existing public repository **Lonly-Tree/Lonly-Tree**.
The spelling is intentional: `Lonly-Tree`, without an `e`.

1. Clone your repository and copy the package contents into that checkout, including the hidden `.github` folder. Replace `README.md` and keep your existing certificate and other files.
2. Commit and push the changes to `main` using your usual GitHub login.
3. Open **Actions → Update profile art → Run workflow** to verify the first refresh.

The supplied assets already include real public contribution data, so the profile displays immediately. The workflow runs daily at 06:17 UTC; GitHub can delay scheduled runs. It uses GitHub's automatic workflow token for the commit, with `contents: write`; no personal access token is needed. Branch protection that disallows bot pushes must be handled using your repository's normal review process.

## Edit the content

Change `profile.json`, then use Python 3.11 or later:

```sh
python scripts/build_profile.py
```

No third-party Python packages are needed at runtime. To regenerate only the artwork using the saved calendar:

```sh
python scripts/build_profile.py --offline
```

The README uses a combined profile SVG to keep the ASCII tree and neofetch card aligned. Separate `tree.svg` and `info-card.svg` assets are also included. All artwork is generated locally, has accessible titles, and respects reduced-motion settings. The static content remains visible when CSS animation is unavailable.

## Data and maintenance

- Details and contact links come from your existing README; C++ comes from your public C++ repositories.
- Counts come from GitHub's public contribution-calendar HTML, including any private contribution totals you choose to expose publicly. Private project names are never requested.
- If GitHub changes its calendar markup, the updater fails instead of replacing the graph with invented or partial counts. Existing committed artwork remains available.
- GitHub may disable scheduled workflows in public repositories after prolonged inactivity; re-enable from the Actions tab when needed.
- Existing snake automation is retained. The new README uses the new contribution SVG instead of the snake or third-party stats widgets.

## Development checks

```sh
python -m pip install -r requirements-dev.txt
python -m pytest --cov=scripts.build_profile --cov-fail-under=90
python -m mypy --strict scripts/build_profile.py
python -m black --check scripts tests
python -m ruff check scripts tests
```

Inspired by [Avi Vashishta's animated GitHub README guide](https://www.avivashishta.com/blog/build-animated-github-profile-readme). The generator and ASCII tree in this package are original.
