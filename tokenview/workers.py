"""Small daemon worker pool: network timeouts cannot hold the GUI process open."""
import concurrent.futures
import queue
import threading


class WorkerPool:
    def __init__(self, count=4):
        self.queue=queue.Queue()
        self.closed=False
        self.threads=[]
        for index in range(count):
            thread=threading.Thread(target=self._work,name=f'tokenview-worker-{index}',daemon=True)
            thread.start()
            self.threads.append(thread)

    def _work(self):
        while True:
            task=self.queue.get()
            if task is None:
                return
            future,fn,args=task
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(fn(*args))
            except BaseException as e:
                future.set_exception(e)

    def submit(self,fn,*args):
        if self.closed:
            raise RuntimeError('worker pool closed')
        future=concurrent.futures.Future()
        self.queue.put((future,fn,args))
        return future

    def shutdown(self):
        self.closed=True
        while True:
            try:
                task=self.queue.get_nowait()
            except queue.Empty:
                break
            if task:
                task[0].cancel()
        for thread in self.threads:
            self.queue.put(None)
