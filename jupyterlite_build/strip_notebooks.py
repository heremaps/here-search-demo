import json
from pathlib import Path
import argparse


def strip_notebook(nb_path: Path):
    """
    Strip the output cells of a notebook.

    Args:
        nb_path: Path to the notebook file

    Returns: None
    """
    with open(nb_path, "r") as f:
        notebook = json.load(f)

    for cell in notebook.get("cells", []):
        cell["outputs"] = []
        cell["execution_count"] = None

    metadata = notebook.get("metadata", {})
    metadata.pop("widgets", None)

    nb_path.write_text(json.dumps(notebook, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--notebooks-dir", type=Path, required=True, help="Directory containing notebooks")

    args = parser.parse_args()
    if not args.notebooks_dir.is_dir():
        print(f"Error: {args.notebooks_dir} is not a directory")
        return 1

    for nb_path in sorted(args.notebooks_dir.glob("*.ipynb")):
        strip_notebook(nb_path)
        print(f"Stripped: {nb_path.name}")

    return 0


if __name__ == "__main__":
    exit(main())
