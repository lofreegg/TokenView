import datetime
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import threading
import re
import tempfile
import urllib.request
import urllib.error
from .rpc import CodexRpc, RpcError


class ProviderError(Exception):
    """Messages are deliberately safe for display and logs."""


def numeric(value, percent=False):
    if value is None or isinstance(value, bool):
        raise ProviderError('额度响应缺少有效数值')
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ProviderError('额度响应格式已变化') from None
    if not math.isfinite(number) or (percent and not 0 <= number <= 100):
        raise ProviderError('额度响应数值不合法')
    return number


def snapshot(metrics, source):
    return {'metrics': metrics, 'source': source, 'at': time.time()}


def parse_codex(result):
    bucket = (result.get('rateLimitsByLimitId') or {}).get('codex') or result.get('rateLimits')
    if not isinstance(bucket, dict):
        raise ProviderError('官方未返回可展示额度')
    metrics = {}
    for name in ('primary', 'secondary'):
        window = bucket.get(name)
        if not isinstance(window, dict):
            continue
        duration = window.get('windowDurationMins')
        spec = {300: ('5H', '5h'), 10080: ('周', 'weekly')}.get(duration)
        if not spec:
            continue
        label, period = spec
        if period in metrics:
            raise ProviderError('官方返回了重复额度窗口')
        used = numeric(window.get('usedPercent'), percent=True)
        reset = window.get('resetsAt')
        if reset is not None:
            reset = numeric(reset)
            if reset <= 0:
                reset = None
        metrics[period] = {'label': label, 'period': period, 'unit': 'percent', 'value': round(100 - used, 4), 'reset': reset}
    if not metrics:
        raise ProviderError('官方未返回 5H 或周额度')
    result_snapshot = snapshot([metrics[k] for k in ('5h', 'weekly') if k in metrics], 'OpenAI Codex App Server')
    if result.get('ordinaryUsageAllowed') is False:
        result_snapshot['notice'] = '官方暂不允许普通额度使用'
    return result_snapshot


def parse_agy(body):
    if body.get('status') != 'SUCCESS' or not isinstance(body.get('response'), str):
        raise ProviderError('AGY 当前账号无法查询，请在 AGY 完成登录')
    found = {}
    specs = {
        ('Gemini Models', 'Five Hour Limit Remaining'): ('Gemini', '5H', '5h'),
        ('Gemini Models', 'Weekly Limit Remaining'): ('Gemini', '周', 'weekly'),
        ('Claude and GPT models', 'Five Hour Limit Remaining'): ('Claude/GPT', '5H', '5h'),
        ('Claude and GPT models', 'Weekly Limit Remaining'): ('Claude/GPT', '周', 'weekly'),
    }
    for line in body['response'].splitlines():
        parts = [p.strip() for p in line.split('\t')]
        if len(parts) != 4 or (parts[0], parts[1]) not in specs:
            continue
        spec = specs[(parts[0], parts[1])]
        if not parts[2].endswith('%') or spec in found:
            raise ProviderError('AGY 额度响应格式已变化')
        value = numeric(parts[2][:-1], percent=True)
        try:
            stamp = datetime.datetime.fromisoformat(parts[3].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError()
            reset = stamp.timestamp()
        except ValueError:
            raise ProviderError('AGY 重置时间未被识别') from None
        found[spec] = {'label': spec[1], 'period': spec[2], 'group': spec[0], 'unit': 'percent', 'value': value, 'reset': reset}
    ordered = [found[spec] for spec in specs.values() if spec in found]
    if not ordered or not any(m['group'] == 'Gemini' for m in ordered):
        raise ProviderError('AGY 未返回 Gemini 额度')
    return snapshot(ordered, 'AGY CLI /usage')


def parse_deepseek(body):
    balances = body.get('balance_infos')
    if not isinstance(balances, list) or not balances:
        raise ProviderError('官方余额响应格式已变化')
    balance = next((b for b in balances if b.get('currency') == 'CNY'), balances[0])
    currency = balance.get('currency')
    if currency not in ('CNY', 'USD'):
        raise ProviderError('官方余额币种未被识别')
    total = numeric(balance.get('total_balance'))
    granted = numeric(balance.get('granted_balance'))
    return snapshot([{'label': '余额', 'value': total, 'unit': currency},
                     {'label': '赠送', 'value': granted, 'unit': currency}], 'DeepSeek 官方余额 API')


def profile_env(product, profile):
    env = dict(os.environ)
    if product == 'codex':
        env['CODEX_HOME'] = str(profile)
        # Do not inherit an Agent's externally injected inference/API authentication.
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'CODEX_SESSION_ID', 'CODEX_THREAD_ID'):
            env.pop(key, None)
    elif product == 'antigravity':
        env.update(USERPROFILE=str(profile), APPDATA=str(profile / 'AppData' / 'Roaming'),
                   LOCALAPPDATA=str(profile / 'AppData' / 'Local'), XDG_CONFIG_HOME=str(profile / '.config'),
                   AGY_CLI_DISABLE_AUTO_UPDATE='1')
    return env


