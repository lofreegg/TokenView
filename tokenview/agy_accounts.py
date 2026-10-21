"""Independent Google authorization, isolated from both MyAgents and AGY CLI.

The installed CLIProxy engine handles OAuth/refresh; no OAuth client secret is
copied into this project. Persistent credentials are Windows-user DPAPI blobs.
The engine's temporary auth files live in an owner-only directory and are
removed after the owned process exits. No model inference is requested.
"""
import datetime
import json
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .providers import ProviderError, numeric, snapshot, NoRedirect


def engine_program():
    override = os.environ.get('TOKENVIEW_CLIPROXY')
    if override:
        path = Path(override)
        if not path.is_file():
            raise ProviderError('独立授权引擎路径无效')
        return path
    root = Path.home() / '.myagents' / 'runtimes' / 'cliproxy'
    versions = sorted(root.glob('*'), key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in p.name.split('.')), reverse=True)
    for version in versions:
        candidates = list(version.glob('win32-x64/*/cli-proxy-api.exe'))
        if candidates:
            return candidates[0]
    raise ProviderError('未找到独立 Google 授权引擎，请先安装 MyAgents Antigravity Runtime')


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def login_url(url, callback_port):
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    callback = urllib.parse.urlsplit(query.get('redirect_uri', [''])[0])
    if (parsed.scheme != 'https' or parsed.netloc != 'accounts.google.com'
        or not query.get('state') or callback.scheme != 'http'
        or callback.hostname != 'localhost' or callback.port != callback_port
        or callback.path != '/oauth-callback'):
        raise ProviderError('授权地址校验失败，未打开网页')
    query['prompt'] = ['consent select_account']
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))


def parse_summary(body):
    groups = body.get('groups')
    if not isinstance(groups, list):
        raise ProviderError('Google 未返回分组额度，保留旧数据')
    metrics = {}
    for group in groups:
        name = str(group.get('displayName', '')).casefold()
        category = 'Gemini' if 'gemini' in name else 'Claude/GPT' if ('claude' in name or 'gpt' in name) else None
        if not category:
            continue
        for bucket in group.get('buckets', []):
            description = str(bucket.get('displayName', '')).casefold()
            window = str(bucket.get('window', '')).strip().casefold()
            # Only explicit provider window fields/names qualify. Reset date alone
            # is not evidence of a five-hour or weekly allowance.
            period = '5h' if window in ('5h', '18000s', 'five_hour') or 'five hour' in description else (
                'weekly' if window in ('7d', '168h', '604800s', 'weekly') or 'weekly' in description else None)
            if not period or bucket.get('disabled'):
                continue
            fraction = numeric(bucket.get('remainingFraction'))
            if not 0 <= fraction <= 1 or (category, period) in metrics:
                raise ProviderError('Google 额度格式已变化，未猜测显示')
            raw_reset = bucket.get('resetTime')
            reset = None
            if raw_reset:
                try:
                    stamp = datetime.datetime.fromisoformat(raw_reset.replace('Z', '+00:00'))
                    if stamp.tzinfo is None:
                        raise ValueError()
                    reset = stamp.timestamp()
                except (TypeError, ValueError):
                    raise ProviderError('Google 重置时间格式未识别') from None
            metrics[category, period] = {'label': '5H' if period == '5h' else '周', 'period': period,
                'group': category, 'unit': 'percent', 'value': round(fraction * 100, 4), 'reset': reset}
    if not any(group == 'Gemini' for group, _ in metrics):
        raise ProviderError('Google 未返回明确的 Gemini 5H/周额度')
    return snapshot([metrics[key] for key in [('Gemini', '5h'), ('Gemini', 'weekly'),
        ('Claude/GPT', '5h'), ('Claude/GPT', 'weekly')] if key in metrics], 'Google 额度接口 · 独立账号')


def proxy_url():
    from .integrated import config
    proxy = config().get('proxySettings', {})
    if proxy.get('enabled') and proxy.get('host') and proxy.get('port'):
        protocol = proxy.get('protocol', 'http')
        if protocol in ('http', 'https', 'socks5'):
            return f"{protocol}://{proxy['host']}:{int(proxy['port'])}"
    return ''


def restrict_directory(path):
    # Remove inherited access before any token file is created. Fail closed.
    identity = subprocess.run(['whoami.exe', '/user', '/fo', 'csv', '/nh'], capture_output=True,
                              creationflags=0x08000000, timeout=5)
    sid = re.search(rb'S-1-5-[0-9-]+', identity.stdout)
    if not sid:
        raise ProviderError('无法建立账号私有目录')
    result = subprocess.run(['icacls.exe', str(path), '/inheritance:r', '/grant:r',
        '*' + sid.group().decode() + ':(OI)(CI)F'], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=0x08000000, timeout=5)
    if result.returncode:
        raise ProviderError('账号私有目录权限设置失败')


