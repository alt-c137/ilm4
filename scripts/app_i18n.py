"""Переводы мобильного приложения: какие фразы t('…') ещё без перевода.

    python3 scripts/app_i18n.py            — список непереведённых (en, uz)

Переводы лежат в mobile/src/lib/locales/en.ts и uz.ts (ключ — русский текст).
Фразы, переведённые на сайте (locale/*.json), можно копировать оттуда.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAT = re.compile(r"""\bt\(\s*(['"])((?:\\.|(?!\1).)*)\1""")


def app_msgids() -> set:
    out = set()
    for f in (ROOT / 'mobile' / 'src').rglob('*.ts*'):
        if 'locales' in f.parts:
            continue
        for m in PAT.finditer(f.read_text()):
            out.add(m.group(2).replace("\\'", "'"))
    return out


ENTRY = re.compile(r'^\s+("(?:[^"\\]|\\.)*"): ("(?:[^"\\]|\\.)*"),?$', re.MULTILINE)


def load(lang: str) -> dict:
    text = (ROOT / 'mobile' / 'src' / 'lib' / 'locales' / f'{lang}.ts').read_text()
    return {json.loads(k): json.loads(v) for k, v in ENTRY.findall(text)}


if __name__ == '__main__':
    ids = app_msgids()
    for lang in ('en', 'uz'):
        have = load(lang)
        missing = sorted(i for i in ids if i not in have)
        print(f'{lang}: {len(ids) - len(missing)}/{len(ids)} переведено')
        for m in missing:
            print('   ', m)
