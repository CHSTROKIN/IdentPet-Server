import base64
import datetime

from flask import Flask, request, jsonify, make_response, url_for, redirect, render_template

from google.cloud import storage    # type: ignore
from google.cloud import firestore
from stream_chat import StreamChat

from database import DBInterface, SightingDocument, AlertDocument
from specification import post_specifications_by_endpoint
import specification as s
from matcher import SpoofMatch, SpoofTarget, SpoofMatcher, AIMatcher
from notification import send_push_message

from locations import points_within_radius

app = Flask(__name__)
app.config["DEBUG"] = True
app.config["match_state"] = False
app.config["match_function"] = lambda st: st
app.config["bucket_name"] = "petfinder-424117.appspot.com"
app.config["not_found_url"] = "https://storage.googleapis.com/petfinder-424117.appspot.com/No_image_available.svg.png"

db = firestore.Client(project="petfinder-424117")

dbi = DBInterface(project="petfinder-424117", bucket_name="petfinder-424117.appspot.com")
matcher: SpoofMatcher = SpoofMatcher(SpoofMatch.ALWAYS, SpoofTarget.ALL)
# matcher: SpoofMatcher = AIMatcher(5, SpoofMatch.ALWAYS, SpoofTarget.ALL)
server_client = StreamChat(api_key="cecspa2wrfyy", api_secret="r4fq35udvu87ekgawu6t3mhx92pdq5sas24npgujxj9hp3gwzah49x5gc86bqqkx")

logs: list[tuple[str, str, str, str]] = []
def log(endpoint, method, messages):
    for message in messages:
        logs.append((str(datetime.datetime.now(tz=datetime.UTC)), endpoint, method, message))

s.Specification.log_func = log
@app.route("/", methods=["GET"])
def index():
    return "Hello, World!"

@app.route("/image", methods=["POST"])
def image():
    data = base64.urlsafe_b64decode(request.json["base64"] + "==")
    fname = dbi.upload_image(data)
    return make_response(jsonify({"id": fname}), 200)

@app.route("/channel/<channel_id>", methods=["DELETE"])
def channel(channel_id):
    server_client.delete_channels([channel_id])
    return make_response(jsonify({}), 200)

@app.route("/sighting", methods=["POST"])
def sighting():
    data = request.json
    # log("sighting", "POST",["Sighting begin"])
    interpreted, warnings = s.sighting_spec.interpret_request(data, strict=True)
    if warnings:
        # log("sighting","POST", ["Warnings found in request"])
        return s.sighting_spec.response(warnings=warnings)
    
    document = SightingDocument.from_dict(interpreted, generate_timestamp=True)

    # log("sighting","POST", [f"document is {document.to_dict()}"])
        
    document = dbi.add_sighting_image(document, data["image"])
    # log("sighting", "POST", ["sighting image added"])
    alerts = dbi.list_alerts()
    # log("sighting","POST", [f"alerts are {alerts}"])
    
    matched = matcher.match(document, alerts, log=log)
    
    pet_ids = set([m.pet_id for m in matched])
    # log("sighting","POST", [f"matched are {matched}"])
    # log("sighting", "POST",[f"pet_ids are {pet_ids}"])
    if "pet_id" in interpreted and interpreted["pet_id"] not in pet_ids:
        match = dbi.get_alert(interpreted["pet_id"], create_if_not_present=False)
        if match is not None:
            matched.append(match)
    # log("sighting","POST", [f"matched are {matched}"])
    for match in matched:
        dbi.add_sighting(match, document)
        # log("sighting","POST", [f"match is {match}"])
        # log("sighting","POST", [f"match.push_token is {match.push_token}"])
        if match.push_token is not None:
            send_push_message(match.push_token, "Sighting Alert",
                              f"Your pet {match.name} may have been sighted! Check the app for more details.",
                              {"pet_id": match.pet_id})
    
    
    # log("sighting","POST", [f"matched are2 {matched}"])
    # log("sighting","POST", [f"matchedN is {len(matched)}"])
    return s.sighting_spec.response({
        "matchN": len(matched),
    })
    
def valid_token(token: str):
    if token is None:
        return False
    return token.startswith("ExponentPushToken[") and token.endswith("]")

@app.route("/pet/unsight", methods=["POST"])
def unsight():
    data = request.json
    interpreted, warnings = s.pet_unsight_spec.interpret_request(data, strict=True)
    if warnings:
        return s.pet_unsight_spec.response(warnings=warnings)
    
    alert = dbi.get_alert(interpreted["id"], create_if_not_present=False)
    dbi.remove_sighting(alert, int(interpreted["sighting_index"]))
    return s.pet_unsight_spec.response()

