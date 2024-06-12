import random
from enum import Enum
from typing import Protocol
from database import SightingDocument, AlertDocument

class SpoofMatch(Enum):
    NEVER = 0
    HALF = 1
    ALTERNATING = 2
    ALWAYS = 3

class SpoofTarget(Enum):
    FIRST = 0
    ONE = 1
    RANDOM = 2
    ALL = 3

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
