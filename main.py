import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import *
from PyQt5 import uic, QtCore
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import core


form_class = uic.loadUiType("./main.ui")[0]

class MainWindow(QMainWindow, form_class, QObject):
    main_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # UI Setting
        self.setupUi(self)

        self.setFixedSize(562, 332)  # Fix window size
        self.setWindowFlags(QtCore.Qt.MSWindowsFixedSizeDialogHint)  # Remove resizing mouse cursor

        # StatusBar
        self.statusBar = QStatusBar(self)
        self.statusBar.setSizeGripEnabled(False)  # Remove resizing grip of status bar
        self.setStatusBar(self.statusBar)

        # Enable Drag & Drop file into GUI
        self.setAcceptDrops(True)

        # PushButton
        self.pathButton.clicked.connect(self._btnOpenPath)
        self.cancelButton.clicked.connect(self._forceWorkerReset)

        # Worker Thread
        self.worker = core.Core()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        # Connect Signals
        self._connectSignals()

    def _connectSignals(self):
        self.main_signal.connect(self.worker.main)
        self.patchButton.clicked.connect(self._transmitData)

        self.worker.finished.connect(self._updateLog)
        self.worker.finished_err.connect(self._eventHandler)

    def _btnOpenPath(self):
        fname = QFileDialog.getOpenFileName(self)
        
        self.pathEdit.setText(str(Path(fname[0])))

    # Drag & Drop event handler: https://gist.github.com/peace098beat/db8ef7161508e6500ebe
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        
        self.pathEdit.setText(str(Path(files[0])))  # Currently load only one file.

    def _transmitData(self):
        # Force reset worker thread
        self._forceWorkerReset()
        self.worker_thread.start()

        self.logEdit.setPlainText("")

        if self.pathEdit.text() == "":
            return

        self.main_signal.emit(self.pathEdit.text())
    
    @pyqtSlot(str)
    def _updateLog(self, signal):
        currentLog = self.logEdit.toPlainText()

        self.logEdit.setPlainText("%s\n%s" % (currentLog, signal))
        self.logEdit.moveCursor(QTextCursor.End)

        if "Done." in signal:
            self._forceWorkerReset()

    def _forceWorkerReset(self):
        if self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()

    # Handle exception events
    @pyqtSlot(list)
    def _eventHandler(self, event):
        self.msgbox = QMessageBox(self)
        self.msgbox.setIcon(QMessageBox.Information)
        self.msgbox.setWindowTitle("Error")

        if event[0]:
            self.msgbox.setText("예기치 못한 오류가 발생했습니다.")
            self.msgbox.setInformativeText("자세한 정보는 아래 Show Details.. 버튼을 눌러 확인해주십시요.")
            self.msgbox.setDetailedText(event[1])
        else:
            self.msgbox.setText("오류가 발생했습니다.")
            self.msgbox.setInformativeText(event[1])

        self.msgbox.setStandardButtons(QMessageBox.Ok)

        self.msgbox.show()
        self._forceWorkerReset()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
