import random
from enum import Enum
from typing import Protocol
from database import SightingDocument, AlertDocument
import math 
import torch
import torch.nn as nn
import torch.nn.functional as F
import time 

class SpoofMatch(Enum):
    NEVER = 0
    HALF = 1
    ALTERNATING = 2
    ALWAYS = 3
    AI = 4
class SpoofTarget(Enum):
    FIRST = 0
    ONE = 1
    RANDOM = 2
    ALL = 3
    AI = 4
    
DIMENSION = 512

class MatcherProtocol(Protocol):
    def match(self, sighting: SightingDocument, alerts: list[AlertDocument]) -> list[AlertDocument]:
        ...
        
class SpoofMatcher:
    def __init__(self, match_mode: SpoofMatch, target_mode: SpoofTarget):
        self.match_mode: SpoofMatch = match_mode
        self.target_mode: SpoofTarget = target_mode
        self.alternation_state: bool = True
    
    def match(self, sighting: SightingDocument, alerts: list[AlertDocument]) -> list[AlertDocument]:
        if self.match_mode == SpoofMatch.NEVER:
            return []
        
        if len(alerts) <= 0:
            return []
        
        did_match = (SpoofMatch.ALWAYS == self.match_mode)
        if SpoofMatch.ALTERNATING == self.match_mode:
            did_match = self.alternation_state
            self.alternation_state = not self.alternation_state
        elif SpoofMatch.HALF == self.match_mode:
            did_match = random.random() < 0.5
        
        if not did_match:
            return []
        
        targets = []
        if SpoofTarget.FIRST == self.target_mode:
            targets.append(alerts[0])
        elif SpoofTarget.ONE == self.target_mode:
            targets.append(random.choice(alerts))
        elif SpoofTarget.RANDOM == self.target_mode:
            targets.extend(set(random.choices(alerts, k=random.randint(0, len(alerts)))))
        elif SpoofTarget.ALL == self.target_mode:
            targets.extend(alerts)
        
        return targets

class AIMatcher(SpoofMatcher):
    def __init__(self, nearestK: int = 5, match_mode: SpoofMatch = SpoofMatch.AI, target_mode: SpoofTarget = SpoofTarget.AI):
        super().__init__(match_mode, target_mode)
        self.nearestK = nearestK
        self.match_mode: SpoofMatch = match_mode
        self.target_mode: SpoofTarget = target_mode
        self.cos = nn.CosineSimilarity(dim = 1, eps=1e-6)
        self.disFactor = 0.03
    def distance(self, a: SightingDocument, b:AlertDocument) -> float:
        x = a.to_dict()["location_lat"]
        y = a.to_dict()["location_long"]
        x1 = b.to_dict()["location_lat"]
        y1 = b.to_dict()["location_long"]
        return math.sqrt((x1-x)**2 + (y1-y)**2)
    def vecToTensor(self, vec):
        return torch.tensor(vec._value).unsqueeze(0) #(1, 512)
    def match(self, sighting: SightingDocument, alerts: list[AlertDocument]) -> list[AlertDocument]:
        topK = self.nearestK
        if(len(alerts) <= self.nearestK):
            topK = 1
        if(len(alerts) == 0):
            return []
        similarity_alerts = [(alert, self.cos(self.vecToTensor(alert.to_dict()["embedding"]), self.vecToTensor(sighting.to_dict()["embedding"]))) for alert in alerts]
        similarity_alerts = [(alert, similarity * (self.disFactor)/(self.distance(sighting, alert))) for alert, similarity in similarity_alerts]
        similarity_alerts.sort(key=lambda x: x[1], reverse=True)
        
        return [alert for alert, similarity in similarity_alerts[:topK]]
# if __name__ == '__main__':
#     pass
