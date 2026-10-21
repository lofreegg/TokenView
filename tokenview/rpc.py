import json
import queue
import subprocess
import threading
import time


class RpcError(Exception):
    pass


class CodexRpc:
    def __init__(self, program, env, cwd, register=None, unregister=None, credential_store='keyring'):
        self.messages = queue.Queue(maxsize=128)
        self.pending = []
        self.counter = 0
        self.process = subprocess.Popen([str(program), '-c', f'cli_auth_credentials_store="{credential_store}"', 'app-server'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=cwd,
            creationflags=0x08000000)
        self.unregister=unregister
        if register:
            register(self.process)
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.request('initialize', {'clientInfo': {'name': 'tokenview_python', 'version': '0.1.0'}}, timeout=20)
            self.send({'method': 'initialized', 'params': {}})
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(1024 * 1024 + 1)
                if not line or len(line) > 1024 * 1024:
                    break
                value = json.loads(line)
                self.messages.put(value, timeout=1)
        except Exception:
            pass
        finally:
            try:
                self.messages.put(None, timeout=1)
            except queue.Full:
                pass

    def send(self, value):
        self.process.stdin.write((json.dumps(value) + '\n').encode())
        self.process.stdin.flush()

    def request(self, method, params=None, timeout=30):
        self.counter += 1
        request_id = self.counter
        value = {'method': method, 'id': request_id}
        if params is not None:
            value['params'] = params
        self.send(value)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                raise RpcError('Codex 查询超时，保留上次成功数据') from None
            if message is None:
                raise RpcError('Codex 查询进程提前结束')
            if message.get('id') == request_id:
                if 'error' in message:
                    raw = str(message['error']).lower()
                    if any(t in raw for t in ('auth', 'login', 'sign in', 'log in', 'unauthorized')):
                        raise RpcError('请先登录授权')
                    raise RpcError('Codex 服务暂不可查询，请稍后重试')
                return message.get('result', {})
            if 'method' in message:
                self.pending.append(message)
        raise RpcError('Codex 查询超时')

    def login(self, open_url, cancel):
        result = self.request('account/login/start', {'type': 'chatgpt'}, timeout=30)
        url = result.get('authUrl', '')
        if not url.startswith(('https://auth.openai.com/', 'https://chatgpt.com/', 'https://auth0.openai.com/')):
            raise RpcError('授权地址未被识别，请更新官方 Codex CLI')
        open_url(url)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline and not cancel.is_set():
            if self.pending:
                message = self.pending.pop(0)
            else:
                try:
                    message = self.messages.get(timeout=0.5)
                except queue.Empty:
                    continue
            if message is None:
                raise RpcError('登录进程提前结束')
            if message.get('method') == 'account/login/completed':
                if message.get('params', {}).get('success'):
                    return True
                raise RpcError('登录未完成，请重试')
        try:
            self.request('account/login/cancel', {'loginId': result.get('loginId')}, timeout=3)
        except Exception:
            pass
        raise RpcError('登录已取消或超时')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for pipe in (self.process.stdin, self.process.stdout):
            if pipe:
                pipe.close()
        if self.unregister:
            self.unregister(self.process)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
