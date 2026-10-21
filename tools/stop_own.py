"""Graceful WM_QUIT for an explicitly selected TokenView instance only."""
import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tokenview import native

parser=argparse.ArgumentParser()
parser.add_argument('--pid',type=int,required=True)
args=parser.parse_args()
callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
native.user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
native.user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
native.user32.PostThreadMessageW.argtypes=[wintypes.DWORD,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
threads=set()
def find(hwnd,param):
    if native.process_id(hwnd)!=args.pid:
        return True
    title=ctypes.create_unicode_buffer(256)
    native.user32.GetWindowTextW(hwnd,title,256)
    if title.value.startswith('TokenView Python •'):
        threads.add(native.user32.GetWindowThreadProcessId(hwnd,None))
    return True
native.user32.EnumWindows(callback_type(find),0)
if not threads:
    raise SystemExit('No matching TokenView-owned window; no action taken')
for thread in threads:
    assert native.user32.PostThreadMessageW(thread,0x0012,0,0)
print('graceful-quit-posted',args.pid)
