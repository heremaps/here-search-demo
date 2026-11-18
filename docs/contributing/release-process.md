---
hide-toc: true
---

# Update the package

The release tools run through [uv](https://docs.astral.sh/uv/): `uvx` runs `bumpver` and `twine` without installing them, and `uv build` builds the package.

## Release

1. Check that the `Python package` workflow (`test.yml`) is enabled. It has a daily `schedule` trigger, and GitHub automatically disables scheduled workflows of a public repository after 60 days without repository activity. The `keepalive` job of `test.yml` re-enables the workflow on every scheduled run to prevent that, so this step is a fallback for when it has been disabled anyway. While it is disabled, the PR checks and the daily run do not start. Re-enable it in the repository’s Actions tab (select `Python package`, then “Enable workflow”), or run `gh workflow enable test.yml --repo heremaps/here-search-demo`. `gh workflow list --all --repo heremaps/here-search-demo` shows its state.
2. Merge the code, doc and notebook changes of the release through regular PRs, without touching the version. `main` keeps the previous version until the bump.
3. Update your checkout: `git switch main && git pull`.
4. Preview the bump with `uvx bumpver update --set-version <version> --dry --no-fetch`. It lists the changes to `pyproject.toml`, `src/here_search_demo/__init__.py` and the project `README.md`.
5. Optionally check the package locally: `rm -rf dist && uv build && uvx twine check dist/*`. Remove `dist/` first, because the build adds to the files already there. Do not upload from your machine: the release workflow publishes to PyPI.
6. Run `uvx bumpver update --set-version <version>`. `bumpver` updates those files, creates the version commit on `main`, tags it, and pushes the commit and the tag. This works only if you are allowed to push to `main` (see the branch protection of the repository). If the push is rejected, undo the local changes with `git tag -d <version>` and `git reset --hard origin/main`, then follow the release branch route below.
7. Check that the `test.yml` jobs for the version commit finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
8. Use “Draft a new release” in GitHub and select the tag created by bumpver.
9. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.

## Release branch route

Use this when `main` does not accept direct pushes. The version commit goes through a PR, and the tag is created on `main` after the merge.

1. Do steps 1 to 4 above. Then create a release branch: `git switch -c release/<version>`.
2. Run `uvx bumpver update --set-version <version> --no-tag-commit --no-push`. `bumpver` updates the files and creates the version commit, but creates no tag and pushes nothing. Then push the branch: `git push origin release/<version>`.

    The tag is created later, on `main`. A tag made on the release branch would point to a commit that does not exist on `main` after a squash merge.

3. Open a PR from the release branch. It contains only the version commit.
4. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo.
5. Merge the PR into `main`, then check that `main` is at the version commit (`git fetch origin && git show origin/main:pyproject.toml | grep current_version`).
6. Use “Draft a new release” in GitHub. Choose “Create new tag on publish”, enter `<version>` as the tag name, and set the target to `main`. If other commits landed on `main` after the version commit, select the version commit as the target instead.
7. Publishing the release creates the tag, triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.
8. Run `git fetch --tags origin` in your checkout, so that the next `bumpver` run sees the new tag as the latest version.
