from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ResponseFormatter:

    @staticmethod
    def dump(object: BaseModel, expand: Optional[Dict[str, List[str]]] = None, exclude_defaults=False):
        """
        Expands pydantic objects and shows only the specified fields.

        :param expand: Dictionary where keys are field names to expand and values are lists of fields to include.
                       Example: {'club': ['name', 'location'], 'players': ['name', 'level']}
        :param exclude_defaults: Whether to exclude fields with default values.
        """
        data = object.model_dump(exclude_defaults=exclude_defaults)

        # Expands requested keys
        if expand:
            for field_name, included_fields in expand.items():
                value = getattr(object, field_name, None)
                if value:
                    # If it is a list of objects, process each element
                    if isinstance(value, list):
                        expanded_list = []
                        for item in value:
                            # Convert if it is a pydantic model
                            if isinstance(item, BaseModel):
                                expanded_list.append(item.model_dump(include=set(included_fields)))
                            else:
                                expanded_list.append(item)
                        data[field_name] = expanded_list
                    elif isinstance(value, BaseModel):
                        # If it is a single object
                        data[field_name] = value.model_dump(include=set(included_fields))
        return data


if __name__ == '__main__':

    from domain.club import Club


    club = Club(**{
            "id": "clubs/006",
            "state": "ENABLED",
            "name": "PADEL TRAINING",
            "address": None,
            "location": {
                "latitude": 40.3518425,
                "longitude": -3.5486913
            },
            "open_hours": {
                "opens": "09:00",
                "closes": "23:00"
            },
            "phone": None,
            "website": None,
            "courts": [
                {
                    "_id": "courts/006_001",
                    "state": "ENABLED",
                    "type": "SKU",
                    "name": "Pista 1",
                    "club": "clubs/006",
                    "cameras": [
                        "cameras/006_001_0",
                        "cameras/006_001_1"
                    ],
                    "_version": 1,
                    "_created": "2025-02-21T15:52:45.090000",
                    "_updated": "2025-02-21T15:52:45.090000"
                },
                {
                    "_id": "courts/006_002",
                    "state": "ENABLED",
                    "type": "SKU",
                    "name": "Pista 2",
                    "club": "clubs/006",
                    "cameras": [
                        "cameras/006_002_0",
                        "cameras/006_002_1"
                    ],
                    "_version": 1,
                    "_created": "2025-02-21T15:52:45.091000",
                    "_updated": "2025-02-21T15:52:45.091000"
                }
            ],
            "trainers": []
        })

    print(ResponseFormatter.dump(object=club, expand={'courts': ['id', 'name', 'state']}, exclude_defaults=True))