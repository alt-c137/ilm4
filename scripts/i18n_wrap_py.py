"""Разметить русские строки Python-кода для перевода (Django i18n).

    .venv/bin/python scripts/i18n_wrap_py.py

Внутри функций:        'Сохранено'            → _('Сохранено')              (gettext — язык запроса)
                       f'Вернули: {n}'        → _('Вернули: {n}').format(n=n)
На уровне модуля/класса ('choices', подписи):   → _lazy('...')                 (gettext_lazy — язык в момент показа)

Не трогает: docstring'и, журнал (log_action, AuditLog, log.*), admin/migrations/tests/management,
verbose_name / help_text / default полей моделей (это админка), строки, уже обёрнутые в _().
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CYR = re.compile(r'[А-Яа-яЁё]')
SKIP_PARTS = {'migrations', 'tests', 'management', '.venv', '__pycache__'}
SKIP_FILES = {'admin.py', 'apps.py', 'geo.py', 'transfer.py', 'audit.py', 'weather.py'}
# переменные-данные (ключевые слова поиска, регулярки): переводить нельзя — сломается поиск
SKIP_ASSIGN = {'NATION_GROUPS', 'CONTACT_PATTERNS', 'COUNTRIES', 'CITIES'}
SKIP_CALLS = {'log_action', 'create', 'info', 'warning', 'error', 'exception', 'debug', 'write', '_', '_lazy',
              'gettext', 'gettext_lazy', 'ngettext', 'print', 'CommandError', 'deconstruct', 'compile', 'search',
              'match', 'sub', 'icontains'}
MSG_CALLS = {'success', 'error', 'info', 'warning'}           # messages.success(request, '...')
SKIP_KW = {'verbose_name', 'verbose_name_plural', 'help_text', 'default', 'action', 'target', 'note',
           'related_name', 'upload_to', 'description'}
FIELD_RE = re.compile(r'(Field|ForeignKey|OneToOneField|ManyToManyField)$')
IMPORT = 'from django.utils.translation import gettext as _\nfrom django.utils.translation import gettext_lazy as _lazy\n'


def call_name(call: ast.Call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', '')


class Finder(ast.NodeVisitor):
    def __init__(self, is_models):
        self.edits = []          # (start, end, replacement)
        self.stack = []          # 'func' / 'class'
        self.is_models = is_models
        self.parents = []

    def generic_visit(self, node):
        self.parents.append(node)
        super().generic_visit(node)
        self.parents.pop()

    def visit_FunctionDef(self, node):
        self._doc(node)
        self.stack.append('func')
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self._doc(node)
        self.stack.append('class')
        self.generic_visit(node)
        self.stack.pop()

    def visit_Module(self, node):
        self._doc(node)
        self.generic_visit(node)

    def _doc(self, node):
        body = getattr(node, 'body', [])
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], 'value', None), ast.Constant):
            body[0].value._doc = True

    def in_func(self):
        return 'func' in self.stack

    def skip_context(self, node):
        parent = self.parents[-1] if self.parents else None
        # keyword=... и позиционные аргументы полей моделей
        for anc in reversed(self.parents):
            if isinstance(anc, ast.keyword) and anc.arg in SKIP_KW:
                return True
            if isinstance(anc, ast.Call):
                name = call_name(anc)
                if name in SKIP_CALLS and name not in MSG_CALLS:
                    return True
                if name in MSG_CALLS and isinstance(anc.func, ast.Attribute) and \
                        getattr(anc.func.value, 'id', '') in ('log', 'logger', 'logging'):
                    return True
                if self.is_models and FIELD_RE.search(name) and parent is anc and anc.args and anc.args[0] is node:
                    return True
                break
        for a in self.parents:
            if isinstance(a, ast.Assign) and any(getattr(t, 'id', '') in SKIP_ASSIGN for t in a.targets):
                return True
        # class Meta: ...
        return any(isinstance(a, ast.ClassDef) and a.name == 'Meta' for a in self.parents)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and CYR.search(node.value) and not getattr(node, '_doc', False) \
                and not self.skip_context(node):
            fn = '_' if self.in_func() else '_lazy'
            self.edits.append((node, f'{fn}({node.value!r})'))

    def visit_JoinedStr(self, node):
        text = ''.join(v.value for v in node.values if isinstance(v, ast.Constant))
        if not CYR.search(text) or self.skip_context(node) or not self.in_func():
            return                           # части f-строки по отдельности не размечаем
        fmt, kwargs = [], []
        for i, v in enumerate(node.values):
            if isinstance(v, ast.Constant):
                fmt.append(v.value.replace('{', '{{').replace('}', '}}'))
            else:
                src = ast.unparse(v.value)
                key = src if re.fullmatch(r'[A-Za-z_]\w*', src) else f'v{i}'
                spec = ''
                if v.format_spec is not None:
                    spec = ':' + ''.join(c.value for c in v.format_spec.values if isinstance(c, ast.Constant))
                conv = {115: '!s', 114: '!r', 97: '!a'}.get(v.conversion, '')
                fmt.append('{' + key + conv + spec + '}')
                if (key, src) not in kwargs:
                    kwargs.append((key, src))
        call = f"_({''.join(fmt)!r}).format(" + ', '.join(f'{k}={s}' for k, s in kwargs) + ')'
        self.edits.append((node, call))


def process(path: Path) -> bool:
    src = path.read_text()
    if not CYR.search(src):
        return False
    tree = ast.parse(src)
    finder = Finder(is_models=path.name == 'models.py')
    finder.visit(tree)
    if not finder.edits:
        return False
    lines = src.splitlines(keepends=True)
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln))

    def pos(line, col):   # col — в байтах UTF-8
        text = lines[line - 1]
        return offs[line - 1] + len(text.encode()[:col].decode(errors='ignore'))
    edits = sorted(((pos(n.lineno, n.col_offset), pos(n.end_lineno, n.end_col_offset), rep)
                    for n, rep in finder.edits), reverse=True)
    out = src
    for start, end, rep in edits:
        out = out[:start] + rep + out[end:]
    if 'gettext as _\n' not in out:
        # импорт — после последнего импорта верхнего уровня
        tree2 = ast.parse(src)
        last = max((n.end_lineno for n in tree2.body if isinstance(n, (ast.Import, ast.ImportFrom))), default=0)
        if last == 0:
            doc_end = tree2.body[0].end_lineno if tree2.body and isinstance(tree2.body[0], ast.Expr) else 0
            last = doc_end
        out_lines = out.splitlines(keepends=True)
        # номер строки после правок не сдвинулся: правки не меняют число строк до импорта
        out = ''.join(out_lines[:last]) + IMPORT + ''.join(out_lines[last:])
    ast.parse(out)   # проверка, что код остался корректным
    path.write_text(out)
    return True


def main(args):
    files = [Path(a) for a in args] or [p for p in (ROOT / 'apps').glob('**/*.py')
                                        if not SKIP_PARTS & set(p.parts) and p.name not in SKIP_FILES]
    changed = [f for f in files if process(f)]
    print(f'Размечено файлов: {len(changed)}')
    for f in changed:
        print('  ', f.relative_to(ROOT))


if __name__ == '__main__':
    main(sys.argv[1:])