@app.route("/pet/found", methods=["POST"])
def found():
    data = request.json
    # log("pet/found", "POST", [f"Data is {data}"])
    
    interpreted, warnings = s.pet_found_spec.interpret_request(data, strict=True)
    # log("pet/found", "POST", [f"interpreted is {interpreted}"])
    # log("pet/found", "POST", [f"warnings are {warnings}"])
    if warnings:
        return s.pet_found_spec.response(warnings=warnings)
    
    alert = dbi.get_alert(interpreted["id"], create_if_not_present=False)
    invalid_token_warnings = []
    # log("pet/found", "POST", [f"alert is {alert}"])
    
    push_tokens = [s.push_token for s in alert.sightings if valid_token(s.push_token)]
    push_tokens = list(set(push_tokens))
    # log("pet/found", "POST", [f"push_tokens are {push_tokens}"])
    for token in push_tokens:
        try:
            send_push_message(token,
                        "Thank you!",
                        "You have helped someone reunite with their lost pet. Thank you for your help!",
                        {"pet_id": interpreted["id"]})
        except ValueError:
            invalid_token_warnings.append(f"Invalid token: {token}")    
    dbi.delete_alert(interpreted["id"])
    return s.pet_found_spec.response(warnings=invalid_token_warnings)

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
        
        return s.pet_alert_spec_get.response(document.to_dict(stringify_timestamp=True))
    else:
        data = request.json
        interpreted, warnings = s.pet_alert_spec_post.interpret_request(data, strict=True)
        if warnings:
            return s.pet_alert_spec_post.response(warnings=warnings)
        
        if "sightings" not in interpreted:
            interpreted["sightings"] = []
        
        document = AlertDocument.from_dict(interpreted, generate_timestamp=True)
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
    data = request.args.to_dict(flat=True)
    interpreted, warnings = s.pet_nearby_spec_get.interpret_request(data, strict=True)
    if warnings:
        return s.pet_nearby_spec_get.response(warnings=warnings)
    
    pet_data = [p.to_dict() for p in dbi.list_alerts()]
    
    points = [(p["location_lat"], p["location_long"]) for p in pet_data]
    radius = interpreted.get("radius", 30.)
    center = (interpreted["location_lat"], interpreted["location_long"])
    
    pet_data = points_within_radius(center, points, pet_data, radius)
    
    for data in pet_data:
        urls = dbi.get_pet_images(data["pet_id"], create_if_not_present=True).image_urls
        if len(urls) == 0:
            data["image"] = app.config["not_found_url"]
        else:
            data["image"] = urls[0]
            
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

@app.route("/pet/images", methods=["GET", "POST"])
def pet_images():
    if request.method == "GET":
        image_doc = db.collection("pets").document(request.args.get("id"))
        if not image_doc.get().to_dict():
            return make_response(jsonify([]), 200)
        
        images = image_doc.get().to_dict().get("images", [])
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
        pet_images = dbi.get_pet_images(data["id"], create_if_not_present=True)
        pet_images = dbi.add_pet_image(pet_images, data["imageID"])
        dbi.set_pet_images(pet_images)
        return make_response(jsonify({}), 200)

# Debug routes.
@app.route("/debug", methods=["GET"])
def debug():
    return render_template("debug.html.j2",
                           matcher=matcher.__class__.__name__,
                           mode=matcher.match_mode.name,
                           target=matcher.target_mode.name)

@app.route("/debug/logs", methods=["GET"])
def debug_logs():
    return render_template("log.html.j2", logs=logs)

@app.route("/debug/warning", methods=["GET"])
def debug_warning():
    return s.pet_alert_spec_get.response(warnings=["This is a warning."])

@app.route("/debug/request/<path:endpoint>", methods=["GET"])
def debug_request(endpoint):
    spec = post_specifications_by_endpoint[endpoint]
    fields = list(spec.required_fields.keys()) + list(spec.optional_fields.keys())
    return render_template("composer.html.j2", endpoint=endpoint, fields=fields)

@app.route("/debug/doc/<path:endpoint>", methods=["GET"])
def debug_doc(endpoint):
    if endpoint in post_specifications_by_endpoint:
        spec = post_specifications_by_endpoint[endpoint]
    elif endpoint in s.get_specifications_by_endpoint:
        spec = s.get_specifications_by_endpoint[endpoint]
    else:
        return make_response("No specification found for endpoint.", 404)
    required_fields = list(spec.required_fields.keys())
    optional_fields = list(spec.optional_fields.keys())
    renamed_fields = [(k, v) for k, v in spec.database_map.items()]
    return render_template("specification.html.j2",
                           endpoint="/" + endpoint,
                           required_fields=required_fields,
                           optional_fields=optional_fields,
                           renamed_fields=renamed_fields)

@app.route("/debug/match", methods=["GET"])
def debug_match():
    global matcher
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
        elif mode == "reset":
            matcher = SpoofMatcher(SpoofMatch.ALWAYS, SpoofTarget.ALL)
        elif mode == "ai":
            matcher = AIMatcher()
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
