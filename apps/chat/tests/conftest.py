"""Async-тесты (Channels) оставляют соединения БД в закрытом event-loop —
закрываем их после каждого теста, иначе следующие тесты падают с InterfaceError."""
import pytest
from django.db import connections


@pytest.fixture(autouse=True)
def close_db_after_async():
    yield
    for conn in connections.all():
        conn.close()
