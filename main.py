import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import traceback
import faulthandler

ROOT = Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    if getattr(sys,'frozen',False):
        runtime_cache = ROOT / 'runtime-cache'
        runtime_cache.mkdir(parents=True,exist_ok=True)
        os.environ['TEMP'] = os.environ['TMP'] = str(runtime_cache)
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=str(ROOT / 'app-data'))
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    from tokenview import native
    native.init_dpi()
    data = Path(args.data_dir).resolve()
    data.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data / 'application.log', maxBytes=256*1024, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')
    fault_log = open(data / 'native-fault.log', 'a', encoding='utf-8')
    faulthandler.enable(file=fault_log, all_threads=True)
    mutex, first = native.single_instance(data)
    if not first:
        logging.info('duplicate launch pid=%s; waking existing instance', os.getpid())
        (data/'wake.flag').write_text('wake','ascii')
        native.kernel32.CloseHandle(mutex)
        return
    logging.info('process started pid=%s parent=%s smoke=%s',os.getpid(),os.getppid(),args.smoke)
    import clr
    clr.AddReference('System.Windows.Forms')
    from System.Threading import Thread, ThreadStart, ApartmentState
    failures = []
    def desktop_main():
        ui = None
        try:
            from tokenview.store import Store
            from tokenview.service import Controller
            from tokenview.ui import Desktop
            from System.Windows.Forms import Application, UnhandledExceptionMode
            Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException)
            def ui_exception(sender, event):
                logging.error('UI callback exception: %s', event.Exception.ToString())
            Application.ThreadException += ui_exception
            Application.EnableVisualStyles()
            Application.SetCompatibleTextRenderingDefault(False)
            store = Store(data)
            if not args.smoke:
                from tokenview.integrated import connect_existing
                connect_existing(store)
            controller = Controller(store)
            ui = Desktop(store, controller, args.smoke)
            if args.smoke:
                from tools.smoke import smoke
                smoke(ui)
            else:
                ui.run()
                logging.info('UI message loop returned pid=%s closed=%s',os.getpid(),ui.closed)
        except BaseException:
            failures.append(traceback.format_exc())
            logging.error('启动失败：%s', failures[-1])
        finally:
            if ui and not ui.closed:
                ui.exit()
    thread = Thread(ThreadStart(desktop_main))
    thread.SetApartmentState(ApartmentState.STA)
    thread.Start()
    thread.Join()
    faulthandler.disable()
    fault_log.close()
    native.kernel32.CloseHandle(mutex)
    logging.info('process completed pid=%s failures=%s',os.getpid(),len(failures))
    if failures:
        if sys.stdout:
            print(failures[-1])
        else:
            native.user32.MessageBoxW(None,'TokenView 启动失败，请查看程序目录 app-data/application.log。','TokenView',0x10)
        sys.exit(1)


if __name__ == '__main__':
    main()
