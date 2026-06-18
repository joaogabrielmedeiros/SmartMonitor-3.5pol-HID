# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import glob
import os
import select
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from library.lcd.lcd_comm_rev_a import LcdCommRevA
from library.log import logger


class LcdCommRevAHid(LcdCommRevA):
    USB_VENDOR_ID = "00000483"
    USB_PRODUCT_ID = "00000065"
    HID_REPORT_SIZE = 64
    SMARTMONITOR_RESET_COMMAND = b"\x01reset"
    SMARTMONITOR_YMODEM_COMMAND = b"ymodem"
    YMODEM_SOH = 0x01
    YMODEM_STX = 0x02
    YMODEM_EOT = 0x04
    YMODEM_ACK = 0x06
    YMODEM_NAK = 0x15
    SMARTMONITOR_TIME_COMMAND = 0x03

    def __init__(self, com_port: str = "AUTO", display_width: int = 320, display_height: int = 480,
                 update_queue=None):
        logger.debug("HW revision: A over HID (experimental)")
        self.requested_com_port = com_port
        self._io_lock = threading.Lock()
        super().__init__(com_port=com_port, display_width=display_width, display_height=display_height,
                         update_queue=update_queue)

    @staticmethod
    def _uevent_to_dict(uevent_path: str) -> dict[str, str]:
        data = {}
        with open(uevent_path, "rt", encoding="utf-8") as stream:
            for line in stream:
                if "=" not in line:
                    continue
                key, value = line.strip().split("=", 1)
                data[key] = value
        return data

    @classmethod
    def auto_detect_com_port(cls) -> Optional[str]:
        for uevent_path in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
            try:
                data = cls._uevent_to_dict(uevent_path)
            except OSError:
                continue

            if data.get("HID_ID", "").upper() != f"0003:{cls.USB_VENDOR_ID}:{cls.USB_PRODUCT_ID}":
                continue

            hidraw_name = Path(uevent_path).parents[1].name
            return f"/dev/{hidraw_name}"

        return None

    @staticmethod
    def _trace_path() -> Optional[str]:
        return os.environ.get("SMARTMONITOR_HID_TRACE") or None

    def _trace_report(self, direction: str, payload: bytes):
        trace_path = self._trace_path()
        if not trace_path:
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} {direction} {payload.hex()}\n"
        try:
            with open(trace_path, "a", encoding="ascii") as trace_file:
                trace_file.write(line)
        except OSError:
            logger.warning("Failed to append HID trace to %s", trace_path)

    def openSerial(self):
        if self.lcd_serial is not None:
            logger.debug("HID device already open on %s", self.com_port)
            return

        last_error = None
        for attempt in range(1, 11):
            if self.requested_com_port == "AUTO":
                candidate_port = None
                if self.com_port and Path(self.com_port).exists():
                    candidate_port = self.com_port
                    logger.debug("Trying previously known HID device: %s", candidate_port)
                else:
                    candidate_port = self.auto_detect_com_port()
                    if candidate_port:
                        logger.debug(f"Auto detected HID device: {candidate_port}")

                if not candidate_port:
                    last_error = FileNotFoundError("SmartMonitor hidraw device is not visible yet")
                    time.sleep(0.5)
                    continue

                self.com_port = candidate_port
            else:
                self.com_port = self.requested_com_port
                logger.debug(f"Static HID device: {self.com_port}")

            try:
                self.lcd_serial = os.open(self.com_port, os.O_RDWR | os.O_NONBLOCK)
                return
            except OSError as e:
                last_error = e
                self.lcd_serial = None
                time.sleep(0.5)

        logger.error(
            "Cannot open HID device automatically after waiting for re-enumeration: %s",
            last_error,
        )
        try:
            raise SystemExit(0)
        except SystemExit:
            raise

    def closeSerial(self):
        if self.lcd_serial is not None:
            try:
                os.close(self.lcd_serial)
            except OSError:
                pass
            self.lcd_serial = None

    def reopenSerial(self, wait_after_close: float = 1.0, flush_input: bool = True):
        self.closeSerial()
        time.sleep(wait_after_close)
        self.openSerial()
        if flush_input:
            self.serial_flush_input()

    def recoverSerial(self, attempts: int = 3, wait_after_close: float = 1.0, flush_input: bool = True):
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                self.reopenSerial(wait_after_close=wait_after_close, flush_input=flush_input)
                return
            except OSError as exc:
                last_error = exc
                logger.warning(
                    "HID recover attempt %d/%d failed while reopening %s: %s",
                    attempt,
                    attempts,
                    self.com_port,
                    exc,
                )
                time.sleep(wait_after_close)
        if last_error is not None:
            raise last_error

    def serial_write(self, data: bytes):
        assert self.lcd_serial is not None

        offset = 0
        while offset < len(data):
            payload = data[offset: offset + self.HID_REPORT_SIZE]
            report = bytes([0]) + payload.ljust(self.HID_REPORT_SIZE, b"\x00")
            os.write(self.lcd_serial, report)
            self._trace_report("TX", report)
            offset += len(payload)
            time.sleep(0.002)

    def write_hid_report(self, payload: bytes):
        if len(payload) > self.HID_REPORT_SIZE:
            raise ValueError(
                f"HID payload must fit in one report ({self.HID_REPORT_SIZE} bytes max, got {len(payload)})")
        with self._io_lock:
            if self.lcd_serial is None:
                self.openSerial()
            last_error = None
            for attempt in range(1, 4):
                try:
                    self.serial_write(payload)
                    return
                except OSError as exc:
                    last_error = exc
                    if attempt == 3:
                        break
                    logger.warning(
                        "HID write failed on attempt %d/3, recovering device before retry: %s",
                        attempt,
                        exc,
                    )
                    self.recoverSerial(attempts=3, wait_after_close=1.0)
            if last_error is not None:
                raise last_error

    def serial_read(self, size: int) -> bytes:
        assert self.lcd_serial is not None

        deadline = time.monotonic() + 1.0
        data = bytearray()

        while len(data) < size and time.monotonic() < deadline:
            timeout = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([self.lcd_serial], [], [], timeout)
            if not ready:
                break

            try:
                report = os.read(self.lcd_serial, self.HID_REPORT_SIZE + 1)
            except BlockingIOError:
                continue

            if not report:
                break

            # hidraw returns plain report data for unnumbered reports.
            # Some stacks may still expose a leading zero report id, so drop it defensively.
            if len(report) == self.HID_REPORT_SIZE + 1 and report[0] == 0:
                report = report[1:]

            self._trace_report("RX", report)
            data.extend(report)

        return bytes(data[:size])

    def serial_readall(self) -> bytes:
        chunks = []

        while True:
            ready, _, _ = select.select([self.lcd_serial], [], [], 0)
            if not ready:
                break

            try:
                report = os.read(self.lcd_serial, self.HID_REPORT_SIZE + 1)
            except BlockingIOError:
                break

            if not report:
                break

            if len(report) == self.HID_REPORT_SIZE + 1 and report[0] == 0:
                report = report[1:]

            self._trace_report("RX", report)
            chunks.append(report)

        return b"".join(chunks)

    @staticmethod
    def _crc16_xmodem(payload: bytes) -> int:
        crc = 0
        for byte in payload:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

    def read_hid_report(self, timeout: float = 1.0) -> bytes:
        with self._io_lock:
            if self.lcd_serial is None:
                self.openSerial()

            ready, _, _ = select.select([self.lcd_serial], [], [], timeout)
            if not ready:
                return b""

            report = os.read(self.lcd_serial, self.HID_REPORT_SIZE + 1)
            if not report:
                return b""

            if len(report) == self.HID_REPORT_SIZE + 1 and report[0] == 0:
                report = report[1:]

            self._trace_report("RX", report)
            return report

    def _expect_ack_report(self, timeout: float = 2.0) -> bytes:
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            report = self.read_hid_report(timeout=max(0.0, deadline - time.monotonic()))
            if not report:
                continue
            if report[0] == self.YMODEM_ACK:
                return report
            if report[0] == self.YMODEM_NAK:
                return report
            logger.debug("Ignoring non-ACK HID report during SmartMonitor upload: %s", report.hex())

        raise TimeoutError("Timed out waiting for ACK from SmartMonitor")

    @classmethod
    def _build_ymodem_frame(cls, block_type: int, block_number: int, payload: bytes) -> bytes:
        frame = bytes([block_type, block_number & 0xFF, 0xFF - (block_number & 0xFF)]) + payload
        crc = cls._crc16_xmodem(payload)
        return frame + crc.to_bytes(2, "big")

    def _send_ymodem_frame(self, frame: bytes, timeout: float = 2.0, max_retries: int = 8) -> bytes:
        last_report = b""
        for attempt in range(1, max_retries + 1):
            self.serial_write(frame)
            report = self._expect_ack_report(timeout=timeout)
            last_report = report
            if report and report[0] == self.YMODEM_ACK:
                return report
            if report and report[0] == self.YMODEM_NAK:
                logger.warning(
                    "SmartMonitor NAKed YMODEM frame on attempt %d/%d, resending",
                    attempt,
                    max_retries,
                )
                continue
        raise TimeoutError(f"SmartMonitor kept NAKing YMODEM frame after {max_retries} retries: {last_report.hex()}")

    def smartmonitor_send_reset(self, reconnect_delay: float = 2.5):
        self.write_hid_report(self.SMARTMONITOR_RESET_COMMAND)
        logger.debug("SmartMonitor reset command sent, waiting %.1f s", reconnect_delay)
        time.sleep(reconnect_delay)
        self.recoverSerial(attempts=5, wait_after_close=0.5)

    def smartmonitor_enter_ymodem(self, timeout: float = 2.0, attempts: int = 3) -> bytes:
        last_exc = None
        per_attempt_timeout = max(1.0, timeout / max(1, attempts))
        for attempt in range(1, attempts + 1):
            self.serial_flush_input()
            self.write_hid_report(self.SMARTMONITOR_YMODEM_COMMAND)
            try:
                return self._expect_ack_report(timeout=per_attempt_timeout)
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    logger.debug(
                        "No YMODEM ACK after command attempt %d/%d, retrying",
                        attempt,
                        attempts,
                    )
                    time.sleep(0.3)
        if last_exc is not None:
            raise last_exc
        raise TimeoutError("Timed out waiting for YMODEM entry ACK from SmartMonitor")

    def smartmonitor_upload_theme(self, theme_path: str, remote_name: str = "img.dat", send_reset: bool = True,
                                  ack_timeout: float = 2.0):
        if self.lcd_serial is None:
            self.openSerial()
        else:
            # hidraw descriptors can remain open while the endpoint is effectively dead.
            # Always force a clean reopen before entering the SmartMonitor upload/reset flow.
            self.recoverSerial(attempts=5, wait_after_close=0.5)

        ack_report = None
        last_exc = None
        reset_delays = [2.5, 3.5, 4.5] if send_reset else [0.0]
        for attempt_index, reset_delay in enumerate(reset_delays, start=1):
            try:
                if send_reset:
                    try:
                        self.smartmonitor_send_reset(reconnect_delay=reset_delay)
                    except OSError as exc:
                        logger.warning(
                            "SmartMonitor reset attempt %d/%d failed before upload, recovering device: %s",
                            attempt_index,
                            len(reset_delays),
                            exc,
                        )
                        self.recoverSerial(attempts=5, wait_after_close=1.0)
                else:
                    self.recoverSerial(attempts=3, wait_after_close=0.5)

                ack_report = self.smartmonitor_enter_ymodem(timeout=max(ack_timeout, 3.0), attempts=3)
                break
            except Exception as exc:
                last_exc = exc
                if attempt_index < len(reset_delays):
                    logger.warning(
                        "YMODEM entry failed on attempt %d/%d, retrying with another reset cycle: %s",
                        attempt_index,
                        len(reset_delays),
                        exc,
                    )
                    try:
                        self.recoverSerial(attempts=5, wait_after_close=1.0)
                    except OSError:
                        pass
                    continue
                raise last_exc

        if ack_report is None:
            raise last_exc or TimeoutError("SmartMonitor did not acknowledge YMODEM entry")
        logger.debug("SmartMonitor YMODEM ready: %s", ack_report.hex())

        with open(theme_path, "rb") as theme_file:
            theme_data = theme_file.read()

        header_payload = bytearray(128)
        header = f"{remote_name}\0{len(theme_data)}\0".encode("ascii")
        header_payload[:len(header)] = header
        self._send_ymodem_frame(
            self._build_ymodem_frame(self.YMODEM_SOH, 0, bytes(header_payload)),
            timeout=ack_timeout,
        )

        total_blocks = max(1, (len(theme_data) + 1023) // 1024)
        for block_index in range(total_blocks):
            start = block_index * 1024
            chunk = theme_data[start:start + 1024]
            chunk = chunk.ljust(1024, b"\x1A")
            block_number = (block_index + 1) & 0xFF

            self._send_ymodem_frame(
                self._build_ymodem_frame(self.YMODEM_STX, block_number, chunk),
                timeout=ack_timeout,
            )

            if block_index == 0 or (block_index + 1) == total_blocks or (block_index + 1) % 16 == 0:
                logger.info("SmartMonitor theme upload %d/%d blocks", block_index + 1, total_blocks)

        self.write_hid_report(bytes([self.YMODEM_EOT]))
        self._expect_ack_report(timeout=ack_timeout)

        self._send_ymodem_frame(
            self._build_ymodem_frame(self.YMODEM_SOH, 0, bytes(128)),
            timeout=ack_timeout,
        )
        logger.debug("SmartMonitor theme upload complete, waiting for HID interface to come back")
        self.recoverSerial(attempts=6, wait_after_close=1.0)

    def smartmonitor_send_raw_command(self, command: int, pairs: list[tuple[int, int]]):
        if not 0 <= command <= 0xFF:
            raise ValueError(f"Command must fit in one byte, got {command}")
        if len(pairs) > 20:
            raise ValueError(f"SmartMonitor packets support at most 20 pairs, got {len(pairs)}")

        payload = bytearray(self.HID_REPORT_SIZE)
        payload[0] = command & 0xFF
        payload[1] = len(pairs) & 0xFF

        offset = 2
        for tag, value in pairs:
            if not 0 <= tag <= 0xFF:
                raise ValueError(f"Tag must fit in one byte, got {tag}")
            if not 0 <= value <= 0xFFFF:
                raise ValueError(f"Value must fit in two bytes, got {value}")
            payload[offset] = tag & 0xFF
            payload[offset + 1:offset + 3] = value.to_bytes(2, "big")
            offset += 3

        self.write_hid_report(bytes(payload))

    def smartmonitor_send_datetime(self, when: Optional[datetime] = None):
        if when is None:
            when = datetime.now()

        payload = bytearray(self.HID_REPORT_SIZE)
        payload[0] = self.SMARTMONITOR_TIME_COMMAND
        payload[1] = 0x01
        payload[2] = 0x15
        payload[3] = when.year - 2000
        payload[4] = when.month
        payload[5] = when.day
        payload[6] = when.hour
        payload[7] = when.minute
        payload[8] = when.second
        payload[9] = when.isoweekday()
        payload[10] = 0x64
        self.write_hid_report(bytes(payload))

    def serial_flush_input(self):
        self.serial_readall()

    def WriteLine(self, line: bytes):
        try:
            self.serial_write(line)
        except OSError:
            logger.error(
                "OSError: Failed to send HID data to device. Closing and reopening hidraw path before retrying once.")
            self.closeSerial()
            time.sleep(1)
            self.openSerial()
            self.serial_write(line)

    def ReadData(self, readSize: int):
        try:
            return self.serial_read(readSize)
        except OSError:
            logger.error(
                "OSError: Failed to read HID data from device. Closing and reopening hidraw path before retrying once.")
            self.closeSerial()
            time.sleep(1)
            self.openSerial()
            return self.serial_read(readSize)
