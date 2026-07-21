---
hide-toc: true
---

# Update the package

The release runbook, split by platform. These steps are intended for a human
maintainer.

## gitlab part

1. Ensure that `ruff check src tests scripts` and `pytest` succeed.
2. Ensure that the hidden gitlab variable `CI_PRIVATE_TOKEN` is valid.
3. Ensure that all needed changes are committed and pushed.
4. Check the gitlab pipeline ran successfully
5. Run `bumpver update --set-version <release> --dry`
6. Check the changes
7. Run the same command without `--dry`

    `bumpver` will automatically:
    - Update the version in all specified files.
    - Commit the changes.
    - Tag the commit with the new version.
    - Push the commit and the tag to the GitLab repository.

8. Check the gitlab pipeline ran successfully and that the artifacts are uploaded in the related gitlab release
9. Build the new wheel with `python -m build --sdist --wheel`
10. Upload it to HERE artifactory with `twine upload --repository-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi dist/*`
11. Trigger the latest gitlab `pages` job
12. Check the JupyterLite static page works
13. Check the drop in of `here-search-demo.zip` content in a JupyterLab env works

## github part

1. Create a release branch from `main`, for example `git checkout -b release/<version>`.
2. Make the code/doc/notebook changes that the new release requires (bug fixes, dependency updates, README notes, etc.), then commit and push those updates so they land on the release branch.
3. Run `bumpver update --set-version <version>` on that branch. The command will update `pyproject.toml`, `_install.py`, this file, create the version commit, tag it, and push to the remote.
4. Open a PR from your release branch.
5. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
6. After the PR merges into `main`, use “Draft a new release” in GitHub and select the tag created by bumpver.
7. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.
