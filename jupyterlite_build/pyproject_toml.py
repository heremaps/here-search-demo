###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import re
import sys


def pkg_name(dep: str) -> str:
    """Extract package name from dependency string."""
    return re.split(r"[>=<!;\[ ]", dep)[0].strip()


def collect_specs(
    project: dict,
    extras: list[str] | None = None,
    base_line_spec: list[str] | None = None,
) -> dict[str, str]:
    groups = [project.get("dependencies", [])]
    optional = project.get("optional-dependencies", {})

    for extra in extras or []:
        if extra not in optional:
            print(f"Warning: extra '{extra}' not found", file=sys.stderr)
        else:
            groups.append(optional[extra])

    spec_by_name = {name: name for name in (base_line_spec or [])}

    for group in groups:
        for dep in group:
            name = pkg_name(dep)
            spec_by_name.setdefault(name, dep)

    return spec_by_name
