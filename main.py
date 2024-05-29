from flask import Flask, request, jsonify, make_response
import uuid
import base64

from google.cloud import storage
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

import model

app = Flask(__name__)
db = firestore.Client(project="petfinder-424117")

DUMMY_DATA = []

@app.route("/", methods=["GET"])
def index():
    return "Hello, World!"

@app.route("/embed", methods=["GET"])
def embed():
    fname = request.args.get("fname")
    embedding = model.embed_image(
        model.default_model,
        model.fetch_image(fname),
        model.CONFIG["device"]
    )
    return {"embedding": embedding.tolist()}

# Dummy /image endpoint for testing.
@app.route("/image", methods=["POST"])
def image():
    data = base64.urlsafe_b64decode(request.json["base64"] + "==")
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(model.CONFIG["bucket_name"])
    
    fname = "sighting_" + str(uuid.uuid4()) + ".jpg"
    blob = bucket.blob(fname)

    blob.upload_from_string(
        data, content_type="image/jpeg"
    )
    
    return make_response(jsonify({"id": fname}), 200)

@app.route("/sighting", methods=["POST"])
def sighting():
    data = request.json
    
    embedding = model.embed_image(
        model.default_model,
        model.fetch_image(data["imageID"]),
        model.CONFIG["device"]
    )
    data["embedding"] = Vector(embedding.tolist()[0])
    
    db.collection("sightings").add(data)
    
    return make_response(jsonify({}), 200)
