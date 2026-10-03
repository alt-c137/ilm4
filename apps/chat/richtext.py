"""Оформление текста сообщений, как в Telegram: **жирный**, __курсив__, ~~зачёркнутый~~, `код`, ||скрытый||.

В базе — обычный текст с этими знаками. Сайт и приложение превращают их в оформление при показе.
Скрытый текст («спойлер») не должен попадать в предпросмотр списка чатов и в уведомления — plain() его прячет.
"""
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

_CODE = re.compile(r'`([^`\n]+)`')
_PAIRS = [(re.compile(r'\*\*(?=\S)(.+?)(?<=\S)\*\*', re.DOTALL), '<b>{}</b>'),
          (re.compile(r'__(?=\S)(.+?)(?<=\S)__', re.DOTALL), '<i>{}</i>'),
          (re.compile(r'~~(?=\S)(.+?)(?<=\S)~~', re.DOTALL), '<s>{}</s>'),
          (re.compile(r'\|\|(?=\S)(.+?)(?<=\S)\|\|', re.DOTALL),
           '<span class="spoiler" role="button" tabindex="0">{}</span>')]
_URL = re.compile(r'(?<![\w"=>/])(https?://[^\s<]+[^\s<.,:;!?)\]»"\'])')
_MENTION = re.compile(r'(?<![\w@/.])@([A-Za-z][A-Za-z0-9_]{3,31})(?![\w.])')
_SPOILER = re.compile(r'\|\|(?=\S)(.+?)(?<=\S)\|\|', re.DOTALL)
_MARKS = re.compile(r'\*\*|__|~~|`')


def to_html(text: str):
    """Безопасный HTML: сначала экранируем всё, потом расставляем разрешённые теги."""
    out = escape(text or '')
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f'\x00{len(codes) - 1}\x00'

    out = _CODE.sub(keep, out)                         # внутри `кода` ничего не оформляем
    for rx, tpl in _PAIRS:
        out = rx.sub(lambda m, t=tpl: t.format(m.group(1)), out)
    out = _URL.sub(r'<a href="\1" target="_blank" rel="noopener nofollow ugc">\1</a>', out)
    # @имя — ссылка на человека, группу или канал (как упоминание в Telegram); внутри уже готовых ссылок не трогаем
    out = re.sub(r'(<a [^>]*>.*?</a>)|' + _MENTION.pattern,
                 lambda m: m.group(1) or f'<a class="mention" href="/@{m.group(2).lower()}/">@{m.group(2)}</a>', out)
    out = re.sub(r'\x00(\d+)\x00', lambda m: f'<code>{codes[int(m.group(1))]}</code>', out)
    return mark_safe(out.replace('\n', '<br>'))


def plain(text: str) -> str:
    """Для списка чатов и уведомлений: скрытое — «▒▒▒», знаки оформления убраны."""
    out = _SPOILER.sub(lambda m: '▒' * min(len(m.group(1)), 12), text or '')
    return _MARKS.sub('', out)
