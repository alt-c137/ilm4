# Одноразовый (редизайн v2): убрать старые заголовки секций, задублированные
# section-hero. Запуск из корня проекта.
from pathlib import Path

FILES = [
    "apps/market/templates/market/list.html",
    "apps/maps/templates/maps/map.html",
    "apps/health/templates/health/index.html",
    "apps/news/templates/news/list.html",
    "apps/forum/templates/forum/list.html",
    "apps/jobs/templates/jobs/list.html",
    "apps/migration/templates/migration/list.html",
    "apps/services/templates/services/list.html",
    "apps/library/templates/library/list.html",
    "apps/nikah/templates/nikah/list.html",
    "apps/wallet/templates/wallet/index.html",
    "apps/chat/templates/chat/inbox.html",
]

for rel in FILES:
    path = Path(rel)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [ln for ln in lines
            if 'class="sec__t"' not in ln
            and "<h1>Кошелёк</h1>" not in ln
            and "<h1>Сообщения</h1>" not in ln]
    if len(kept) != len(lines):
        path.write_text("".join(kept), encoding="utf-8")
        print("cleaned:", rel, f"(-{len(lines) - len(kept)} строк)")
    else:
        print("skip:", rel)
print("DONE")
