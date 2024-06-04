import base64

from flask import Flask, request, jsonify, make_response, url_for, redirect

from google.cloud import storage    # type: ignore
from google.cloud import firestore

from database import DBInterface, SightingDocument, AlertDocument
from specification import post_specifications_by_endpoint
import specification as s
from matcher import SpoofMatch, SpoofTarget, SpoofMatcher

app = Flask(__name__)
app.config["DEBUG"] = True
app.config["match_state"] = False
app.config["match_function"] = lambda st: st
app.config["bucket_name"] = "petfinder-424117.appspot.com"
app.config["not_found_url"] = "https://storage.googleapis.com/petfinder-424117.appspot.com/No_image_available.svg.png"


db = firestore.Client(project="petfinder-424117")

dbi = DBInterface(project="petfinder-424117", bucket_name="petfinder-424117.appspot.com")
matcher: SpoofMatcher = SpoofMatcher(SpoofMatch.ALWAYS, SpoofTarget.FIRST)

@app.route("/", methods=["GET"])
def index():
    return "Hello, World!"

@app.route("/image", methods=["POST"])
def image():
    data = base64.urlsafe_b64decode(request.json["base64"] + "==")
    fname = dbi.upload_image(data)
    return make_response(jsonify({"id": fname}), 200)

@app.route("/sighting", methods=["POST"])
def sighting():
    data = request.json
    interpreted, warnings = s.sighting_spec.interpret_request(data, strict=True)
    if warnings:
        return s.sighting_spec.response(warnings=warnings)
    
    document = SightingDocument.from_dict(interpreted)
    document = dbi.add_sighting_image(document, data["image"])
    alerts = dbi.list_alerts()
    matched = matcher.match(document, alerts)
    
    for match in matched:
        dbi.add_sighting(match, document)
        dbi.set_alert(match)
    
    return s.sighting_spec.response({
        "matchN": len(matched),
    })

@app.route("/pet/found", methods=["POST"])
def found():
    data = request.json
    interpreted, warnings = s.pet_found_spec.interpret_request(data, strict=True)
    if warnings:
        return s.pet_found_spec.response(warnings=warnings)
    
    dbi.delete_alert(interpreted["id"])
    return s.pet_found_spec.response()

@app.route("/pet/alert", methods=["GET", "POST"])
def alert():
    if request.method == "GET":
        data = request.args.to_dict(flat=True)
        interpreted, warnings = s.pet_alert_spec_get.interpret_request(data, strict=True)
        if warnings:
            return s.pet_alert_spec_get.response(warnings=warnings)
        
        document = dbi.get_alert(interpreted["pet_id"], create_if_not_present=False)
        if document is None:
            return s.pet_alert_spec_get.response(warnings=[f"No alert found matching {interpreted['pet_id']}!"], code=404)
        
        return s.pet_alert_spec_get.response(document.to_dict())
    else:
        data = request.json
        interpreted, warnings = s.pet_alert_spec_post.interpret_request(data, strict=True)
        if warnings:
            return s.pet_alert_spec_post.response(warnings=warnings)
        
        if "sightings" not in interpreted:
            interpreted["sightings"] = []
            
        document = AlertDocument.from_dict(interpreted)
        dbi.set_alert(document)
        return s.pet_alert_spec_post.response()

# DEPRECATED: Will stop existing moving forwards, since local storage has taken on this role.
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
    pet_data = [p.to_dict() for p in dbi.list_alerts()]
    return make_response(jsonify(pet_data), 200)

# DEPRECATED: Will stop existing moving forwards, since local storage has taken on this role.
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

