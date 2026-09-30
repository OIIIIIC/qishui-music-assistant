"""Bounded end-to-end validation using exactly the same Runner as the app."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
os.environ['QISHUI_DATA_DIR'] = str(Path('.local/live-test').resolve())
from PySide6.QtCore import QCoreApplication, QTimer
from qishui.storage import load_settings
from qishui.worker import Runner

p=argparse.ArgumentParser()
p.add_argument('--rounds',type=int,default=1)
p.add_argument('--seconds',type=int,default=240)
p.add_argument('--platform',choices=('auto','harmony','android'),default='auto')
p.add_argument('--serial',default='')
a=p.parse_args()
app=QCoreApplication([])
settings=load_settings() | {'target':a.rounds,'max_minutes':max(1,a.seconds//60),
                            'platform':a.platform,'serial':a.serial}
worker=Runner(settings)
worker.logged.connect(lambda s: print(s,flush=True))
def report(s):
    print(json.dumps(s,ensure_ascii=False),flush=True)
    if s['status']=='paused':
        worker.stop()
worker.changed.connect(report)
worker.finished.connect(app.quit)
QTimer.singleShot(a.seconds*1000,worker.stop)
worker.start()
app.exec()
