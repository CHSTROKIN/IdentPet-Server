"""
Each one of these objects represent translating parameters received from the user
by an API endpoint into a corresponding database document.
"""

from typing import Any, TypeAlias
from flask import jsonify, make_response, Response
import warnings as wn

from database import SightingDocument, AlertDocument

Warning: TypeAlias = str
API_BASE = "https://petfinder-424117.nw.r.appspot.com"

permissiveFloat = lambda x=None: float(x) if x else float()
permissiveInt = lambda x=None: int(x) if x else int()
permissiveBool = lambda x=None: bool(x) if x else bool()

class Specification:
    log_func = lambda a, b, c: None
    """Contains a specification for one API endpoint.
    Each of the _fields dictionaries is a mapping between a field and a type.
    Type coercion will occur when the field is received from the user if
    the field is present in the dictionary and the type is callable.
    
    Annotations gives special annotations for specific fields in the specification,
    including in required fields, optional fields, and response fields.
    The 'warnings' field is always implicit.
    """
    def __init__(self, name, endpoint, desc=None,
                 required_fields=None, optional_fields=None, database_map=None,
                 response_fields=None, annotations=None, method=None):
        self.name = name
        self.endpoint = endpoint
        self.desc = desc or "No description available."
        self.required_fields = required_fields or {}
        self.optional_fields = optional_fields or {}
        self.database_map = database_map or {}
        self.response_fields = response_fields or {}
        self.annotations = annotations or {}
        self.method = method or "GET"
    
    def interpret_request(self, data: dict[str, str], strict=False) -> tuple[dict[str, Any], list[Warning]]:
        """Interprets the request data according to the specification.
        In addition to warning about missing required fields, strict mode
        will also warn if any fields are present that are not in the specification."""
        interpreted = {}
        warnings = []
        required_fields = set(self.required_fields.keys())
        
        for field, value in data.items():
            new_name = self.database_map.get(field, field)
            if field in self.required_fields:
                interpreted[new_name] = self.required_fields[field](value)
                required_fields.remove(field)
            elif field in self.optional_fields:
                interpreted[new_name] = self.optional_fields[field](value)
            elif strict:
                warnings.append(f"Field '{field}' is not in the specification.")
                
        if required_fields:
            warnings.append(f"Missing required fields: {', '.join(required_fields)}.")
            
        return interpreted, warnings

    def response(self, response: dict[str, Any] | None = None,
                 warnings: list[Warning] | None = None,
                 code: int | None = None) -> Response:

        response = response or {}
        
        for key in response:
            if key not in self.response_fields:
                wn.warn(f"Response field '{key}' not in specification.")
                Specification.log_func(self.name, self.endpoint, [f"Response field '{key}' not in specification."])
        
        for key in self.response_fields:
            if key not in response:
                response[key] = self.response_fields[key]()
        
        response["warnings"] = response.get("warnings", []) + (warnings or [])
        code = code or (400 if warnings else 200)
        
        if response["warnings"]:
            Specification.log_func(self.name, self.endpoint, response["warnings"])

        return make_response(jsonify(response), code)

upload_image_spec = Specification(
    "Upload Image to Cloud Storage",
    "/image",
    "Uploads an image to the cloud storage bucket, returning its filename as id.",
    method="POST",
    required_fields={"base64": str},
    response_fields={"id": str}
)

sighting_spec = Specification(
    "Report a Sighting",
    "/sighting",
    "Reports a sighting of a pet, matching it with any alerts.",
    method="POST",
    optional_fields={
        "location_lat": permissiveFloat,
        "location_long": permissiveFloat,
        "location_desc": str,
        "description": str,
        "breed": str,
        "color": str,
        "other": str,
        "behaviour": str,
        "health": str,
        "image": str,
        "id": str,
        "chatID": str,
        "contactinfo": str,
        "message": str,
    },
    database_map={
        "specificLocation": "location_desc",
        "id": "pet_id",
        "chatID": "chat_id"
    },
    response_fields={
        "matchN": int
    },
    annotations={
        "image": f"Should be a cloud image path obtained from a call to {upload_image_spec.endpoint}.",
        "matchN": "The number of alerts matched by the sighting.",
        "chatID": "If set, indicates that the user is willing to be contacted about the sighting."
    }
)

pet_found_spec = Specification(
    "Report a Pet as Found",
    "/pet/found",
    "Reports a pet as found, removing any alerts associated with it.",
    method="POST",
    required_fields={"id": str}
)

pet_alert_spec_post = Specification(
    "Report a Pet as Lost",
    "/pet/alert",
    "Reports a pet as lost, creating an alert for it.",
    method="POST",
    required_fields={
        "id": str,
    },
    database_map={
        "id": "pet_id"
    },
    optional_fields={
        "animal": str,
        "breed": str,
        "description": str,
        "location_lat": permissiveFloat,
        "location_long": permissiveFloat,
        "condition": str,
        "more": str,
        "assistance": lambda x: str(x).lower() == "true",
        "name": str,
        "push_token": str,
        "size": str
    },
)

pet_alert_spec_get = Specification(
    "Get Alert Information",
    "/pet/alert",
    "Gets information about a pet alert and any matched sightings reported.",
    method="GET",
    required_fields={"id": str},
    response_fields={
        "animal": str,
        "breed": str,
        "description": str,
        "location_lat": permissiveFloat,
        "location_long": permissiveFloat,
        "condition": str,
        "more": str,
        "assistance": permissiveBool,
        "name": str,
        "sightings": list[SightingDocument],
        "push_token": str,
        "timestamp": str,
        "size": str,
        "contactinfo": str,
        "message": str
    },
    database_map={
        "id": "pet_id"
    },
    annotations={
        "sightings": f"A list of sightings that matched the alert (see §'{sighting_spec.name}' for more details). Note that 'specificLocation' is returned as 'location_desc' instead."
    }
)

pet_nearby_spec_get = Specification(
    "Get Nearby Alerts",
    "/pet/nearby",
    "Gets alerts that are nearby the provided location.",
    method="GET",
    required_fields={
        "location_lat": permissiveFloat,
        "location_long": permissiveFloat
    },
    optional_fields={
        "radius": permissiveFloat
    },
    response_fields={
        "alerts": list[AlertDocument]
    }
)

channel_spec = Specification(
    "Create a New Channel",
    "/channel",
    "Creates a new channel between the two provided chatIDs.",
    method="POST",
    required_fields={
        "chatID1": str,
        "chatID2": str
    }
)

get_specifications_by_endpoint = {
    "pet/alert": pet_alert_spec_get
}

post_specifications_by_endpoint = {
    "image": upload_image_spec,
    "sighting": sighting_spec,
    "pet/found": pet_found_spec,
    "pet/alert": pet_alert_spec_post
}
