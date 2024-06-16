import vertexai # type: ignore
# from vertexai.vision_models import Image, MultiModalEmbeddingModel # type: ignore
# from google.cloud.firestore_v1.vector import Vector # type: ignore

vertexai.init(project="petfinder-424117")
import base64
# model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
from vertexai.vision_models import Image
# from PIL import Image as PILImage
import math
import torchvision.transforms as transforms
import time 
import cv2 
import numpy as np

import typing
PATH = "Loss1.9962_epoch7.bin"
CONFIG = {"seed": 2022,
          "epochs": 4,
          "img_size": 448,
          "model_name": "efficientnet_b0",
          "num_class": 120,
          "embedding_size": 512,
          "train_batch_size":16,
          "valid_batch_size": 16,
          "learning_rate": 1e-4,
          "scheduler": 'CosineAnnealingLR',
          "min_lr": 1e-6,
          "T_max": 500,
          "weight_decay": 1e-6,
          "n_fold": 5,
          "n_accumulate": 1,
          "device": "cpu",
          # ArcFace Hyperparameters
          "s": 30.0, 
          "m": 0.50,
          "ls_eps": 0.0,
          "easy_margin": False
          }

class GeM(nn.Module):
    def __init__(self, p=3, eps=1e-6):
        super(GeM, self).__init__()
        self.p = nn.Parameter(torch.ones(1)*p)
        self.eps = eps

    def forward(self, x):
        return self.gem(x, p=self.p, eps=self.eps)
        
    def gem(self, x, p=3, eps=1e-6):
        return F.avg_pool2d(x.clamp(min=eps).pow(p), (x.size(-2), x.size(-1))).pow(1./p)
        
    def __repr__(self):
        return self.__class__.__name__ + \
                '(' + 'p=' + '{:.4f}'.format(self.p.data.tolist()[0]) + \
                ', ' + 'eps=' + str(self.eps) + ')'
class ArcMarginProduct(nn.Module):
    r"""Implement of large margin arc distance: :
        Args:
            in_features: size of each input sample
            out_features: size of each output sample
            s: norm of input feature
            m: margin
            cos(theta + m)
        """
    def __init__(self, in_features, out_features, s=30.0, 
                 m=0.50, easy_margin=False, ls_eps=0.0):
        super(ArcMarginProduct, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.s = s
        self.m = m
        self.ls_eps = ls_eps  # label smoothing
        self.weight = nn.Parameter(torch.FloatTensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)

        self.easy_margin = easy_margin
        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)
        self.th = math.cos(math.pi - m)
        self.mm = math.sin(math.pi - m) * m

    def forward(self, input, label):
        # --------------------------- cos(theta) & phi(theta) ---------------------
        cosine = F.linear(F.normalize(input), F.normalize(self.weight))
        sine = torch.sqrt(1.0 - torch.pow(cosine, 2))
        phi = cosine * self.cos_m - sine * self.sin_m
        if self.easy_margin:
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        # --------------------------- convert label to one-hot ---------------------
        # one_hot = torch.zeros(cosine.size(), requires_grad=True, device='cuda')
        one_hot = torch.zeros(cosine.size(), device=CONFIG['device'])
        one_hot.scatter_(1, label.view(-1, 1).long(), 1)
        if self.ls_eps > 0:
            one_hot = (1 - self.ls_eps) * one_hot + self.ls_eps / self.out_features
        # -------------torch.where(out_i = {x_i if condition_i else y_i) ------------
        output = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        output *= self.s

        return output
class DogImageModel(nn.Module):
    def __init__(self, model_name, embedding_size, pretrained=True):
        super(DogImageModel, self).__init__()
        self.model = timm.create_model(model_name, pretrained=pretrained)
        in_features = self.model.classifier.in_features
        self.model.classifier = nn.Identity()
        self.model.global_pool = nn.Identity()
        self.pooling = GeM()
        self.embedding = nn.Linear(in_features, embedding_size)
        self.fc = ArcMarginProduct(embedding_size, 
                                   120,
                                   s=CONFIG["s"], 
                                   m=CONFIG["m"], 
                                   easy_margin=CONFIG["ls_eps"], 
                                   ls_eps=CONFIG["ls_eps"])

    def forward(self, images, labels):
        features = self.model(images)
        pooled_features = self.pooling(features).flatten(1)
        embedding = self.embedding(pooled_features)
        output = self.fc(embedding, labels)
        return output
    
    def extract(self, images):
        features = self.model(images)
        pooled_features = self.pooling(features).flatten(1)
        embedding = self.embedding(pooled_features)
        return embedding
    
def init_model():
    model = DogImageModel(CONFIG['model_name'], CONFIG['embedding_size'])
    model.load_state_dict(torch.load(PATH, map_location=torch.device(CONFIG["device"])))
    model.to(CONFIG['device'])
    model.eval()
    return model
main_model = init_model()
def tensor_to_str(a):
    return a.numpy().tostring()
def embed_image_from_url(url: str):
    image = Image.load_from_file(url)._pil_image
    if(image == None):
        return torch.zeros(1, 512)
    transform = transforms.Compose([
        transforms.Resize((448, 448)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    image = transform(image)
    input_image = torch.tensor(image).to(CONFIG['device'])
    resized_image = input_image.unsqueeze(0)
    embeddings = main_model.extract(resized_image).squeeze(0).to(torch.float32)
    return base64.b64encode(embeddings.detach().numpy().tostring()).decode('utf-8')#（512）
# @torch.inference_mode()
# def test_inference():
#     model = init_model()
#     image = PILImage.open('t1.jpg')
#     transform = transforms.Compose([
#         transforms.Resize((448, 448)),
#         transforms.ToTensor(),
#         transforms.Normalize(
#             mean=[0.485, 0.456, 0.406],
#             std=[0.229, 0.224, 0.225]
#         )
#     ])
#     image = transform(image)
#     input_image = torch.tensor(image).to(CONFIG['device'])
#     resized_image = input_image.unsqueeze(0)
#     embeddings = main_model.extract(resized_image).squeeze(0).to(torch.float32)
#     return base64.b64encode(embeddings.detach().numpy().tostring()).decode('utf-8')#（512）

# #     return base64.b64encode(model.extract(resized_image).squeeze(0).numpy().tostring())
# if __name__ =='__main__':
#     print(test_inference())
#     print('Model is loaded successfully')

# import torch

# Create a tensor
# tensor = torch.tensor([[1.0, 2.0], [3.0, 4.0]])

# Convert tensor to string
# tensor_str = tensor.numpy().tostring()
# print("Tensor to string:", tensor_str)

# import numpy as np

# Convert string back to numpy array
# tensor_back_np = np.fromstring(tensor_str, dtype=np.float32).reshape(2, 2)

#  Convert numpy array back to tensor
# tensor_back = torch.from_numpy(tensor_back_np)
# print("String back to tensor:", tensor_back)
