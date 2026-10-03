"""Поиск по подстроке без учёта регистра — и для кириллицы на SQLite.

PostgreSQL сравнивает без регистра любые буквы. SQLite (локальная разработка) — только латиницу: «минор» не находит
«Минор». Поэтому на SQLite ищем сразу несколько написаний: как ввели, строчными, с заглавной, Каждое Слово, ПРОПИСНЫМИ.
"""
from django.db import connection
from django.db.models import Q


def icontains(field: str, q: str) -> Q:
    if connection.vendor != 'sqlite':
        return Q(**{f'{field}__icontains': q})
    out = Q()
    for variant in {q, q.lower(), q.capitalize(), q.title(), q.upper()}:
        out |= Q(**{f'{field}__contains': variant})
    return out
