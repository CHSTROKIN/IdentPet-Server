from google.cloud import storage    # type: ignore
from google.cloud import firestore  # type: ignore
import uuid

from enum import Enum
from typing import TypeAlias
import datetime

from model import embed_image_from_url
# from google.cloud.firestore_v1.vector import Vector # type: ignore

PetID: TypeAlias = str
CloudFilePath: TypeAlias = str
ImageURL: TypeAlias = str

# Not actually associated with a database collection.
class SightingDocument:
    def __init__(self, match_with: list[PetID],
        location_lat:  float | None = None, location_long: float | None = None,
        location_desc: str   | None = None, description:   str   | None = None,
        breed:         str   | None = None, color:         str   | None = None,
        other:         str   | None = None, behaviour:     str   | None = None,
        health:        str   | None = None, image:         CloudFilePath | None = None,
        image_url:     ImageURL | None = None,
        message:       str | None = None,
        chat_id:       str   | None = None,
        push_token:    str   | None = None,
        contactinfo:   str | None = None,
        timestamp:     datetime.datetime | None = None,
        embedding:     str | None = None):
        
        self.location_lat = location_lat
        self.location_long = location_long
        self.location_desc = location_desc
        self.description = description
        self.breed = breed
        self.color = color
        self.other = other
        self.behaviour = behaviour
        self.health = health
        self.match_with = match_with
        self.image = image
        self.image_url = image_url
        self.chat_id = chat_id
        self.timestamp = timestamp
        self.message = message
        self.contactinfo = contactinfo
        self.embedding = embedding
        self.push_token = push_token
    
    @staticmethod
    def from_dict(data, generate_timestamp=False):
        return SightingDocument(
            location_lat=data.get('location_lat'),
            location_long=data.get('location_long'),
            location_desc=data.get('location_desc'),
            description=data.get('description'),
            breed=data.get('breed'),
            color=data.get('color'),
            other=data.get('other'),
            behaviour=data.get('behaviour'),
            health=data.get('health'),
            match_with=data.get('match_with'),
            image=data.get('image'),
            image_url=data.get('image_url'),
            chat_id=data.get('chat_id'),
            message=data.get('message'),
            contactinfo=data.get('contactinfo'),
            timestamp=data.get('timestamp',
                               datetime.datetime.now(tz=datetime.timezone.utc) if generate_timestamp else None),
            embedding=data.get('embedding'),
            push_token=data.get('push_token')
        ) # Timestamp is rather hacky, but should work.
    def to_dict(self, stringify_timestamp=False):
        return {
            'location_lat': self.location_lat,
            'location_long': self.location_long,
            'location_desc': self.location_desc,
            'description': self.description,
            'breed': self.breed,
            'color': self.color,
            'other': self.other,
            'behaviour': self.behaviour,
            'health': self.health,
            'match_with': self.match_with,
            'image': self.image,
            'image_url': self.image_url,
            'chat_id': self.chat_id,
            'message': self.message,
            'timestamp': str(self.timestamp) if stringify_timestamp else self.timestamp,
            'contactinfo': self.contactinfo,
            'embedding': self.embedding,
            'push_token': self.push_token
        }

# Associated with the 'alerts' collection.
class AlertDocument:
    def __init__(self, sightings: list[SightingDocument],
        pet_id:        PetID,               name:          str   | None = None,
        animal:        str   | None = None, breed:         str   | None = None, 
        description:   str   | None = None, assistance:    bool  | None = None, 
        location_lat:  float | None = None, location_long: float | None = None,
        condition:     str   | None = None, more:          str   | None = None,
        push_token:    str   | None = None, timestamp:     datetime.datetime | None = None,
        size:          str   | None = None,
        ):
        
        self.pet_id = pet_id
        self.name = name
        self.animal = animal
        self.breed = breed
        self.description = description
        self.assistance = assistance
        self.location_lat = location_lat
        self.location_long = location_long
        self.condition = condition
        self.more = more
        self.sightings = sightings
        self.push_token = push_token
        self.timestamp = timestamp
        self.size = size
    
    @staticmethod
    def from_dict(data, generate_timestamp=False):
        return AlertDocument(
            pet_id=data['pet_id'],
            name=data.get('name'),
            animal=data.get('animal'),
            breed=data.get('breed'),
            description=data.get('description'),
            assistance=data.get('assistance'),
            location_lat=data.get('location_lat'),
            location_long=data.get('location_long'),
            condition=data.get('condition'),
            more=data.get('more'),
            size=data.get('size'),
            sightings=[SightingDocument.from_dict(
                s, generate_timestamp=generate_timestamp) for s in data.get('sightings')],
            push_token=data.get('push_token'),
            timestamp=data.get('timestamp',
                               datetime.datetime.now(tz=datetime.timezone.utc) if generate_timestamp else None),
        )
    
    def to_dict(self, stringify_timestamp=False):
        return {
            'pet_id': self.pet_id,
            'name': self.name,
            'animal': self.animal,
            'breed': self.breed,
            'description': self.description,
            'assistance': self.assistance,
            'location_lat': self.location_lat,
            'location_long': self.location_long,
            'condition': self.condition,
            'more': self.more,
            'sightings': [s.to_dict(stringify_timestamp=stringify_timestamp) for s in self.sightings],
            'push_token': self.push_token,
            'timestamp': str(self.timestamp) if stringify_timestamp else self.timestamp,
            'size': self.size,
        }