def cli_program(product):
    override = os.environ.get('TOKENVIEW_CODEX' if product == 'codex' else 'TOKENVIEW_AGY')
    if override:
        path = Path(override)
        if not path.is_file() or path.suffix.lower() != '.exe':
            raise ProviderError('配置的 CLI 路径不可用')
        return path
    command = shutil.which('codex.exe' if product == 'codex' else 'agy.exe')
    if command:
        return Path(command)
    if product == 'codex':
        root = Path(os.environ.get('USERPROFILE', '')) / '.myagents' / 'runtimes' / 'codex'
        choices = list(root.glob('*/win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe'))
        if choices:
            choices.sort(key=lambda p: tuple(int(n) for n in p.parents[4].name.split('.') if n.isdigit()), reverse=True)
            return choices[0]
    else:
        agy_env = os.environ.get('TOKENVIEW_AGY')
        if agy_env and Path(agy_env).is_file():
            return Path(agy_env)
        fallback = Path(os.environ.get('USERPROFILE', '')) / '.antigravity' / 'bin' / 'agy.exe'
        if fallback.is_file():
            return fallback
    raise ProviderError('未找到 Codex CLI' if product == 'codex' else '未找到 AGY CLI')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProviderError('查询地址发生重定向，已停止发送凭据')


