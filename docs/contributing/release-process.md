---
hide-toc: true
---

# Update the package

The release tools run through [uv](https://docs.astral.sh/uv/): `uvx` runs `bumpver` and `twine` without installing them, and `uv build` builds the package.

1. Check that the `Python package` workflow (`test.yml`) is enabled. It has a daily `schedule` trigger, and GitHub automatically disables scheduled workflows of a public repository after 60 days without repository activity. The `keepalive` job of `test.yml` re-enables the workflow on every scheduled run to prevent that, so this step is a fallback for when it has been disabled anyway. While it is disabled, the PR checks and the daily run do not start. Re-enable it in the repository’s Actions tab (select `Python package`, then “Enable workflow”), or run `gh workflow enable test.yml --repo heremaps/here-search-demo`. `gh workflow list --all --repo heremaps/here-search-demo` shows its state.
2. Merge the code, doc and notebook changes of the release through regular PRs, without touching the version. `main` keeps the previous version until the release PR below is merged.
3. Create a release branch from the updated `main`, for example `git switch main && git pull && git switch -c release/<version>`.
4. Preview the bump with `uvx bumpver update --set-version <version> --dry --no-fetch`. It lists the changes to `pyproject.toml`, `src/here_search_demo/__init__.py` and the project `README.md`.
5. Run `uvx bumpver update --set-version <version> --no-tag-commit --no-push`. `bumpver` updates those files and creates the version commit, but creates no tag and pushes nothing. Then push the branch: `git push origin release/<version>`.

    The tag is created later, on `main`. A tag made on the release branch would point to a commit that does not exist on `main` after a squash merge.

6. Optionally check the package locally: `rm -rf dist && uv build && uvx twine check dist/*`. Remove `dist/` first, because the build adds to the files already there. Do not upload from your machine: the release workflow publishes to PyPI.
7. Open a PR from the release branch. It contains only the version commit.
8. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
9. Merge the PR into `main`, then check that `main` is at the version commit (`git fetch origin && git show origin/main:pyproject.toml | grep current_version`).
10. Use “Draft a new release” in GitHub. Choose “Create new tag on publish”, enter `<version>` as the tag name, and set the target to `main`. If other commits landed on `main` after the version commit, select the version commit as the target instead.
11. Publishing the release creates the tag, triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.
12. Run `git fetch --tags origin` in your checkout, so that the next `bumpver` run sees the new tag as the latest version.
