import pytest
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert import HTMLExporter
from pathlib import Path
from typing import List
import tempfile

CELL_TIMEOUT = 600


def search_notebooks(directories: List[str]) -> List[str]:
    """
    Find all notebooks from given directories, looking inside directories, too.
    The searched extension is '.ipynb' (case-insensitive), and directories
    are not searched recursively.
    """
    notebooks = []
    for directory in directories:
        dir_path = Path(directory)
        if dir_path.is_dir():
            notebooks.extend(
                str(nb_path) for nb_path in dir_path.glob("*.ipynb") if not nb_path.stem.endswith("_executed")
            )
    return notebooks


def execute_notebook(nb_path: str, cell_timeout=CELL_TIMEOUT) -> bool:
    """
    Execute a single notebook and save the executed version.
    """
    try:
        nb_path = Path(nb_path)
        with nb_path.open() as f:
            notebook = nbformat.read(f, as_version=4)

        ExecutePreprocessor(timeout=cell_timeout, kernel_name="python3").preprocess(
            notebook, resources={"metadata": {"path": str(nb_path.parent)}}
        )
        executed_path = nb_path.with_stem(nb_path.stem + "_executed")
        with executed_path.open("w", encoding="utf-8") as f:
            nbformat.write(notebook, f)

        html_exporter = HTMLExporter()
        (body, resources) = html_exporter.from_notebook_node(notebook)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_html_file:
            temp_html_file.write(body.encode("utf-8"))

        return True
    except Exception as e:
        print(f"Error executing {nb_path}: {e}")
        return False
    finally:
        executed_path = Path(nb_path).with_stem(Path(nb_path).stem + "_executed")
        if executed_path.exists():
            executed_path.unlink()


@pytest.mark.parametrize("notebook_path", search_notebooks(["notebooks"]))
def test_published_notebooks(notebook_path):
    assert execute_notebook(notebook_path), f"Error executing {notebook_path}"