class Provider:
    def __init__(self, store):
        self.store = store
        self.active = {}
        self.lock = threading.Lock()
        self.closed = False

    def register(self, account_id, process):
        with self.lock:
            if self.closed:
                if process.poll() is None:
                    process.terminate()
                raise ProviderError('程序已退出')
            self.active.setdefault(account_id,set()).add(process)

    def unregister(self, account_id, process):
        with self.lock:
            processes=self.active.get(account_id)
            if processes:
                processes.discard(process)
                if not processes:
                    self.active.pop(account_id,None)

    def cancel(self, account_id):
        with self.lock:
            processes=list(self.active.pop(account_id,set()))
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

    def close(self):
        with self.lock:
            self.closed=True
            accounts=list(self.active)
        for account_id in accounts:
            self.cancel(account_id)

    def rpc(self,account):
        from .integrated import myagents_home
        shared = account.connection == 'myagents'
        profile=myagents_home() / 'codex' if shared else self.store.profile(account)
        return CodexRpc(cli_program('codex'),profile_env('codex',profile),profile,
            register=lambda p:self.register(account.id,p),unregister=lambda p:self.unregister(account.id,p),
            credential_store='auto' if shared else 'keyring')

    def fetch(self, account, cancel=None):
        try:
            if cancel is not None and cancel.is_set():
                raise ProviderError('已取消查询')
            if self.closed:
                raise ProviderError('程序已退出')
            if account.product == 'deepseek':
                if account.connection == 'myagents':
                    from .integrated import deepseek_key
                    key = deepseek_key()
                else:
                    key = self.store.secret(account.id)
                request = urllib.request.Request('https://api.deepseek.com/user/balance', headers={'Authorization': 'Bearer ' + key})
                opener = urllib.request.build_opener(NoRedirect())
                with opener.open(request, timeout=20) as response:
                    raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ProviderError('官方响应过大')
                return parse_deepseek(json.loads(raw))
            if account.product == 'codex':
                with self.rpc(account) as rpc:
                    if account.connection=='myagents':
                        identity=rpc.request('account/read',{'refreshToken':False}).get('account') or {}
                        if identity.get('email'):
                            account.name=identity['email']
                    result = rpc.request('account/rateLimits/read')
                    return parse_codex(result)
            if account.connection != 'myagents':
                from .agy_accounts import fetch
                return fetch(self, account, cancel)
            # The host-linked row remains read-only and never shares a new account's authorization.
            agy_env=dict(os.environ,AGY_CLI_DISABLE_AUTO_UPDATE='1')
            log_handle,log_name=tempfile.mkstemp(prefix='agy-usage-',suffix='.log',dir=self.store.root)
            os.close(log_handle)
            p = subprocess.Popen([str(cli_program('antigravity')), '-p', '/usage', '--output-format', 'json', '--log-file',log_name],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               creationflags=0x08000000, cwd=self.store.root,env=agy_env)
            self.register(account.id,p)
            try:
                output,_=p.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                self.cancel(account.id)
                raise
            finally:
                self.unregister(account.id,p)
                try:
                    # Read only the authenticated identity, never output raw CLI logs.
                    identity_log=Path(log_name).read_text('utf-8',errors='replace')[-262144:]
                    identities=re.findall(r'applyAuthResult: email=([^\s,]+)',identity_log)
                finally:
                    Path(log_name).unlink(missing_ok=True)
            if p.returncode != 0:
                raise ProviderError('AGY 查询失败，请确认 AGY 已登录')
            if len(output) > 1024 * 1024:
                raise ProviderError('AGY 响应过大')
            if account.connection=='myagents':
                from .integrated import antigravity_identity
                expected=antigravity_identity()
                if not identities or not expected or identities[-1].casefold()!=expected.casefold():
                    raise ProviderError('AGY 与 MyAgents 账号不一致，未混用额度')
                account.name=expected
            return parse_agy(json.loads(output))
        except ProviderError:
            raise
        except RpcError as e:
            raise ProviderError(str(e)) from None
        except urllib.error.HTTPError as e:
            raise ProviderError('Key 无效或已失效' if e.code in (401, 403) else '额度接口暂不可用，请稍后重试') from None
        except (subprocess.TimeoutExpired, TimeoutError):
            raise ProviderError('查询超时，将保留上次成功数据') from None
        except KeyError:
            raise ProviderError('请重新添加 API Key') from None
        except Exception:
            raise ProviderError('查询失败，请检查网络、登录或 CLI 版本') from None

    def authorize(self, account, open_url, cancel):
        if account.connection == 'myagents':
            raise ProviderError('此账号由 MyAgents 管理，请在 MyAgents 中登录')
        if account.product == 'antigravity':
            from .agy_accounts import authorize
            return authorize(self, account, open_url, cancel)
        if account.product != 'codex':
            raise ProviderError('该产品不使用登录授权')
        profile = self.store.profile(account)
        try:
            with self.rpc(account) as rpc:
                return rpc.login(open_url, cancel)
        except RpcError as e:
            raise ProviderError(str(e)) from None

    def revoke(self, account):
        if account.connection == 'myagents':
            return
        if account.product == 'codex':
            profile = self.store.profile(account)
            with self.rpc(account) as rpc:
                rpc.request('account/logout', timeout=15)
