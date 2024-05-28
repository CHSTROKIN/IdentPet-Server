from flask import Flask, request, jsonify, make_response
import model

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
    return make_response(jsonify({"id": "dummy-id"}), 200)

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
