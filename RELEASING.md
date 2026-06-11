# Releasing aion-redteam

This project ships two ways: a **public GitHub repo** (source, issues, contributions) and
**PyPI** (`pip install aion-redteam`). There is no server to deploy — aion-redteam is a
CLI tool that users run locally against their own agents.

The normal release flow is fully automated: **push a version tag and CI publishes to
PyPI** via Trusted Publishing (no tokens stored in the repo). The manual steps below are
only needed once for setup, or as a fallback.

---

## 0. One-time: create the GitHub repo and push

```bash
# Create the repo on github.com/Cypharia/aion-redteam (public), then:
git remote add origin https://github.com/Cypharia/aion-redteam.git
git push -u origin main
```

CI (`.github/workflows/ci.yaml`) runs on every push/PR: lint, scenario validation, and
tests on Python 3.11 + 3.12.

---

## 1. One-time: configure PyPI Trusted Publishing

Trusted Publishing lets GitHub Actions upload to PyPI with no API token.

1. Make sure the project name `aion-redteam` is available on https://pypi.org. If it is
   already taken, pick a new `name` in `pyproject.toml` (and re-check on PyPI).
2. On PyPI: **Account → Publishing → Add a pending publisher** with:
   - **PyPI Project Name:** `aion-redteam`
   - **Owner:** `Cypharia`
   - **Repository name:** `aion-redteam`
   - **Workflow name:** `release.yaml`
   - **Environment name:** `pypi`
3. On GitHub: **Settings → Environments → New environment** named `pypi` (optionally add
   required reviewers so a human approves each publish).

Do the same on https://test.pypi.org if you want a TestPyPI dry-run target (see §4).

---

## 2. Pre-release checklist

```bash
# In the project venv:
ruff check src tests examples            # lint clean
pytest -q                                # all green (e2e skips without a key)
aion-redteam validate src/aion_redteam/scenarios   # 20/20 valid
uv build --native-tls                    # wheel + sdist build
uvx twine check dist/*                   # metadata valid
```

Bump the version in **one** place (the build reads it from here automatically):

- `src/aion_redteam/__init__.py` → `__version__`

Move the `CHANGELOG.md` `[Unreleased]` notes under a new `## [x.y.z] - YYYY-MM-DD`
heading, then commit:

```bash
git add -A
git commit -m "chore(release): v0.1.0"
git push
```

---

## 3. Cut the release (automated path)

```bash
git tag v0.1.0      # tag MUST match the version in pyproject.toml
git push --tags
```

The `Release` workflow then:

1. Builds the sdist + wheel and runs `twine check`.
2. Publishes to PyPI via Trusted Publishing (the `pypi` environment).
3. Creates a GitHub Release with auto-generated notes and attaches the artifacts.

Verify:

```bash
pip install aion-redteam==0.1.0
aion-redteam --version
```

---

## 4. Optional: TestPyPI dry-run

To rehearse without touching real PyPI:

```bash
uv build --native-tls
# Token-based upload to TestPyPI (create a token at test.pypi.org → Account → API tokens):
uvx twine upload --repository testpypi dist/*
# Then install from TestPyPI to smoke-test:
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ aion-redteam
```

---

## 5. Fallback: manual token-based publish

If Trusted Publishing isn't set up yet, publish from your machine with an API token:

```bash
uv build --native-tls
# Create a token at pypi.org → Account → API tokens (scope: project or account).
UV_PUBLISH_TOKEN=pypi-XXXX uv publish --native-tls
# or:  uvx twine upload dist/*      (username __token__, password = the token)
```

> Treat PyPI tokens like passwords. Prefer Trusted Publishing so no token is ever stored.

---

## Versioning

Follows [SemVer](https://semver.org). During `0.x`, minor bumps may include breaking
changes; document them in `CHANGELOG.md`.
