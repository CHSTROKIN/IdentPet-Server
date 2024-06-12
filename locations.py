from math import radians, cos, sin, asin, sqrt
from typing import TypeAlias, Any

Point: TypeAlias = tuple[float, float]

# https://stackoverflow.com/questions/4913349/haversine-formula-in-python-bearing-and-distance-between-two-gps-points
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r

def distance(point1: Point, point2: Point) -> float:
    return haversine(point1[0], point1[1], point2[0], point2[1])

def is_within_radius(point1: Point, point2: Point, radius: float) -> bool:
    return distance(point1, point2) <= radius

def points_within_radius(center: Point, points: list[Point], associated_data: list[Any], radius: float) -> list[Point]:
    return [data for point, data in zip(points, associated_data) if is_within_radius(center, point, radius)]
