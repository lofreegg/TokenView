import queue
import threading
import time
import uuid
import shutil
from .workers import WorkerPool
from .providers import Provider, ProviderError


class AlertTracker:
    def __init__(self):
        self.alerted = set()

    def check(self, account_id, metrics, threshold, money_threshold=5):
        messages = []
        for metric in metrics:
            unit = metric.get('unit')
            if unit != 'percent':
                if unit not in ('CNY','USD') or metric['label']!='余额':
                    continue
                key=(account_id,'balance',unit,None)
                if metric['value']>money_threshold:
                    self.alerted.discard(key)
                elif key not in self.alerted:
                    self.alerted.add(key)
                    messages.append(f"余额剩余 {metric['value']:.2f} {unit}")
                continue
            prefix = (account_id, metric.get('group', ''), metric.get('period', metric['label']))
            key = prefix + (metric.get('reset'),)
            if metric['value'] > threshold:
                self.alerted = {v for v in self.alerted if v[:3] != prefix}
            elif key not in self.alerted:
                self.alerted.add(key)
                messages.append(f"{metric.get('group', '')} {metric['label']} 剩余 {metric['value']:g}%".strip())
        return messages


class Controller:
    def __init__(self, store):
        self.store = store
        self.provider = Provider(store)
        self.pool = WorkerPool(4)
        self.events = queue.Queue()
        self.running = {}
        self.closed = False
        self.alerts = AlertTracker()
        self.next_refresh = time.monotonic()
        self.next_feed = time.monotonic()
        self.feed_running = False
        self.feed_error = ''
        self.last_alert_account = None

    def refresh(self, account_id=None):
        if self.closed:
            return
        accounts = [self.store.accounts[account_id]] if account_id in self.store.accounts else list(self.store.accounts.values())
        for account in accounts:
            if account.id in self.running:
                continue
            cancel = threading.Event()
            self.running[account.id] = ('refresh', cancel)
            future = self.pool.submit(self.provider.fetch, account, cancel)
            future.add_done_callback(lambda f, i=account.id, g=account.generation: self.events.put(('snapshot', i, g, f)))
        self.next_refresh = time.monotonic() + self.store.settings['refresh_seconds']

    def authorize(self, account, open_url):
        if self.closed or account.id in self.running:
            return
        if any(kind=='login' for kind,_ in self.running.values()):
            self.store.update_snapshot(account.id,account.generation,None,'请先完成正在进行的登录，再重试此账号')
            return
        cancel = threading.Event()
        self.running[account.id] = ('login', cancel)
        def safe_open(url):
            if not cancel.is_set() and account.id in self.store.accounts:
                self.events.put(('open_url', url, account.id, account.generation, cancel))
        future = self.pool.submit(self.provider.authorize, account, safe_open, cancel)
        future.add_done_callback(lambda f, g=account.generation: self.events.put(('authorized', account.id, g, f)))

    def remove(self, account):
        active = self.running.pop(account.id, None)
        if active:
            active[1].set()
        self.provider.cancel(account.id)
        if account.product == 'codex' and account.connection != 'myagents':
            account.generation=uuid.uuid4().hex
            self.store.update_snapshot(account.id,account.generation,None,'正在撤销登录…')
            self.running[account.id]=('remove',threading.Event())
            future = self.pool.submit(self._remove_owned, account)
            future.add_done_callback(lambda f, g=account.generation: self.events.put(('revoked', account.id,g,f)))
        else:
            self.store.remove_account(account.id)

    def _remove_owned(self,account):
        self.provider.revoke(account)
        root=(self.store.root/'profiles').resolve()
        path=(root/account.id).resolve()
        if path.parent!=root or len(account.id)!=32 or any(c not in '0123456789abcdef' for c in account.id):
            raise ProviderError('账号数据目录未通过校验')
        if path.exists():
            shutil.rmtree(path)

    def tick(self):
        if self.closed:
            return
        now = time.monotonic()
        if now >= self.next_refresh:
            self.refresh()

    def collect(self):
        notices = []
        changed = False
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] in ('snapshot', 'authorized'):
                kind, account_id, generation, future = event
                self.running.pop(account_id, None)
                account = self.store.accounts.get(account_id)
                if not account or account.generation != generation:
                    continue
                try:
                    result = future.result()
                    if kind == 'authorized':
                        self.refresh(account_id)
                    else:
                        self.store.update_snapshot(account_id, generation, result)
                        if self.store.settings['alerts']:
                            for message in self.alerts.check(account_id, result['metrics'], self.store.settings['threshold'], self.store.settings['money_threshold']):
                                self.last_alert_account = account_id
                                notices.append(('alert', f'{account.name}：{message}'))
                except ProviderError as e:
                    self.store.update_snapshot(account_id, generation, None, str(e))
                except Exception:
                    self.store.update_snapshot(account_id, generation, None, '连接未完成，请重试')
                changed = True
            elif event[0] == 'open_url':
                _, url, account_id, generation, cancel = event
                account = self.store.accounts.get(account_id)
                if not self.closed and not cancel.is_set() and account and account.generation == generation:
                    notices.append(('open_url', url))
            elif event[0] == 'feed':
                self.feed_running = False
                try:
                    self.store.feed = event[1].result()
                    self.store.save()
                    self.feed_error = ''
                except Exception:
                    self.feed_error = '信息获取失败，保留上次内容'
                changed = True
            elif event[0] == 'revoked':
                _,account_id,generation,future=event
                self.running.pop(account_id,None)
                try:
                    future.result()
                    self.store.remove_account(account_id)
                except Exception:
                    self.store.update_snapshot(account_id,generation,None,'登录撤销失败，请再次点击移除重试')
                    notices.append(('notice', '账号移除尚未完成。为便于重试，账号仍保留在列表中。'))
                changed=True
        return changed, notices

    def close(self):
        # Same boundary as independent OAuth credential commit. Cancellation
        # cannot become visible halfway through that commit.
        with self.provider.lock:
            self.closed = True
            self.provider.closed = True
            for _, cancel in self.running.values():
                cancel.set()
        self.provider.close()
        self.pool.shutdown()
