---
hide-toc: true
---

# Contributing

Contributor-facing workflows: local environment setup, building the docs, and
shell-script quality checks. Deeper build internals and the release runbook live
on their own pages.

```{toctree}
:maxdepth: 1

build-infrastructure.md
release-process.md
appendix.md
```

## Setup a Notebook Python environment

```shell
uv pip install -e '.[dev,docs,lab]'
```

Also install `micromamba`.

To use JupyterLab, you will need a `ipykernel`:

```shell
prefix=$(python -c "import sys; print(sys.prefix)")
jupyter kernelspec uninstall search_demo
python -m ipykernel install --prefix $prefix --name search_demo --display-name "search demo"
```

## Build the docs

To build the Sphinx docs locally, you need to create the JupyterLite sites first
(see [Build infrastructure](build-infrastructure.md) for what `xeus.sh` produces and
the channel/CI constraints):

```shell
jupyterlite_build/xeus.sh
```

And then inject the docs:

```shell
sphinx-build -b html docs/ workspace/public/docs
```

The HTML output is written to `workspace/public/docs/index.html`.

To preview it locally:

```shell
python -m http.server 8000 --directory workspace/public
```

Then open `http://localhost:8000/docs/`.

## Shell script checks

Use these commands from the repository root for shell script quality checks in `scripts/*.sh`.

Required tools:
- `shfmt`
- `shellcheck`
- `bashate`

Install on macOS:

```shell
brew install shfmt shellcheck
uv tool install bashate
```

Auto-fix formatting, then run linters:

```shell
shfmt -w jupyterlite_build/*.sh && shellcheck jupyterlite_build/*.sh && bashate -i E002,E003,E006 jupyterlite_build/*.sh
```

Check-only mode (no formatting changes):

```shell
shellcheck jupyterlite_build/*.sh && shfmt -d jupyterlite_build/*.sh && bashate -i E002,E003,E006 jupyterlite_build/*.sh
```
