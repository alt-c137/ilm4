"""Схема Шамира (2-из-3 и т.п.) для резервной копии главного ключа переписки.

Ключ делится на N частей; любые K частей восстанавливают его, а K−1 частей не дают
о ключе никакой информации. Арифметика — в поле GF(2^8) (как AES), каждый байт
ключа — свой многочлен степени K−1 со случайными коэффициентами.

Часть выглядит так: ``ilm4-share-2of3-1-<hex>`` (порог, всего, номер, данные).
Это механизм аварийного восстановления: в работе сервер использует ключ из .env.
"""
import secrets

# таблицы логарифмов в GF(256) с порождающим элементом 3 и многочленом x^8+x^4+x^3+x+1 (как в AES)
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x ^= (_x << 1) ^ (0x11B if _x & 0x80 else 0)   # умножение на 3 = x*2 xor x
    _x &= 0xFF
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError
    if a == 0:
        return 0
    return _EXP[(_LOG[a] - _LOG[b]) % 255]


def split(secret: bytes, threshold: int, shares: int) -> list[str]:
    if not 2 <= threshold <= shares <= 255:
        raise ValueError('нужно 2 ≤ порог ≤ частей ≤ 255')
    coeffs = [[b] + [secrets.randbelow(256) for _ in range(threshold - 1)] for b in secret]
    out = []
    for x in range(1, shares + 1):
        ys = []
        for poly in coeffs:
            y = 0
            for c in reversed(poly):          # схема Горнера
                y = _mul(y, x) ^ c
            ys.append(y)
        out.append(f'ilm4-share-{threshold}of{shares}-{x}-{bytes(ys).hex()}')
    return out


def parse(share: str) -> tuple[int, int, bytes]:
    try:
        _p, _s, kind, x, data = share.strip().split('-', 4)
        threshold = int(kind.split('of')[0])
        return int(x), threshold, bytes.fromhex(data)
    except (ValueError, IndexError) as exc:
        raise ValueError(f'не похоже на часть ключа: {share[:24]}…') from exc


def combine(shares: list[str]) -> bytes:
    parts = [parse(s) for s in shares]
    threshold = parts[0][1]
    xs = [p[0] for p in parts]
    if len(set(xs)) != len(xs):
        raise ValueError('одна и та же часть указана дважды')
    if len(parts) < threshold:
        raise ValueError(f'нужно минимум {threshold} части')
    parts = parts[:threshold]
    length = len(parts[0][2])
    if any(len(p[2]) != length for p in parts):
        raise ValueError('части от разных ключей')
    secret = []
    for i in range(length):
        acc = 0
        for j, (xj, _t, yj) in enumerate(parts):   # интерполяция Лагранжа в точке 0
            num, den = 1, 1
            for m, (xm, _t2, _y) in enumerate(parts):
                if m != j:
                    num = _mul(num, xm)
                    den = _mul(den, xm ^ xj)
            acc ^= _mul(yj[i], _div(num, den))
        secret.append(acc)
    return bytes(secret)