# DEPRECATED: Will stop existing moving forwards, since local storage has taken on this role.
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
    <h2>One-Click Actions</h2>
    <ul>
        <li><a href="/debug/reset">Reset Backend State</a></li>
        <li><a href="/debug/match?mode=always">Images Always Match</a></li>
        <li><a href="/debug/match?mode=never">Images Never Match</a></li>
        <li><a href="/debug/match?mode=random">Images Coin-flip Match</a></li>
        <li><a href="/debug/match?mode=alternate">Images Alternatingly Match</a></li>
        <li><a href="/debug/match?mode=all">Positive Match Propagates to All Alerts</a></li>
        <li><a href="/debug/match?mode=one">Positive Match Propagates to One Alert</a></li>
        <li><a href="/debug/match?mode=first">Positive Match Propagates to the First Alert</a></li>
        <li><a href="/debug/match?mode=random">Positive Match Propagates to Random Alerts</a></li>
    </ul>
    <h2>Request Composer</h2>
    <ul>
        <li><a href="/debug/request/image">POST /image</a></li>
        <li><a href="/debug/request/sighting">POST /sighting</a></li>
        <li><a href="/debug/request/pet/found">POST /pet/found</a></li>
        <li><a href="/debug/request/pet/alert">POST /pet/alert</a></li>
    </ul>
    """

@app.route("/debug/request/<path:endpoint>", methods=["GET"])
def debug_request(endpoint):
    spec = post_specifications_by_endpoint[endpoint]
    fields = list(spec.required_fields.keys()) + list(spec.optional_fields.keys())
    inputs = ["<label for='{}'>{}</label><br/><input type='text' name='{}' id='{}' placeholder='{}' />".format(f, f, f, f, f) for f in fields]
    return f"""
    <a href='/debug'>Back to Debug</a>
    <h1>Send Debug Request to /{endpoint}</h1>
    <p>Fill in the fields below to send a request to the specified endpoint.</p>
    <div>
        {'<br/>'.join(inputs)}<br/>
        <button id='submit'>Send Request</button>
    </div>
    <h2>Result</h2>
    <div id='result'></div>
    <h2>Error</h2>
    <div id='error'></div>
    <h2>Common Values</h2>
    <ul>
        <li>Usable fname: No_image_available.svg.png</li>
        <li>Usable fname: cat01_0.jpg</li>
        <li>Usable base64: iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAM0lEQVR4nGJ5L3WZATcw39yAR5YJjxxBMKp5ZGhmVDx5DY+0zuuLtLJ5VPPI0AwIAAD//05PBxgI43H+AAAAAElFTkSuQmCC</li>
    </ul>
    <script>
        document.getElementById('submit').addEventListener('click', function() {{
            var data = {{
                {', '.join([f + f": document.getElementById('{f}').value" for f in fields])}
            }};
            fetch('/{endpoint}', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify(data)
            }})
            .then(response => response.ok ? response.json() : Promise.reject(JSON.stringify(response)))
            .then(data => {{document.getElementById('result').innerText = JSON.stringify(data, null, 2)}})
            .catch(error => {{document.getElementById('error').innerText = error}});
        }});
    </script>
    """

@app.route("/debug/match", methods=["GET"])
def debug_match():
    if app.config["DEBUG"]:
        mode = request.args.get("mode")
        if mode == "always":
            matcher.match_mode = SpoofMatch.ALWAYS
        elif mode == "never":
            matcher.match_mode = SpoofMatch.NEVER
        elif mode == "random":
            matcher.match_mode = SpoofMatch.HALF
        elif mode == "alternate":
            matcher.match_mode = SpoofMatch.ALTERNATING
        elif mode == "all":
            matcher.target_mode = SpoofTarget.ALL
        elif mode == "one":
            matcher.target_mode = SpoofTarget.ONE
        elif mode == "first":
            matcher.target_mode = SpoofTarget.FIRST
        elif mode == "random":
            matcher.target_mode = SpoofTarget.RANDOM
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
            
        alerts = db.collection("alerts").stream()
        for alert in alerts:
            alert.reference.delete()
            
        return redirect(url_for("debug"))
    return make_response("Not allowed: application not in debug mode.", 403)
