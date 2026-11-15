"""Cancellable QProcess client; bounded logs and automatic idle model release."""
import json
import math
from pathlib import Path
from uuid import uuid4
from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal


class WarmClient(QObject):
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)
    released = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, parent=None, idle_ms=60000):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.started.connect(self._send)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(self._log)
        self.process.finished.connect(self._exit)
        self.process.errorOccurred.connect(self._error)
        self.idle = QTimer(self)
        self.idle.setSingleShot(True)
        self.idle.setInterval(idle_ms)
        self.idle.timeout.connect(self.stop)
        self.config = None
        self.request = None
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.log_line = bytearray()
        self.stopping = False

    @property
    def busy(self):
        return self.request is not None

    def hold_idle(self):
        """Keep a resident model while the user records/transcribes a next line."""
        self.idle.stop()

    def resume_idle(self):
        if not self.busy and not self.stopping and self.process.state() == QProcess.ProcessState.Running:
            self.idle.start()

    def submit(self, python, request, environment, script=None):
        if self.busy:
            raise RuntimeError('A conversion is already running.')
        config = (python, request['engine'], request.get('device', 'cpu'),
                  request.get('weights'), request.get('repo'), request.get('cache'), request.get('manifest'),
                  tuple(sorted(environment.toStringList())))
        self.idle.stop()
        if self.config != config:
            if not self.stop(wait=True):
                raise RuntimeError('Previous worker is still stopping. Try again shortly.')
        self.config = config
        self.stopping = False
        self.request = dict(request, id=uuid4().hex)
        self.stdout.clear()
        self.stderr.clear()
        self.log_line.clear()
        if self.process.state() == QProcess.ProcessState.Running:
            self._send()
        elif self.process.state() == QProcess.ProcessState.NotRunning:
            self.process.setProcessEnvironment(environment)
            self.process.start(python, [str(script or Path(__file__).with_name('warm_worker.py'))])
        else:
            self.request = None
            raise RuntimeError('Worker is still stopping. Try again shortly.')

    def _send(self):
        if self.request is not None:
            self.process.write((json.dumps(self.request) + '\n').encode())

    def _log(self):
        chunk = bytes(self.process.readAllStandardError())
        self.stderr.extend(chunk)
        self.stderr = self.stderr[-8192:]
        self.log_line.extend(chunk)
        while b'\n' in self.log_line:
            line, _, self.log_line = self.log_line.partition(b'\n')
            # Only our adapter's concise stages belong in the UI, not model logs.
            if self.request is not None and line.startswith(b'[PVS] '):
                self.progress.emit(line[6:506].decode(errors='replace'))
        self.log_line = self.log_line[-1024:]

    def _read(self):
        self.stdout.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.stdout) > 65536:
            self._fail('Worker returned too much protocol output.')
            return
        while b'\n' in self.stdout:
            line, _, rest = self.stdout.partition(b'\n')
            self.stdout = bytearray(rest)
            try:
                result = json.loads(line)
                if not isinstance(result, dict):
                    raise ValueError()
            except (ValueError, UnicodeError):
                self._fail('Worker returned malformed output.')
                return
            if self.request is None or result.get('id') != self.request['id']:
                continue  # An obsolete/cancelled request must never play.
            if not result.get('ok'):
                self._fail(result.get('error', 'Conversion failed.'))
                return
            seconds = result.get('seconds')
            if (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
                    or type(result.get('warm')) is not bool):
                self._fail('Worker returned invalid conversion timing or model status.')
                return
            if result.get('output_path') != self.request['output_path'] or not Path(result['output_path']).is_file():
                self._fail('Worker did not produce the requested audio file.')
                return
            self.request = None
            self.idle.start()
            self.completed.emit(result)

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.request is not None:
            self._fail('Could not start the runtime: ' + self.process.errorString())

    def _exit(self, code, status):
        self._log()
        if self.request is not None and not self.stopping:
            self._fail('Worker exited before completing conversion. ' + self.stderr.decode(errors='replace')[-1500:])
        self.config = None
        self.released.emit()

    def _fail(self, message):
        self.stop()
        self.failed.emit(str(message))

    def stop(self, wait=False):
        self.idle.stop()
        self.request = None
        self.config = None
        self.stopping = True
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            if wait:
                self.process.waitForFinished(3000)
        return self.process.state() == QProcess.ProcessState.NotRunning
