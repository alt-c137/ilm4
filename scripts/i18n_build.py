"""Собрать переводы интерфейса.

    .venv/bin/python scripts/i18n_build.py            # извлечь фразы → проверить → скомпилировать .mo
    .venv/bin/python scripts/i18n_build.py --missing  # показать, чего не хватает (для переводчика)

Источник переводов — locale/<язык>.json: {"русская фраза": "перевод"}. Их правят люди (или ИИ),
этот скрипт делает из них стандартные файлы Django locale/<язык>/LC_MESSAGES/django.po и .mo.
Фразы — всё, что размечено {% translate %}, _("…") в шаблонах и _() / _lazy() в Python.
Нет перевода → на сайте останется русский текст (ничего не ломается).
"""
import ast
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALE = ROOT / 'locale'
LANGS = ['uz', 'en']
T_TRANS = re.compile(r"""{%\s*translate\s+(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""")
T_UNDER = re.compile(r"""_\((?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\)""")
T_BLOCK = re.compile(r'{%\s*blocktranslate[^%]*%}(.*?){%\s*endblocktranslate\s*%}', re.DOTALL)
PY_FUNCS = {'_', '_lazy', 'gettext', 'gettext_lazy'}


def extract() -> dict:
    """{msgid: [места]} по всему проекту."""
    found = {}

    def add(msg, where):
        if msg:
            found.setdefault(msg, []).append(where)
    for p in ROOT.glob('**/templates/**/*'):
        if '.venv' in p.parts or not p.is_file() or p.suffix not in ('.html', '.txt'):
            continue
        text = p.read_text()
        rel = str(p.relative_to(ROOT))
        for rx in (T_TRANS, T_UNDER):
            for m in rx.finditer(text):
                add(m.group(1) if m.group(1) is not None else m.group(2), rel)
        for m in T_BLOCK.finditer(text):
            add(re.sub(r'{{\s*(\w+)\s*}}', r'%(\1)s', m.group(1)), rel)
    for p in (ROOT / 'static' / 'js').glob('*.js'):          # _t('…') в JavaScript
        for m in re.finditer(r"_t\('((?:[^'\\]|\\.)*)'\)", p.read_text()):
            add(m.group(1), str(p.relative_to(ROOT)))
    for p in (ROOT / 'apps').glob('**/*.py'):
        if {'migrations', 'tests', '__pycache__'} & set(p.parts):
            continue
        rel = str(p.relative_to(ROOT))
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in PY_FUNCS and node.args \
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                add(node.args[0].value, rel)
    return found


def load(lang) -> dict:
    path = LOCALE / f'{lang}.json'
    return json.loads(path.read_text()) if path.exists() else {}


def build():
    from babel.messages.catalog import Catalog
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import write_po

    msgs = extract()
    report = []
    for lang in LANGS:
        tr = load(lang)
        cat = Catalog(locale=lang, project='ilm4', charset='utf-8')
        done = 0
        for msgid in sorted(msgs):
            value = tr.get(msgid, '')
            cat.add(msgid, value, locations=[(w, 0) for w in sorted(set(msgs[msgid]))[:3]])
            done += bool(value)
        out = LOCALE / lang / 'LC_MESSAGES'
        out.mkdir(parents=True, exist_ok=True)
        with open(out / 'django.po', 'wb') as f:
            write_po(f, cat, width=0, omit_header=False)
        buf = io.BytesIO()
        write_mo(buf, cat)
        (out / 'django.mo').write_bytes(buf.getvalue())
        report.append(f'{lang}: переведено {done} из {len(msgs)}')
    print('\n'.join(report))


def missing(lang):
    msgs, tr = extract(), load(lang)
    need = {m: '' for m in sorted(msgs) if not tr.get(m)}
    print(json.dumps(need, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    if '--missing' in sys.argv:
        missing(sys.argv[-1] if sys.argv[-1] in LANGS else 'en')
    elif '--count' in sys.argv:
        print(len(extract()))
    else:
        build()
