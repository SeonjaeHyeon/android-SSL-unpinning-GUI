import os
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import subprocess as sp

from PyQt5.QtCore import *


class Core(QObject):
    finished = pyqtSignal(str)
    finished_err = pyqtSignal(list)

    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)

    @pyqtSlot()
    def _die(self, msg):
        self.finished_err.emit([0, msg])

    @pyqtSlot()
    def _check(self, proc):
        chk = True
        if os.name == "posix":  # Linux
            try:
                sp.check_call(["which", proc], stdout=sp.DEVNULL, stderr=sp.DEVNULL, stdin=sp.DEVNULL)
            except sp.CalledProcessError:
                chk = False
        else:  # Windows
            try:
                sp.check_call(["where", proc], stdout=sp.DEVNULL, stderr=sp.DEVNULL, stdin=sp.DEVNULL)
            except sp.CalledProcessError:
                chk = False

        return chk

    @pyqtSlot()
    def _execute_command(self, cmd):
        self.process = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, stdin=sp.DEVNULL)

        while self.process.poll() is None:
            output = self.process.stdout.readline().decode("utf-8").strip()
            if not output:  # The line is null
                continue

            self.finished.emit(output)

        if self.process.poll():
            stdout, stderr = self.process.communicate()
            self.finished_err.emit([1, stderr.decode("utf-8").strip()])
            return 1

        self.process = None
        return None

    @pyqtSlot()
    def _patch_manifest_file(self, manifest_file):
        try:
            tree = ET.parse(manifest_file)
            root = tree.getroot()

            application = root.find("application")
            network_security_config = application.get(
                "{http://schemas.android.com/apk/res/android}networkSecurityConfig"
            )

            # if network security config attribute not exists, inject it
            if network_security_config is None:
                application.set(
                    "{http://schemas.android.com/apk/res/android}networkSecurityConfig",
                    "@xml/network_security_config",
                )

            with open(manifest_file, "w", encoding="utf-8") as f:
                f.write(ET.tostring(root, encoding="utf-8").decode())
        except Exception as E:
            self.finished_err.emit([1, str(E)])
            return

    @pyqtSlot()
    def _patch_network_security_config(self, config_file):
        try:
            cfg = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <debug-overrides>
        <trust-anchors>
            <certificates src="user" />
        </trust-anchors>
    </debug-overrides>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system" />
            <certificates src="user" />
        </trust-anchors>
    </base-config>
</network-security-config>
"""
            with open(config_file, "w") as f:
                f.write(cfg)
        except Exception as E:
            self.finished_err.emit([1, str(E)])
            return

    @pyqtSlot(str)
    def main(self, apk_path):
        try:
            self.finished.emit("Checking whether Java is installed..")
            self._check("java") or self._die("Java is not installed")

            apktool = "apktool_2.4.1.jar"
            sign = "sign-1.0.jar"
            target_apk = apk_path

            self.finished.emit("Checking file extension..")

            if not target_apk.endswith(".apk"):
                self.finished_err.emit(
                    [0, "The extension of `{}` is not .apk, is it really a APK file?".format(target_apk)]
                    )
                return

            target_apk_unpacked = target_apk.rstrip(".apk")
            target_apk_repacked = target_apk_unpacked + ".repack.apk"

            # Unpacking
            self.finished.emit("Decompiling APK..")

            if self._execute_command(["java", "-jar", apktool, "d", target_apk]):
                return

            # Patch security config of APK to trust user rook certificate
            self.finished.emit("Patching config..")

            manifest_file = Path(target_apk_unpacked) / "AndroidManifest.xml"
            self._patch_manifest_file(str(manifest_file))
            config_file = Path(target_apk_unpacked) / "res" / "xml" / "network_security_config.xml"
            self._patch_network_security_config(str(config_file))

            # Repacking
            self.finished.emit("Re-compiling APK..")

            if self._execute_command(["java", "-jar", apktool, "b", target_apk_unpacked, "-o", target_apk_repacked]):
                return

            # Signing
            self.finished.emit("Signing APK..")

            if self._execute_command(["java", "-jar", sign, target_apk_repacked]):
                return

            # Clean up
            self.finished.emit("Deleting temp files..")

            shutil.rmtree(target_apk_unpacked)
            os.remove(target_apk_repacked)

            self.finished.emit("Done.")
        except Exception as E:
            self.finished_err.emit([1, str(E)])
            return
