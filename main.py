from flask import Flask, request
import model

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello, World!"

@app.route("/embed")
def embed():
    fname = request.args.get("fname")
    embedding = model.embed_image(
        model.default_model,
        model.fetch_image(fname),
        model.CONFIG["device"]
    )
    return {"embedding": embedding.tolist()}
