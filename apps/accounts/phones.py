"""Номера телефонов для поиска знакомых.

Сравниваем по последним 9 цифрам: в контактах номера записаны по-разному
(+998 90…, 8 (900)…, 90 123…), а последние 9 цифр совпадают. Браузер
присылает только SHA-256 от этих цифр — открытые номера контактов на сервер
не уходят и не сохраняются.
"""
import hashlib
import re


def digits(raw: str) -> str:
    return re.sub(r'\D', '', raw or '')


def phone_key(raw: str) -> str:
    d = digits(raw)
    if len(d) < 9:
        return ''
    return hashlib.sha256(d[-9:].encode()).hexdigest()
