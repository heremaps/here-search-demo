---
hide-toc: true
---

# Update the package

The release tools run through [uv](https://docs.astral.sh/uv/): `uvx` runs `bumpver` and `twine` without installing them, and `uv build` builds the package.

1. Create a release branch from `main`, for example `git checkout -b release/<version>`.
2. Make the code/doc/notebook changes that the new release requires (bug fixes, dependency updates, README notes, etc.), then commit and push those updates so they land on the release branch.
3. Preview the bump with `uvx bumpver update --set-version <version> --dry --no-fetch`. It lists the changes to `pyproject.toml`, `src/here_search_demo/__init__.py` and the project `README.md`.
4. Run the same command without `--dry` and `--no-fetch`. `bumpver` updates those files, creates the version commit, tags it, and pushes the commit and the tag to the remote.
5. Optionally check the package locally: `rm -rf dist && uv build && uvx twine check dist/*`. Remove `dist/` first, because the build adds to the files already there. Do not upload from your machine: the release workflow publishes to PyPI.
6. Open a PR from your release branch.
7. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
8. After the PR merges into `main`, use “Draft a new release” in GitHub and select the tag created by bumpver.
9. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.