# Associated with the 'pets' collection.
class PetImagesDocument:
    def __init__(self, pet_id: str, images: list[CloudFilePath], image_urls: list[ImageURL],
                 embedding: str | None = None):
        self.pet_id = pet_id
        self.images = images
        self.image_urls = image_urls
        self.embedding = embedding
    
    @staticmethod
    def from_dict(data):
        return PetImagesDocument(
            pet_id=data['pet_id'],
            images=data['images'],
            image_urls=data['image_urls'],
            embedding=data.get('embedding')
        )
    
    def to_dict(self):
        return {
            'pet_id': self.pet_id,
            'images': self.images,
            'image_urls': self.image_urls,
            'embedding': self.embedding
        }

# A 'None' is always 'Any' for verification purposes.
class DBInterface:
    PROJECT = "petfinder-424117"
    BUCKET_NAME = "petfinder-424117.appspot.com"
    def __init__(self, project, bucket_name):
        self.client = firestore.Client(project or self.PROJECT)
        self.bucket = storage.Client().get_bucket(bucket_name or self.BUCKET_NAME)
    
    def get_alert(self, pet_id: PetID, create_if_not_present=False) -> AlertDocument | None:
        doc = self.client.collection('alerts').document(pet_id).get()
        if doc.exists:
            return AlertDocument.from_dict(doc.to_dict())
        if create_if_not_present:
            document = AlertDocument(pet_id=pet_id, sightings=[])
            self.client.collection("alerts").document(pet_id).set(document.to_dict())
            return document
        return None

    def get_pet_images(self, pet_id: PetID, create_if_not_present=False) -> PetImagesDocument | None:
        doc = self.client.collection('pets').document(pet_id).get()
        if doc.exists:
            return PetImagesDocument.from_dict(doc.to_dict())
        if create_if_not_present:
            document = PetImagesDocument(pet_id=pet_id, images=[], image_urls=[])
            self.client.collection("pets").document(pet_id).set(document.to_dict())
            return document
        return None
    
    def set_alert(self, document: AlertDocument):
        self.client.collection('alerts').document(document.pet_id).set(document.to_dict())
    
    
    def set_pet_images(self, document: PetImagesDocument):
        self.client.collection('pets').document(document.pet_id).set(document.to_dict())
    
    def publish_image(self, image: CloudFilePath) -> ImageURL:
        blob = self.bucket.blob(image)
        if "READER" not in blob.acl.all().get_roles():
            blob.make_public()
        return blob.public_url
    
    def upload_image(self, base64_image: str) -> CloudFilePath:
        fname = "image_" + str(uuid.uuid4()) + ".jpg"
        blob = self.bucket.blob(fname)
        blob.upload_from_string(base64_image, content_type="image/jpeg")
        return fname
    
    def add_pet_image_base64(self, document: PetImagesDocument, base64_image: str) -> PetImagesDocument:
        image = self.upload_image(base64_image)
        self.add_pet_image(document, image)
        return document
    
    def add_sighting_image_base64(self, document: SightingDocument, base64_image: str) -> SightingDocument:
        image = self.upload_image(base64_image)
        self.add_sighting_image(document, image)
        return document
    
    def add_pet_image(self, document: PetImagesDocument, image: CloudFilePath) -> PetImagesDocument:
        url = self.publish_image(image)
        document.images.append(image)
        document.image_urls.append(url)
        document.embedding = embed_image_from_url(url)
        return document
    
    def add_sighting_image(self, document: SightingDocument, image: CloudFilePath) -> SightingDocument:
        document.image = image
        url = self.publish_image(image)
        document.image_url = url
        document.embedding = embed_image_from_url(url)
        return document
    
    def add_sighting(self, document: AlertDocument, sighting: SightingDocument) -> AlertDocument:
        document.sightings.append(sighting)
        self.client.collection("alerts").document(document.pet_id).set({
            "sightings": firestore.ArrayUnion([sighting.to_dict()])
        }, merge=True)
        return document

    def remove_sighting(self, document: AlertDocument, sighting_index: int) -> AlertDocument:
        document.sightings.pop(sighting_index)
        # self.client.collection("alerts").document(document.pet_id).set({
        #     "sightings": firestore.ArrayRemove([sighting.to_dict()])
        # }, merge=True)
        self.set_alert(document)
        return document
    
    def delete_alert(self, pet_id: PetID):
        self.client.collection('alerts').document(pet_id).delete()
    
    def delete_pet_images(self, pet_id: PetID):
        self.client.collection('pets').document(pet_id).delete()
    
    def list_alerts(self) -> list[AlertDocument]:
        return list([AlertDocument.from_dict(r.to_dict())
                     for r in self.client.collection('alerts').stream()])
    
    def list_pet_images(self) -> list[PetImagesDocument]:
        return list([PetImagesDocument.from_dict(r.to_dict())
                     for r in self.client.collection('pets').stream()])
