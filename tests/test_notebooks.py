###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import os
import tempfile
from pathlib import Path
from typing import List

import pytest

try:
    import nbformat
    from nbconvert import HTMLExporter
    from nbconvert.preprocessors import ExecutePreprocessor
    from jupyter_client.kernelspec import KernelSpecManager

    _NBCONVERT_AVAILABLE = True
except ImportError:
    _NBCONVERT_AVAILABLE = False


CELL_TIMEOUT = 60

_CREDENTIAL_FILENAMES = [
    "credentials.properties",
    "credentials.properties.txt",
    ".credentials.properties",
]

_CREDENTIAL_DIRS = [
    Path("notebooks"),
    Path.cwd(),
    Path(""),
    Path.home(),
    Path(os.environ.get("HOME", "")) / ".here",
]

_HERE_CREDENTIALS_FOUND = any((d / f).exists() for d in _CREDENTIAL_DIRS for f in _CREDENTIAL_FILENAMES)

# Skip the entire module when nbconvert is not installed or no HERE credentials are available.
pytestmark = [
    pytest.mark.skipif(
        not _NBCONVERT_AVAILABLE,
        reason="nbconvert is not installed (add the 'lab' extra to your environment)",
    ),
    pytest.mark.skipif(
        not _HERE_CREDENTIALS_FOUND,
        reason="no HERE credentials file found (checked notebooks/, cwd, ~/, ~/.here/)",
    ),
]

EXCLUDED_NOTEBOOKS = {
    "obm_6_profile",  # profiling/interactive notebook: requires live routing + map state
    "obm_4_auth",  # live token retrieval can timeout in CI-like environments
}


def search_notebooks(directories: List[str]) -> List[str]:
    """
    Find all notebooks from the given directories.
    The searched extension is '.ipynb' (case-insensitive), and directories
    are not searched recursively.
    """
    notebooks = []
    for directory in directories:
        dir_path = Path(directory)
        if dir_path.is_dir():
            notebooks.extend(
                str(nb_path)
                for nb_path in dir_path.glob("*.ipynb")
                if not nb_path.stem.endswith("_executed") and nb_path.stem not in EXCLUDED_NOTEBOOKS
            )
    return notebooks


def _has_python3_kernel() -> bool:
    """
    Return True if a 'python3' kernelspec is available in the current environment.
    """
    return "python3" in KernelSpecManager().find_kernel_specs()


def execute_notebook(nb_path: str, cell_timeout: int = CELL_TIMEOUT) -> bool:
    """
    Execute a single notebook with ipykernel ('python3'), independently of
    the kernel metadata stored in the notebook itself.

    The executed notebook is written temporarily as '<name>_executed.ipynb'
    and deleted afterwards.
    """
    executed_path = None

    try:
        nb_path = Path(nb_path)

        if not _has_python3_kernel():
            pytest.skip("python3 kernel is not installed in the current environment")

        with nb_path.open(encoding="utf-8") as f:
            notebook = nbformat.read(f, as_version=4)

        # Force notebook execution to use ipykernel, regardless of the original notebook metadata.
        notebook.setdefault("metadata", {})
        notebook["metadata"]["kernelspec"] = {
            "name": "python3",
            "display_name": "Python 3",
            "language": "python",
        }

        ExecutePreprocessor(
            timeout=cell_timeout,
            kernel_name="python3",
        ).preprocess(
            notebook,
            resources={"metadata": {"path": str(nb_path.parent)}},
        )

        executed_path = nb_path.with_stem(nb_path.stem + "_executed")
        with executed_path.open("w", encoding="utf-8") as f:
            nbformat.write(notebook, f)

        html_exporter = HTMLExporter()
        body, _resources = html_exporter.from_notebook_node(notebook)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_html_file:
            temp_html_file.write(body.encode("utf-8"))

        return True

    except pytest.skip.Exception:
        raise
    except Exception as e:
        print(f"Error executing {nb_path}: {e}")
        return False

    finally:
        if executed_path and executed_path.exists():
            executed_path.unlink()


@pytest.mark.parametrize("notebook_path", search_notebooks(["notebooks"]))
def test_published_notebooks(notebook_path):
    assert execute_notebook(notebook_path), f"Error executing {notebook_path}"