class Session:
    def __init__(self, provider, account, cancel=None):
        self.provider, self.account = provider, account
        self.cancel = cancel
        self.generation = account.generation
        self.process = None
        self.temp = None

    def __enter__(self):
        self.check_active()
        self.temp = tempfile.TemporaryDirectory(prefix='tokenview-agy-', dir=self.provider.store.root)
        self.root = Path(self.temp.name)
        try:
            restrict_directory(self.root)
            self.auth = self.root / 'auth'
            self.auth.mkdir()
            self.port = free_port()
            self.key = secrets.token_urlsafe(32)
            self.config = self.root / 'config.yaml'
            # Legacy spelling is supported by installed v7 and v8 engines.
            settings = {'host': '127.0.0.1', 'port': self.port, 'auth-dir': str(self.auth),
                'remote-management': {'allow-remote': False, 'secret-key': self.key,
                                      'disable-control-panel': True, 'disable-auto-update-panel': True},
                'api-keys': [secrets.token_urlsafe(32)], 'debug': False,
                'logging-to-file': False, 'request-log': False,
                'usage-statistics-enabled': False, 'proxy-url': proxy_url()}
            # JSON is valid YAML, and avoids path/secret quoting ambiguities.
            self.config.write_text(json.dumps(settings), 'utf-8')
            return self
        except Exception:
            self.temp.cleanup()
            raise

    def start(self, args=(), stdout=subprocess.DEVNULL):
        self.check_active()
        self.process = subprocess.Popen([str(engine_program()), '-config', str(self.config),
            '-local-model', *args], cwd=self.root, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        self.provider.register(self.account.id, self.process)
        return self.process

    def check_active(self):
        current = self.provider.store.accounts.get(self.account.id)
        if (self.provider.closed or (self.cancel is not None and self.cancel.is_set())
            or not current or current.generation != self.generation):
            raise ProviderError('已取消账号操作')

    def request(self, path, body=None):
        self.check_active()
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}/v0/management/{path}',
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=25) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ProviderError('额度响应过大')
        return json.loads(raw)

    def wait_ready(self):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline and self.process.poll() is None:
            try:
                return self.request('auth-files')
            except urllib.error.URLError:
                time.sleep(.1)
        raise ProviderError('独立额度查询服务启动失败')

    def credential(self):
        files = list(self.auth.glob('antigravity-*.json'))
        if len(files) != 1 or files[0].is_symlink():
            raise ProviderError('独立授权未完成，请点击账号重新登录')
        raw = files[0].read_bytes()
        if len(raw) > 65536:
            raise ProviderError('授权文件格式不合法')
        data = json.loads(raw)
        if not all(isinstance(data.get(k), str) and data[k] for k in ('email', 'access_token', 'refresh_token', 'project_id')):
            raise ProviderError('授权未完整返回，请重新登录')
        return data

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(3)
            self.provider.unregister(self.account.id, self.process)
            if self.process.stdout:
                self.process.stdout.close()
            self.process = None

    def __exit__(self, *_):
        try:
            self.stop()
        finally:
            self.temp.cleanup()


def authorize(provider, account, open_url, cancel):
    generation = account.generation
    with Session(provider, account, cancel) as session:
        port = free_port()
        process = session.start(['-antigravity-login', '-no-browser', '-oauth-callback-port', str(port)], stdout=subprocess.PIPE)
        lines = queue.Queue()
        def read():
            for raw in iter(process.stdout.readline, b''):
                if len(raw) <= 16384:
                    lines.put(raw.decode('utf-8', errors='replace'))
            lines.put(None)
        threading.Thread(target=read, daemon=True).start()
        deadline = time.monotonic() + 300
        opened = False
        while time.monotonic() < deadline and not cancel.is_set() and not provider.closed:
            try:
                line = lines.get(timeout=.2)
            except queue.Empty:
                continue
            if line is None:
                break
            urls = re.findall(r'https://accounts\.google\.com/[^\s]+', line)
            if urls and not opened:
                open_url(login_url(urls[0], port))
                opened = True
        if cancel.is_set() or provider.closed:
            raise ProviderError('已取消登录')
        if time.monotonic() >= deadline:
            raise ProviderError('登录超时，点击账号可重试')
        process.wait(timeout=5)
        if process.returncode:
            raise ProviderError('Google 授权失败，请检查网络或账号资格后重试')
        credential = session.credential()
        # Serialize commit with Provider.close; never commit after shutdown.
        with provider.lock:
            session.check_active()
            with provider.store.lock:
                if not provider.store.save_credentials(account.id, generation, credential):
                    raise ProviderError('账号已移除，未保存授权')
                account.name = credential['email']
                provider.store.save()


def fetch(provider, account, cancel=None):
    try:
        credential = provider.store.credentials(account.id)
    except KeyError:
        raise ProviderError('请点击账号完成独立 Google 登录') from None
    generation = account.generation
    with Session(provider, account, cancel) as session:
        (session.auth / 'antigravity-account.json').write_text(json.dumps(credential), 'utf-8')
        session.start()
        try:
            files = session.wait_ready().get('files', [])
            own = [f for f in files if f.get('type', f.get('provider')) == 'antigravity'
                   and str(f.get('email', '')).casefold() == credential['email'].casefold()]
            if len(own) != 1 or not own[0].get('auth_index'):
                raise ProviderError('独立账号身份校验失败，未混用额度')
            request = {'auth_index': own[0]['auth_index'], 'method': 'POST',
                'url': 'https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary',
                'header': {'Authorization': 'Bearer $TOKEN$', 'Content-Type': 'application/json',
                           'User-Agent': 'antigravity/2.22.0 windows/amd64'},
                'data': json.dumps({'project': credential['project_id']})}
            result = session.request('api-call', request)
            if result.get('status_code') in (404, 502, 503):
                request['url'] = 'https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary'
                result = session.request('api-call', request)
            if result.get('status_code') != 200:
                raise ProviderError('Google 额度查询被拒绝，请重新登录或稍后重试')
            return parse_summary(json.loads(result['body']))
        finally:
            session.stop()
            refreshed = session.credential()
            if refreshed['email'].casefold() != credential['email'].casefold():
                raise ProviderError('额度查询账号发生变化，未保存')
            provider.store.save_credentials(account.id, generation, refreshed)
