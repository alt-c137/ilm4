"""Разметить русский текст шаблонов для перевода (Django i18n).

    .venv/bin/python scripts/i18n_wrap.py            # все шаблоны проекта
    .venv/bin/python scripts/i18n_wrap.py путь.html  # один файл

Что делает (идемпотентно — повторный запуск ничего не портит):
  текст между тегами          Привет            → {% translate "Привет" %}
  атрибуты placeholder/title  title="Закрыть"   → title="{% translate 'Закрыть' %}"
  строки в аргументах тегов   title="Работа"    → title=_("Работа")
  строки в фильтрах           |default:"нет"    → |default:_("нет")
  строки в <script>           'Готово'          → '{{ _("Готово")|escapejs }}'
Не трогает: {% if %}, комментарии, <style>, текст с кавычками обоих видов (пишет в отчёт).
После разметки: scripts/i18n_build.py — собрать каталог и скомпилировать переводы.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CYR = re.compile(r'[А-Яа-яЁё]')
TOKEN = re.compile(r'({%.*?%}|{{.*?}}|{#.*?#}|<!--.*?-->|<[^>]+>)', re.DOTALL)
ATTRS = ('placeholder', 'title', 'aria-label', 'alt', 'content', 'data-confirm', 'label')
skipped = []


def lit(text: str) -> str | None:
    """Строковый литерал для шаблона: предпочитаем двойные кавычки."""
    if '"' not in text:
        return f'"{text}"'
    if "'" not in text:
        return f"'{text}'"
    return None


def wrap_text(seg: str, path) -> str:
    if not CYR.search(seg):
        return seg
    lead = seg[:len(seg) - len(seg.lstrip())]
    trail = seg[len(seg.rstrip()):]
    core = ' '.join(seg.split())
    q = lit(core)
    if q is None:
        skipped.append((path, core))
        return seg
    return f'{lead}{{% translate {q} %}}{trail}'


def wrap_tag_strings(tag: str) -> str:
    """{% include ... with a="Рус" %}, {% tag "Рус" %}, {{ x|default:"Рус" }} → _("Рус")."""
    head = tag[2:].strip().split(' ', 1)[0] if tag.startswith('{%') else ''
    if head in ('translate', 'trans', 'blocktranslate', 'blocktrans', 'if', 'elif', 'comment', 'load', 'url',
                'extends', 'block'):
        return tag

    def repl(m):
        prefix, q, body = m.group(1), m.group(2), m.group(3)
        if not CYR.search(body):
            return m.group(0)
        return f'{prefix}_({q}{body}{q})'
    # строка, перед которой нет «_(», внутри аргументов
    return re.sub(r'([=:\s,])(["\'])((?:(?!\2).)*)\2', repl, tag)


def wrap_attrs(tag: str, path) -> str:
    if tag.startswith(('<script', '<style', '</')):
        return tag

    def repl(m):
        name, q, value = m.group(1), m.group(2), m.group(3)
        if not CYR.search(value):
            return m.group(0)
        if '{' in value:
            # значение с условиями: переводим русские куски между шаблонными тегами
            iq = "'" if q == '"' else '"'
            parts = []
            for piece in re.split(r'({%.*?%}|{{.*?}})', value):
                if piece.startswith('{') or not CYR.search(piece) or iq in piece:
                    if not piece.startswith('{') and CYR.search(piece):
                        skipped.append((path, piece))
                    parts.append(piece)
                    continue
                lead = piece[:len(piece) - len(piece.lstrip())]
                trail = piece[len(piece.rstrip()):]
                parts.append(f"{lead}{{% translate {iq}{' '.join(piece.split())}{iq} %}}{trail}")
            return f'{name}={q}{"".join(parts)}{q}'
        inner = ' '.join(value.split())
        iq = "'" if q == '"' else '"'
        if iq in inner:
            skipped.append((path, inner))
            return m.group(0)
        return f'{name}={q}{{% translate {iq}{inner}{iq} %}}{q}'
    return re.sub(r'\b(' + '|'.join(ATTRS) + r')=(["\'])(.*?)\2', repl, tag)


def wrap_script(js: str, path) -> str:
    def repl(m):
        q, body = m.group(1), m.group(2)
        if not CYR.search(body) or '{' in body or '\\' in body:
            return m.group(0)
        inner_q = "'" if q == '"' else '"'
        if inner_q in body:
            skipped.append((path, body))
            return m.group(0)
        return f'{q}{{{{ _({inner_q}{body}{inner_q})|escapejs }}}}{q}'
    return re.sub(r"(['\"])((?:(?!\1)[^\n])*?)\1", repl, js)


def process(path: Path) -> bool:
    src = path.read_text()
    if not CYR.search(src):
        return False
    out, in_script, in_style = [], False, False
    for part in TOKEN.split(src):
        if not part:
            continue
        low = part.lower()
        if part.startswith('{%'):
            out.append(wrap_tag_strings(part))
        elif part.startswith('{{'):
            out.append(wrap_tag_strings(part) if '|' in part else part)
        elif part.startswith(('{#', '<!--')):
            out.append(part)
        elif part.startswith('<'):
            if low.startswith('<script') and 'application/json' not in low:
                in_script = True
            elif low.startswith('</script'):
                in_script = False
            elif low.startswith('<style'):
                in_style = True
            elif low.startswith('</style'):
                in_style = False
            out.append(wrap_attrs(part, path))
        elif in_style:
            out.append(part)
        elif in_script:
            out.append(wrap_script(part, path))
        else:
            out.append(wrap_text(part, path))
    new = ''.join(out)
    if new == src:
        return False
    if not re.search(r'{%\s*load\s+[^%]*\bi18n\b', new):
        m = re.match(r'(\s*{% extends [^%]+%}\n?)', new)
        if m:
            new = new[:m.end()] + '{% load i18n %}\n' + new[m.end():]
        else:
            new = '{% load i18n %}' + new
    path.write_text(new)
    return True


def main(args):
    files = [Path(a) for a in args] or [p for p in ROOT.glob('**/templates/**/*.html')
                                        if '.venv' not in p.parts and 'admin' not in p.parts]
    changed = sum(process(f) for f in files)
    print(f'Размечено файлов: {changed} из {len(files)}')
    for path, text in skipped:
        print(f'  пропущено (вручную): {path.relative_to(ROOT) if path.is_absolute() else path}: {text[:70]}')


if __name__ == '__main__':
    main(sys.argv[1:])
