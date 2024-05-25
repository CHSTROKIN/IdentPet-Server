import numpy as np
import pandas as pd

import torch
import torch.nn as nn
from sklearn.preprocessing import Normalizer

import cv2
import timm
import faiss

import albumentations as A
from albumentations.pytorch import ToTensorV2

CONFIG = {
    "img_size": 128,
    "model_name": "tf_efficientnet_b0_ns",
    "embedding_size": 512,
    "device": torch.device("cuda:0" if torch.cuda.is_available() else "cpu"),
}

class Model(nn.Module):
    def __init__(self, model_name, embedding_size):
        super(Model, self).__init__()
        self.model = timm.create_model(model_name, pretrained=True)
        self.model.classifier = nn.Identity()
        in_features = self.model.classifier.in_features
        self.embedding = nn.Linear(in_features, embedding_size)

    def extract(self, images):
        features = self.model(images)
        embedding = self.embedding(features)
        return embedding
