---
hide-toc: true
---

# Update the package

1. Create a release branch from `main`, for example `git checkout -b release/<version>`.
2. Make the code/doc/notebook changes that the new release requires (bug fixes, dependency updates, README notes, etc.), then commit and push those updates so they land on the release branch.
3. Run `bumpver update --set-version <version>` on that branch. The command will update `pyproject.toml`, `_install.py`, this file, create the version commit, tag it, and push to the remote.
4. Open a PR from your release branch.
5. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
6. After the PR merges into `main`, use “Draft a new release” in GitHub and select the tag created by bumpver.
7. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.
