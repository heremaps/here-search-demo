---
hide-toc: true
---

# Update the package

The release tools run through [uv](https://docs.astral.sh/uv/): `uvx` runs `bumpver` and `twine` without installing them, and `uv build` builds the package.

1. Check that the `Python package` workflow (`test.yml`) is enabled. It has a daily `schedule` trigger, and GitHub automatically disables scheduled workflows of a public repository after 60 days without repository activity. While it is disabled, the PR checks and the daily run do not start. Re-enable it in the repository’s Actions tab (select `Python package`, then “Enable workflow”), or run `gh workflow enable test.yml --repo heremaps/here-search-demo`. `gh workflow list --all --repo heremaps/here-search-demo` shows its state.
2. Create a release branch from `main`, for example `git checkout -b release/<version>`.
3. Make the code/doc/notebook changes that the new release requires (bug fixes, dependency updates, README notes, etc.), then commit and push those updates so they land on the release branch.
4. Preview the bump with `uvx bumpver update --set-version <version> --dry --no-fetch`. It lists the changes to `pyproject.toml`, `src/here_search_demo/__init__.py` and the project `README.md`.
5. Run the same command without `--dry` and `--no-fetch`. `bumpver` updates those files, creates the version commit, tags it, and pushes the commit and the tag to the remote.
6. Optionally check the package locally: `rm -rf dist && uv build && uvx twine check dist/*`. Remove `dist/` first, because the build adds to the files already there. Do not upload from your machine: the release workflow publishes to PyPI.
7. Open a PR from your release branch.
8. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
9. After the PR merges into `main`, use “Draft a new release” in GitHub and select the tag created by bumpver.
10. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.
