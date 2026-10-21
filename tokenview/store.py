import base64
import ctypes
from ctypes import wintypes
import json
import threading
import uuid
from pathlib import Path
from .model import Account, PRODUCTS


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError('Windows 加密存储不可用')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.accounts = {}
        self.selected_product = 'codex'
        self.selected_account = None
        self.settings = {'refresh_seconds': 600, 'capsule_scale': 1.0, 'alerts': True, 'threshold': 15, 'money_threshold': 5, 'startup': False}
        self.encrypted = {}
        self.feed = None
        path = self.root / 'state.json'
        if path.exists():
            state = json.loads(path.read_text('utf-8'))
            self.accounts = {a['id']: Account(**a) for a in state.get('accounts', []) if a.get('product') in PRODUCTS}
            self.settings.update(state.get('settings', {}))
            self.selected_product = state.get('selected_product', 'codex')
            if self.selected_product not in PRODUCTS:
                self.selected_product = 'codex'
            self.selected_account = state.get('selected_account')
            if self.selected_account not in self.accounts:
                self.selected_account = None
            self.encrypted = state.get('encrypted', {})
            self.feed = state.get('feed')

    def save(self):
        with self.lock:
            state = {'accounts': [a.to_dict() for a in self.accounts.values()], 'settings': self.settings,
                     'selected_product': self.selected_product, 'selected_account': self.selected_account,
                     'encrypted': self.encrypted, 'feed': self.feed}
            target = self.root / 'state.json'
            temp = self.root / 'state.tmp'
            temp.write_text(json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')
            temp.replace(target)

    def add_account(self, product, name, key=None):
        if product not in PRODUCTS or not name.strip() or len(name.strip()) > 50:
            raise ValueError('请填写 1–50 字的账号名称')
        if product == 'deepseek' and not (key and key.strip()):
            raise ValueError('请填写 API Key')
        with self.lock:
            account = Account(uuid.uuid4().hex, product, name.strip())
            if key:
                self.encrypted[account.id] = base64.b64encode(protect(key.strip().encode())).decode('ascii')
            self.accounts[account.id] = account
            self.select(product, account.id)
            return account

    def secret(self, account_id):
        with self.lock:
            value = self.encrypted[account_id]
        return protect(base64.b64decode(value), decrypt=True).decode('utf-8')

    def credentials(self, account_id):
        return json.loads(self.secret(account_id))

    def save_credentials(self, account_id, generation, credentials):
        with self.lock:
            account = self.accounts.get(account_id)
            if not account or account.generation != generation or account.connection == 'myagents':
                return False
            raw = json.dumps(credentials, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.encrypted[account_id] = base64.b64encode(protect(raw)).decode('ascii')
            self.save()
            return True

    def remove_account(self, account_id):
        with self.lock:
            self.accounts.pop(account_id, None)
            self.encrypted.pop(account_id, None)
            if self.selected_account == account_id:
                self.selected_account = next((a.id for a in self.accounts.values() if a.product == self.selected_product), None)
            self.save()

    def select(self, product, account_id=None):
        with self.lock:
            if product not in PRODUCTS:
                raise ValueError('未知模型')
            if account_id is not None and (account_id not in self.accounts or self.accounts[account_id].product != product):
                raise ValueError('账号与模型不一致')
            self.selected_product = product
            self.selected_account = account_id or next((a.id for a in self.accounts.values() if a.product == product), None)
            self.save()

    def update_snapshot(self, account_id, generation, snapshot, error=''):
        with self.lock:
            account = self.accounts.get(account_id)
            if not account or account.generation != generation:
                return False
            if snapshot is not None:
                json.dumps(snapshot, allow_nan=False)
                account.snapshot = snapshot
            account.error = error
            self.save()
            return True

    def set_settings(self, **values):
        with self.lock:
            settings = dict(self.settings, **values)
            if not 60 <= int(settings['refresh_seconds']) <= 86400:
                raise ValueError('刷新间隔范围为 1–1440 分钟')
            if not 0.8 <= float(settings['capsule_scale']) <= 1.5:
                raise ValueError('胶囊尺寸范围为 80%–150%')
            if not 1 <= int(settings['threshold']) <= 90:
                raise ValueError('提醒阈值范围为 1%–90%')
            if not 0 <= float(settings['money_threshold']) <= 10000:
                raise ValueError('余额提醒阈值范围为 0–10000')
            self.settings = settings
            self.save()

    def profile(self, account):
        path = self.root / 'profiles' / account.id
        path.mkdir(parents=True, exist_ok=True)
        return path
