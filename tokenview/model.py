from dataclasses import dataclass, field, asdict
import time
import uuid

PRODUCTS = {
    'codex': {'name': 'Codex', 'color': '#09A783', 'icon': '✦'},
    'antigravity': {'name': 'Antigravity', 'color': '#5273E8', 'icon': 'A'},
    'deepseek': {'name': 'DeepSeek', 'color': '#238BEC', 'icon': 'D'},
}


@dataclass
class Account:
    id: str
    product: str
    name: str
    generation: str = field(default_factory=lambda: uuid.uuid4().hex)
    snapshot: dict | None = None
    error: str = ''
    created: float = field(default_factory=time.time)
    connection: str = 'independent'

    def to_dict(self):
        return asdict(self)


def reset_text(value, now=None):
    if value is None:
        return '重置时间未返回'
    try:
        seconds = max(0, float(value) - (time.time() if now is None else now))
    except (ValueError, TypeError):
        return '重置时间未返回'
    if seconds < 60:
        return '即将重置'
    minutes = int(seconds // 60)
    if minutes >= 1440:
        return f'{minutes // 1440}天{minutes % 1440 // 60}小时后重置'
    return f'{minutes // 60}小时{minutes % 60}分后重置' if minutes >= 60 else f'{minutes}分钟后重置'


def metric_text(metric):
    if not metric:
        return '—'
    value = metric['value']
    if metric.get('unit') == 'percent':
        return f'{value:g}%'
    symbols = {'CNY': '¥', 'USD': '$'}
    return f"{symbols.get(metric.get('unit'), '')}{value:.2f}"
