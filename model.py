import vertexai # type: ignore
from vertexai.vision_models import Image, MultiModalEmbeddingModel # type: ignore
from google.cloud.firestore_v1.vector import Vector # type: ignore

from database import DBInterface, CloudFilePath, ImageURL

vertexai.init(project="petfinder-424117")
model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")

def embed_image_from_url(url: ImageURL) -> Vector:
    image = Image.load_from_file(url)
    embeddings = model.get_embeddings(image=image, dimension=512)
    return Vector(embeddings.image_embedding)

def embed_image_from_fname(dbi: DBInterface, fname: CloudFilePath) -> Vector:
    return embed_image_from_url(dbi.publish_image(fname))
