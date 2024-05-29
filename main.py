from flask import Flask, request, jsonify, make_response
import uuid
import base64

from google.cloud import storage
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

import model

app = Flask(__name__)
db = firestore.Client(project="petfinder-424117")

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
    
    fname = "image_" + str(uuid.uuid4()) + ".jpg"
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

@app.route("/pet/nearby", methods=["GET"])
def pet():
    pets = db.collection("pets").stream()
    pet_data = []
    for pet in pets:
        images = pet.get("images")
        summary_image = images[0]
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(model.CONFIG["bucket_name"])
        blob = bucket.blob(summary_image)
        blob.make_public()
        
        pet_data.append({
            "id": pet.id,
            "image": blob.public_url 
        })
    
    return make_response(jsonify(pet_data), 200)

@app.route("/pet/data", methods=["GET", "POST"])
def pet_id():
    if request.method == "GET":
        id = request.args.get("id")
        doc_ref = db.collection("pets").document(id)
        if not doc_ref.get().exists:
            return make_response(jsonify({}), 404)
        return make_response(jsonify(doc_ref.get().to_dict()), 200)
    else:
        data = request.json
        if data["mode"] == "add":
            data["id"] = str(uuid.uuid4())
        db.collection("pets").document(data["id"]).set(data, merge=True)
        return make_response(jsonify({
            "petID": data["id"]
        }), 200)

@app.route("/pet/images", methods=["GET", "POST"])
def pet_images():
    if request.method == "GET":
        images = db.collection("pets").document(request.args.get("id")).get().to_dict()["images"]
        image_urls = []
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(model.CONFIG["bucket_name"])
    
        for fname in images:
            blob = bucket.blob(fname)
            blob.make_public()
            image_urls.append(blob.public_url)
            
        return make_response(jsonify(image_urls), 200)
    else:
        data = request.json
        if data["mode"] == "add":
            data["id"] = str(uuid.uuid4())
        
        ref = db.collection("pets").document(data["id"]).get()
        
        if ref.exists:
            db.collection("pets").document(data["id"]).update({
                "images": firestore.ArrayUnion([data["imageID"]])
            })
        else:
            db.collection("pets").document(data["id"]).set({
                "images": [data["imageID"]]
            })
        
        return make_response(jsonify({
            "petID": data["id"]
        }), 200)
