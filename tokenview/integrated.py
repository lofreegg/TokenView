"""Read-only links to user-authorized MyAgents credentials; never copies tokens."""
import json
from pathlib import Path
import uuid
from .model import Account


def myagents_home():
    return Path.home() / '.myagents'


def config(home=None):
    try:
        return json.loads(((home or myagents_home()) / 'config.json').read_text('utf-8-sig'))
    except (OSError, ValueError):
        return {}


def deepseek_key(home=None):
    value = config(home).get('providerApiKeys', {}).get('deepseek')
    if not isinstance(value, str) or not value.strip():
        raise ValueError('MyAgents 未配置 DeepSeek Key')
    return value.strip()


def antigravity_identity(home=None):
    home = home or myagents_home()
    root = home / 'providers' / 'cliproxy' / 'antigravity-sub'
    try:
        active = json.loads((root / 'account-state.json').read_text('utf-8-sig'))['active']['id']
        # Strictly constrain the account directory derived from local metadata.
        uuid.UUID(active)
        for path in (root / 'accounts' / active / 'auth').glob('antigravity-*.json'):
            return json.loads(path.read_text('utf-8-sig')).get('email', '')
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return ''


def connect_existing(store, home=None):
    home = home or myagents_home()
    data = config(home)
    candidates = []
    if (home / 'codex' / 'auth.json').is_file():
        candidates.append(('codex', data.get('managedCodexAuth', {}).get('accountEmail') or 'MyAgents Codex'))
    if antigravity_identity(home):
        candidates.append(('antigravity', antigravity_identity(home)))
    if isinstance(data.get('providerApiKeys', {}).get('deepseek'), str) and data['providerApiKeys']['deepseek'].strip():
        candidates.append(('deepseek', 'MyAgents DeepSeek'))
    for product, name in candidates:
        existing = next((a for a in store.accounts.values() if a.product == product and a.connection == 'myagents'), None)
        if existing:
            existing.name = name
        else:
            account = Account(uuid.uuid4().hex, product, name, connection='myagents')
            store.accounts[account.id] = account
            if product == store.selected_product and not store.selected_account:
                store.selected_account = account.id
    if candidates:
        store.save()
