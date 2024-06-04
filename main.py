from flask import Flask, request, jsonify, make_response, url_for, redirect
import uuid
import base64
import random

from google.cloud import storage
from google.cloud import firestore
# from google.cloud.firestore_v1.vector import Vector

app = Flask(__name__)
app.config["DEBUG"] = True
app.config["match_state"] = False
app.config["match_function"] = lambda st: st
app.config["bucket_name"] = "petfinder-424117.appspot.com"

db = firestore.Client(project="petfinder-424117")

@app.route("/", methods=["GET"])
def index():
    return "Hello, World!"

# Dummy /image endpoint for testing.
@app.route("/image", methods=["POST"])
def image():
    data = base64.urlsafe_b64decode(request.json["base64"] + "==")
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(app.config["bucket_name"])
    
    fname = "image_" + str(uuid.uuid4()) + ".jpg"
    blob = bucket.blob(fname)

    blob.upload_from_string(
        data, content_type="image/jpeg"
    )
    
    return make_response(jsonify({"id": fname}), 200)

@app.route("/sighting", methods=["POST"])
def sighting():
    data = request.json
    (_, ref) = db.collection("sightings").add(data)
    
    match = app.config["match_function"](app.config["match_state"])
    alerts = list(db.collection("alerts").stream())
    if alerts:
        match_with = "" if not match else random.choice().id
    else:
        match = False
    
    ref.set({
        "match": match,
        "match_with": match_with
    }, merge=True)

    return make_response(jsonify({}), 200)

@app.route("/pet/found", methods=["POST"])
def found():
    data = request.json
    id = data["id"]
    db.collection("pets").document(id).set({
        "missing": False
    }, merge=True)
    db.collection("alerts").document(id).delete()
    return make_response(jsonify({}), 200)

@app.route("/pet/alert", methods=["POST"])
def alert():
    data = request.json
    id = data["id"]
    db.collection("alerts").document(id).set(data, merge=True)
    db.collection("pets").document(id).set({
        "missing": True
    }, merge=True)
    return make_response(jsonify({}), 200)

@app.route("/my/pets", methods=["GET"])
def my_pets():
    pets = db.collection("pets").stream()
    pet_data = []
    for pet in pets:
        data = pet.to_dict()
        images = data.get("images", ["No_image_available.svg.png"])
        
        if "name" not in data or "animal" not in data or "breed" not in data or "description" not in data:
            continue
        
        summary_image = images[0]
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(app.config["bucket_name"])
        blob = bucket.blob(summary_image)
        
        if "READER" not in blob.acl.all().get_roles():
            blob.make_public()
        
        if  "assistance" not in data:
            assistance = False
        else:
            assistance = data.get("assistance")

        pet_data.append({
            "id": pet.id,
            "image": blob.public_url,
            "name": data.get("name"),
            "animal": data.get("animal"),
            "breed": data.get("breed"),
            "description": data.get("description"),
            "assistance": assistance,
            "missing": data.get("missing", False)
        })
    
    return make_response(jsonify(pet_data), 200)

# https://stackoverflow.com/questions/46454496/how-to-determine-if-a-google-cloud-storage-blob-is-marked-share-publicly
@app.route("/pet/nearby", methods=["GET"])
def pet():
    pets = db.collection("pets").stream()
    pet_data = []
    for pet in pets:
        data = pet.to_dict()
        images = data.get("images", ["No_image_available.svg.png"])
        
        if "name" not in data or "animal" not in data or "breed" not in data or "description" not in data or "assistance" not in data:
            continue
            
        if "missing" not in data or not data["missing"]:
            continue
        
        summary_image = images[0]
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(app.config["bucket_name"])
        blob = bucket.blob(summary_image)
        
        if "READER" not in blob.acl.all().get_roles():
            blob.make_public()
        
        pet_data.append({
            "id": pet.id,
            "image": blob.public_url,
            "name": data.get("name"),
            "animal": data.get("animal"),
            "breed": data.get("breed"),
            "description": data.get("description"),
            "assistance": data.get("assistance")
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
        db.collection("pets").document(data["id"]).set(data, merge=True)
        return make_response(jsonify({}), 200)

@app.route("/pet/images", methods=["GET", "POST"])
def pet_images():
    if request.method == "GET":
        images = db.collection("pets").document(request.args.get("id")).get().to_dict().get("images", [])
        image_urls = []
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(app.config["bucket_name"])
    
        for fname in images:
            blob = bucket.blob(fname)
            if "READER" not in blob.acl.all().get_roles():
                blob.make_public()
            image_urls.append(blob.public_url)
            
        return make_response(jsonify(image_urls), 200)
    else:
        data = request.json
        
        ref = db.collection("pets").document(data["id"]).get()
        
        if ref.exists:
            db.collection("pets").document(data["id"]).update({
                "images": firestore.ArrayUnion([data["imageID"]])
            })
        else:
            db.collection("pets").document(data["id"]).set({
                "images": [data["imageID"]]
            })
        
        return make_response(jsonify({}), 200)

# Debug routes.
@app.route("/debug", methods=["GET"])
def debug():
    return """
    <h1>Debug</h1>
    <p>Debugging routes for the PetFinder API.</p>
    <ul>
        <li><a href="/debug/reset">Reset Backend State</a></li>
        <li><a href="/debug/match?mode=always">Images Always Match</a></li>
        <li><a href="/debug/match?mode=never">Images Never Match</a></li>
        <li><a href="/debug/match?mode=random">Images Coin-flip Match</a></li>
        <li><a href="/debug/match?mode=alternate">Images Alternatingly Match</a></li>
    </ul>
    """

@app.route("/debug/match", methods=["GET"])
def debug_match():
    if app.config["DEBUG"]:
        mode = request.args.get("mode")
        if mode == "always":
            app.config["match_function"] = lambda st: True
        elif mode == "never":
            app.config["match_function"] = lambda st: False
        elif mode == "random":
            app.config["match_function"] = lambda st: random.choice([True, False])
        elif mode == "alternate":
            app.config["match_state"] = True
            def match_alternate(st):
                app.config["match_state"] = not app.config["match_state"]
                return app.config["match_state"]
            app.config["match_function"] = match_alternate
        else:
            return make_response("Invalid mode.", 400)
        return redirect(url_for("debug"))
    return make_response("Not allowed: application not in debug mode.", 403)

@app.route("/debug/reset", methods=["GET"])
def debug_reset():
    if app.config["DEBUG"]:
        pets = db.collection("pets").stream()
        for pet in pets:
            pet.reference.delete()
            
        sightings = db.collection("sightings").stream()
        for sighting in sightings:
            sighting.reference.delete()
            
        alerts = db.collection("alerts").stream()
        for alert in alerts:
            alert.reference.delete()
            
        return redirect(url_for("debug"))
    return make_response("Not allowed: application not in debug mode.", 403)
