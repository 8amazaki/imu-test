import os, sys, io
import time
import math
import M5
from M5 import *
from hardware import *

# ===== basic config =====
BG = 0x000000
FG = 0xFFFFFF
CENTER_X = 64
CENTER_Y = 64
RING_R = 26
DOT_R = 4

last_ms = 0
last_dx = 0
last_dy = 0

# calibration / test state
start_ms = 0
cal_count = 0
base_acc = [0.0, 0.0, 0.0]
base_gyro = [0.0, 0.0, 0.0]
static_ok = False
acc_move_ok = False
gyro_move_ok = False

# UI labels
label_title = None
label_status = None
label_acc = None
label_gyro = None
label_hint = None


def _get_imu_obj():
    if "Imu" in globals():
        return Imu
    if "IMU" in globals():
        return IMU
    return None


def _read_acc_gyro():
    imu = _get_imu_obj()
    if imu is None:
        return None, None

    acc = None
    gyro = None

    if hasattr(imu, "getAccel"):
        acc = imu.getAccel()
    elif hasattr(imu, "acceleration"):
        acc = imu.acceleration()

    if hasattr(imu, "getGyro"):
        gyro = imu.getGyro()
    elif hasattr(imu, "gyro"):
        gyro = imu.gyro()

    if acc is not None and len(acc) >= 3:
        acc = (float(acc[0]), float(acc[1]), float(acc[2]))
    else:
        acc = None

    if gyro is not None and len(gyro) >= 3:
        gyro = (float(gyro[0]), float(gyro[1]), float(gyro[2]))
    else:
        gyro = None

    return acc, gyro


def _hline(x, y, w, color):
    try:
        M5.Lcd.fillRect(x, y, w, 1, color)
    except Exception:
        M5.Lcd.drawLine(x, y, x + w - 1, y, color)


def _vline(x, y, h, color):
    try:
        M5.Lcd.fillRect(x, y, 1, h, color)
    except Exception:
        M5.Lcd.drawLine(x, y, x, y + h - 1, color)


def _draw_tilt_base():
    M5.Lcd.drawCircle(CENTER_X, CENTER_Y, RING_R, 0x666666)
    _hline(CENTER_X - RING_R, CENTER_Y, RING_R * 2, 0x333333)
    _vline(CENTER_X, CENTER_Y - RING_R, RING_R * 2, 0x333333)
    M5.Lcd.fillCircle(CENTER_X, CENTER_Y, DOT_R, FG)


def _draw_tilt_dot(ax, ay):
    global last_dx, last_dy

    M5.Lcd.fillCircle(CENTER_X + last_dx, CENTER_Y + last_dy, DOT_R, BG)

    dx = int(max(-1.0, min(1.0, ax)) * (RING_R - DOT_R - 1))
    dy = int(max(-1.0, min(1.0, ay)) * (RING_R - DOT_R - 1))

    d = math.sqrt(dx * dx + dy * dy)
    lim = RING_R - DOT_R - 1
    if d > lim and d > 0:
        s = lim / d
        dx = int(dx * s)
        dy = int(dy * s)

    sy = -dy
    M5.Lcd.fillCircle(CENTER_X + dx, CENTER_Y + sy, DOT_R, FG)

    last_dx = dx
    last_dy = sy


def _reset_test():
    global start_ms, cal_count, base_acc, base_gyro
    global static_ok, acc_move_ok, gyro_move_ok
    global last_dx, last_dy

    start_ms = time.ticks_ms()
    cal_count = 0
    base_acc = [0.0, 0.0, 0.0]
    base_gyro = [0.0, 0.0, 0.0]
    static_ok = False
    acc_move_ok = False
    gyro_move_ok = False
    last_dx = 0
    last_dy = 0

    Widgets.fillScreen(BG)
    _draw_tilt_base()


def setup():
    global label_title, label_status, label_acc, label_gyro, label_hint

    M5.begin()
    Widgets.fillScreen(BG)
    Widgets.setRotation(0)

    label_title = Widgets.Label("6-AXIS CHECK", 4, 4, 1.0, 0x00FFCC, BG, Widgets.FONTS.DejaVu12)
    label_status = Widgets.Label("S:NG A:NG G:NG", 4, 20, 1.0, 0xFFAA00, BG, Widgets.FONTS.DejaVu12)
    label_acc = Widgets.Label("ACC: ---", 4, 92, 1.0, FG, BG, Widgets.FONTS.DejaVu12)
    label_gyro = Widgets.Label("GYR: ---", 4, 106, 1.0, FG, BG, Widgets.FONTS.DejaVu12)
    label_hint = Widgets.Label("BtnA: RESET", 4, 118, 1.0, 0xAAAAAA, BG, Widgets.FONTS.DejaVu12)

    _draw_tilt_base()
    _reset_test()


def loop():
    global last_ms, cal_count, static_ok, acc_move_ok, gyro_move_ok
    global base_acc, base_gyro

    M5.update()

    try:
        if BtnA.wasPressed():
            _reset_test()
    except Exception:
        pass

    now = time.ticks_ms()
    if time.ticks_diff(now, last_ms) < 100:
        return
    last_ms = now

    acc, gyro = _read_acc_gyro()
    if acc is None or gyro is None:
        label_status.setText("IMU API ERROR")
        label_status.setColor(0xFF3333, BG)
        label_acc.setText("ACC: N/A")
        label_gyro.setText("GYR: N/A")
        return

    _draw_tilt_dot(acc[0], acc[1])

    if time.ticks_diff(now, start_ms) < 1000:
        cal_count += 1
        for i in range(3):
            base_acc[i] += acc[i]
            base_gyro[i] += gyro[i]
        label_status.setText("CALIBRATING...")
        label_status.setColor(0x33CCFF, BG)
    else:
        if cal_count > 0:
            for i in range(3):
                base_acc[i] /= cal_count
                base_gyro[i] /= cal_count
            cal_count = 0

        acc_norm = math.sqrt(acc[0] * acc[0] + acc[1] * acc[1] + acc[2] * acc[2])
        gyro_norm = math.sqrt(gyro[0] * gyro[0] + gyro[1] * gyro[1] + gyro[2] * gyro[2])

        if (0.80 <= acc_norm <= 1.20) and (gyro_norm < 8.0):
            static_ok = True

        if (abs(acc[0] - base_acc[0]) > 0.25 or
            abs(acc[1] - base_acc[1]) > 0.25 or
            abs(acc[2] - base_acc[2]) > 0.25):
            acc_move_ok = True

        if (abs(gyro[0] - base_gyro[0]) > 20.0 or
            abs(gyro[1] - base_gyro[1]) > 20.0 or
            abs(gyro[2] - base_gyro[2]) > 20.0):
            gyro_move_ok = True

        s = "OK" if static_ok else "NG"
        a = "OK" if acc_move_ok else "NG"
        g = "OK" if gyro_move_ok else "NG"
        label_status.setText("S:{} A:{} G:{}".format(s, a, g))
        if static_ok and acc_move_ok and gyro_move_ok:
            label_status.setColor(0x33CC00, BG)
        else:
            label_status.setColor(0xFFAA00, BG)

    label_acc.setText("ACC:{:+.2f},{:+.2f},{:+.2f}".format(acc[0], acc[1], acc[2]))
    label_gyro.setText("GYR:{:+.1f},{:+.1f},{:+.1f}".format(gyro[0], gyro[1], gyro[2]))


if __name__ == "__main__":
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg
            print_error_msg(e)
        except Exception:
            print("Error:", e)
