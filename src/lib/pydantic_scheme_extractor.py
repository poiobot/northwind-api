from pydantic import BaseModel
from typing import Dict
from datetime import datetime


class SchemeExtractor:

    @staticmethod
    def extract_class_scheme(entity: BaseModel):
        """
        Extracts a pydantic object metadata separating keys and types from reference fields
        :param entity: a pydantic object
        :return: a dictionary of key-value pairs describing the object's metadata
        """

        def extract_references(metadata: Dict):
            references = {}

            for key, metadata in metadata.items():
                # Check if the field contains a "table" key (indicating a reference)
                if "table" in metadata:
                    is_array = False

                    # Check if "type" is "array" or nested dictionaries contain "type": "array"
                    if metadata.get("type") == "array":
                        is_array = True
                    elif "anyOf" in metadata:
                        # Traverse through anyOf elements to find "type": "array"
                        for option in metadata["anyOf"]:
                            if isinstance(option, dict) and option.get("type") == "array":
                                is_array = True
                                break
                    elif "items" in metadata:
                        # Check nested "items" for "type": "array"
                        items = metadata.get("items")
                        if isinstance(items, dict) and items.get("type") == "array":
                            is_array = True

                    # Add to references with "table" and "is_array"
                    references[key] = {"table": metadata["table"], "is_array": is_array}

            return references

        def get_field_type(field_metadata: Dict) -> str:
            """
            Determines the field type, checking for datetime format
            """
            field_type = field_metadata.get("type", "str")

            # Check if it's a datetime field (format: "date-time")
            if field_metadata.get("format") == "date-time":
                return "datetime"

            # Check in anyOf for datetime format
            if "anyOf" in field_metadata:
                for option in field_metadata["anyOf"]:
                    if isinstance(option, dict) and option.get("format") == "date-time":
                        return "datetime"

            return field_type

        schema = entity.model_json_schema(by_alias=False)
        properties = schema.get("properties", None)
        ename = entity.__name__
        if not properties:
            # ename = schema['$ref'].split('/')[-1]
            properties = schema['$defs'][ename].get('properties', {})

        # Extract reference fields (contain the "table" key)
        references = extract_references(properties)
        properties = {key: get_field_type(properties[key]) for key in properties.keys()}
        return {"class": ename, "table": references["id"]["table"], "properties": properties,
                "references": references}
