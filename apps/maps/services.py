"""Гео-хелперы: расстояние между точками (гаверсинус, км)."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1, lon1, lat2, lon2) -> float:
    """Расстояние по большой окружности — «как далеко от меня»."""
    lat1, lon1, lat2, lon2 = (float(v) for v in (lat1, lon1, lat2, lon2))
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * asin(sqrt(a))


def nearby(qs, lat, lon, radius_km: float = 50):
    """Отфильтровать qs (с полями lat/lon) по радиусу, добавив .distance_km."""
    items = []
    for obj in qs:
        d = distance_km(lat, lon, obj.lat, obj.lon)
        if d <= radius_km:
            obj.distance_km = round(d, 1)
            items.append(obj)
    return sorted(items, key=lambda o: o.distance_km)
