from flask import Flask, request, jsonify, make_response
import model
from google.cloud import storage
import uuid
import base64

app = Flask(__name__)

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

# Dummy /sighting endpoint for testing.
@app.route("/sighting", methods=["POST"])
def sighting():
    data = request.json
    DUMMY_DATA.append(data)
    return make_response(jsonify({}), 200)

# Dummy /debug/sighting route for debugging.
@app.route("/debug/sighting", methods=["GET"])
def sighting_debug():
    return str(DUMMY_DATA)
