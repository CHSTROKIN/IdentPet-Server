import numpy as np
import pandas as pd

import torch
import torch.nn as nn
from sklearn.preprocessing import Normalizer

import cv2
import timm

import albumentations as A
from albumentations.pytorch import ToTensorV2

from google.cloud import storage

CONFIG = {
    "img_size": 128,
    "model_name": "tf_efficientnet_b0_ns",
    "embedding_size": 512,
    "device": torch.device("cuda:0" if torch.cuda.is_available() else "cpu"),
    "bucket_name": "petfinder-424117.appspot.com",
}

transform = A.Compose([
        A.Resize(CONFIG['img_size'], CONFIG['img_size']),
        A.Normalize(
                mean=[0.485, 0.456, 0.406], 
                std=[0.229, 0.224, 0.225], 
                max_pixel_value=255.0, 
                p=1.0
            ),
        ToTensorV2()], p=1.)

class Model(nn.Module):
    def __init__(self, model_name, embedding_size):
        super(Model, self).__init__()
        self.model = timm.create_model(model_name, pretrained=True)
        in_features = self.model.classifier.in_features
        self.model.classifier = nn.Identity()
        self.embedding = nn.Linear(in_features, embedding_size)

    def extract(self, images):
        features = self.model(images)
        embedding = self.embedding(features)
        return embedding

def create_model():
    model = Model(CONFIG["model_name"], CONFIG["embedding_size"])
    weights = torch.load("weight.pkt", map_location=torch.device(CONFIG["device"]))
    del weights["fc.weight"]
    model.load_state_dict(weights)
    return model

# https://stackoverflow.com/questions/17170752/python-opencv-load-image-from-byte-string
def fetch_image(image_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(CONFIG["bucket_name"])
    blob = bucket.blob(image_name)
    contents = blob.download_as_bytes()
    
    nparr = np.fromstring(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = transform(image=img)["image"][np.newaxis, :, :, :]
    
    return img

# default_model = create_model()
class DummyModel:
    def embed_image(*args, **kwargs):
        return [0.0] * CONFIG["embedding_size"]
default_model = DummyModel()

@torch.inference_mode()
def embed_image(model, image, device):
    model.eval()
    
    image = image.to(device, dtype=torch.float)
    outputs = model.extract(image)
    embed = outputs.cpu().numpy()
    
    return embed
