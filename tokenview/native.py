import ctypes
from ctypes import wintypes
import os
import time
import winreg
from pathlib import Path

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
dwm = ctypes.WinDLL('dwmapi', use_last_error=True)
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.GetDpiForWindow.argtypes = [wintypes.HWND]
user32.GetDpiForWindow.restype = wintypes.UINT
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HANDLE


class MonitorInfo(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT), ('work', wintypes.RECT), ('flags', wintypes.DWORD)]


user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]


def init_dpi():
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        user32.SetProcessDPIAware()


def process_id(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_name(pid):
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return ''
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return Path(buffer.value).name.lower()
        return ''
    finally:
        kernel32.CloseHandle(handle)


def window_rect(hwnd):
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def sample_host_background(hwnd, excluded=()):
    """Read a few visible host-titlebar pixels; no screenshot/image is created.

    Confirm each point belongs to this exact host root. Never sample another
    foreground application's contents or our own covering windows.
    """
    bounds = window_rect(hwnd)
    if not bounds:
        return []
    x, y, width, height = bounds
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    gdi = ctypes.WinDLL('gdi32')
    gdi.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi.GetPixel.restype = wintypes.DWORD
    scale = max(1, user32.GetDpiForWindow(hwnd) / 96)
    points = [(x + round(width * fraction), y + round(offset * scale))
              for offset in (14, 28) for fraction in (.12, .24, .4, .56, .72, .86)]
    if excluded:
        left, top, w, h = excluded[0]
        points[:0] = [(left - 12, top + h // 2), (left + w + 12, top + h // 2)]
    samples = []
    dc = user32.GetDC(None)
    if not dc:
        return samples
    try:
        for px, py in points:
            if not (x <= px < x + width and y <= py < y + height):
                continue
            if any(a <= px < a + w and b <= py < b + h for a, b, w, h in excluded):
                continue
            at = user32.WindowFromPoint(wintypes.POINT(px, py))
            if not at or user32.GetAncestor(at, 2) != hwnd:
                continue
            value = gdi.GetPixel(dc, px, py)
            if value != 0xFFFFFFFF:
                samples.append((value & 255, (value >> 8) & 255, (value >> 16) & 255))
    finally:
        user32.ReleaseDC(None, dc)
    return samples


def work_area(hwnd):
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    if user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):
        r = info.work
        return r.left, r.top, r.right, r.bottom
    return (0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1) - 48)


def no_shadow(hwnd):
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    policy = ctypes.c_int(1)
    dwm.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(policy), 4)


def no_activate(hwnd):
    user32.GetWindowLongPtrW.argtypes=[wintypes.HWND,ctypes.c_int]
    user32.GetWindowLongPtrW.restype=ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype=ctypes.c_ssize_t
    style=user32.GetWindowLongPtrW(hwnd,-20)
    user32.SetWindowLongPtrW(hwnd,-20,style|0x08000000|0x80)


class Host:
    def __init__(self):
        self.hwnd = None
        self.cache = {}
        self.next_discovery=0

    def discover(self):
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        candidates=[]
        def inspect_window(hwnd,param):
            if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                pid=process_id(hwnd)
                if pid not in self.cache:
                    self.cache[pid]=(process_name(pid),time.monotonic())
                if self.cache[pid][0]=='myagents.exe':
                    rect=window_rect(hwnd)
                    if rect and rect[2]>=400 and rect[3]>=300:
                        candidates.append((rect[2]*rect[3],hwnd))
            return True
        user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
        user32.EnumWindows(callback_type(inspect_window),0)
        if candidates:
            self.hwnd=max(candidates,key=lambda v:v[0])[1]

    def inspect(self):
        front = user32.GetForegroundWindow()
        pid = process_id(front)
        now = time.monotonic()
        if pid not in self.cache or now - self.cache[pid][1] > 10:
            self.cache[pid] = (process_name(pid), now)
        name = self.cache[pid][0]
        if name == 'myagents.exe' and user32.IsWindowVisible(front) and not user32.IsIconic(front):
            self.hwnd = front
        valid = bool(self.hwnd and user32.IsWindow(self.hwnd) and user32.IsWindowVisible(self.hwnd) and not user32.IsIconic(self.hwnd))
        if not valid and now>=self.next_discovery:
            self.next_discovery=now+5
            self.discover()
            valid=bool(self.hwnd and user32.IsWindowVisible(self.hwnd) and not user32.IsIconic(self.hwnd))
        own = pid == os.getpid()
        return valid, name == 'myagents.exe', own


def set_startup(enabled, launcher):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:
            command = f'"{launcher}"' if Path(launcher).suffix.lower()=='.exe' else f'wscript.exe "{launcher}"'
            winreg.SetValueEx(key, 'TokenViewPythonPersonal', 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, 'TokenViewPythonPersonal')
            except FileNotFoundError:
                pass


def single_instance(root):
    import hashlib
    digest = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    handle = kernel32.CreateMutexW(None, False, 'Local\\TokenViewPython-' + digest)
    if not handle:
        raise OSError('无法创建单实例锁')
    return handle, ctypes.get_last_error() != 183
