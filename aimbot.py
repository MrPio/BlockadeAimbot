import os
import threading
import time
from types import NoneType

import cv2
import keyboard
import numpy
import numpy as np
import pyautogui
import win32api
import win32con
import winput
from PIL import Image, ImageChops
from pygame import mixer

pyautogui.PAUSE = 0
pyautogui.MINIMUM_DURATION = 0
SCALE_FACTOR_X = 1.75 * 2 *0.594
SCALE_FACTOR_Y = 1.775 * 1.7 *0.594
EXPONENTIAL_FACTOR = 0.69

mixer.init()
beeps = [
    mixer.Sound('raw/beep_in_01.wav'),
    mixer.Sound('raw/beep_in_02.wav'),
    mixer.Sound('raw/beep_out_01.wav')
]
[beep.set_volume(0.01) for beep in beeps]


class EnemyDetector:
    def __init__(self) -> None:
        screen_size = pyautogui.size()
        self.screen_region = (
            int(screen_size[0] * 0.3),
            int(screen_size[1] * 0.3),
            int(screen_size[0] * 0.4),
            int(screen_size[1] * 0.4),
        )

    def detect(self, img: np.array = None) -> tuple[bool, int, int]:
        face = (np.array([80, 160, 160]), np.array([102, 240, 240]))
        blue = (np.array([0, 100, 8]), np.array([40, 250, 160]))
        zorro_blue = (np.array([0, 120, 76]), np.array([11, 156, 90]))
        red = (np.array([110, 200, 135]), np.array([170, 250, 160]))
        green = (np.array([40, 170, 90]), np.array([80, 250, 160]))

        screenshot = numpy.array(pyautogui.screenshot(region=self.screen_region)) if img is None else img
        # cv2.imshow('screenshot', screenshot[:, :, ::-1])
        # cv2.waitKey(1000)
        hsv = cv2.cvtColor(numpy.array(screenshot), cv2.COLOR_BGR2HSV)
        for color in [zorro_blue]:
            mask = cv2.inRange(hsv, color[0], color[1])
            # cv2.imshow('screenshot', mask)
            # cv2.waitKey(2000)
            # cv2.imwrite("target.png", mask)
            contoursOrange, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contoursOrange:
                if cv2.contourArea(c) <= 23:
                    continue
                print(cv2.contourArea(c))
                x, y, h, w = cv2.boundingRect(c)
                pos = (int(x + h / 2 - screenshot.shape[1] / 2), int(y + w / 2 - screenshot.shape[0] / 2))
                print('detected enemy at: ', pos)
                return True, pos[0], pos[1]
        return False, 0, 0


class ScreenGrabber:
    def __init__(self) -> None:
        self.old_screen: Image = None
        self.screen: Image = None
        self.screen_w, self.screen_h = pyautogui.size()
        self.corner_x, self.corner_y = (int(self.screen_w * 0.425), int(self.screen_h * 0.425))
        self.region_size = (int(self.screen_w * 0.15), int(self.screen_h * 0.15))
        self.tracking_region = (
            int(self.screen_w * 0.765),
            int(self.screen_h * 0.1),
            int(self.screen_w * 0.2),
            int(self.screen_w * 0.2),
        )
        self.tracking_image: Image = None

    def take_screen(self) -> None:
        region = (
            self.corner_x,
            self.corner_y,
            self.region_size[0],
            self.region_size[1],
        )
        self.old_screen, self.screen = (self.screen, pyautogui.screenshot(region=region))

    def show_screens(self) -> None:
        if self.old_screen:
            self.old_screen.show()
        self.screen.show()

    def find_movement(self) -> tuple[bool, int, int]:
        if self.old_screen is None:
            return False, 0, 0
        diff_image = ImageChops.difference(self.old_screen, self.screen).convert('L')
        new_pixels = [(x, y) for x in range(diff_image.width) for y in range(diff_image.height) if
                      abs(diff_image.getpixel((x, y))) > 40]
        if new_pixels and len(new_pixels) > 20 ** 2:
            center_x = sum(x for x, _ in new_pixels) // len(new_pixels)
            center_y = sum(y for _, y in new_pixels) // len(new_pixels)
            diff_image.save(f'{time.time()}.png')
            return True, center_x + self.corner_x - self.screen_w // 2, center_y + self.corner_y - self.screen_h // 2
        else:
            return False, -1, -1

    def perform_tracking(self):
        global SCALE_FACTOR_X, SCALE_FACTOR_Y
        SCALE_FACTOR_X, SCALE_FACTOR_Y = (1, 1)
        beeps[1].play()
        self.tracking_image = pyautogui.screenshot(region=self.tracking_region)
        self.tracking_image.save('tracking.png')
        MouseManager.move(self.screen_w // 8, -self.screen_h // 8)
        pyautogui.sleep(0.75)
        beeps[1].play()
        track_new_pos = pyautogui.locateOnScreen('tracking.png', grayscale=True, confidence=0.5)
        if type(track_new_pos) is NoneType:
            beeps[2].play()
        else:
            beeps[0].play()
            pyautogui.screenshot(
                region=(track_new_pos.left, track_new_pos.top, track_new_pos.width, track_new_pos.height)) \
                .save('tracking2.png')
            new_pos = (track_new_pos.left + int(track_new_pos.width / 2),
                       track_new_pos.top + int(track_new_pos.height / 2))
            old_pos = (self.tracking_region[0] + self.tracking_region[2] // 2,
                       self.tracking_region[1] + self.tracking_region[3] // 2)
            SCALE_FACTOR_X = (self.screen_w // 8) / (old_pos[0] - new_pos[0])
            SCALE_FACTOR_Y = (self.screen_h // 8) / (-(old_pos[1] - new_pos[1]))
            print(self.screen_w, self.screen_h)
            print(
                f'track moved from {old_pos} to {new_pos}, so the new scale factors are ({SCALE_FACTOR_X}, {SCALE_FACTOR_Y})')


class MouseManager:
    STEP = 100
    STEP_DURATION = 0.005

    @staticmethod
    def move(x: int, y: int):
        print(x, y)
        print(x ** EXPONENTIAL_FACTOR)
        new_x = int(abs(x) ** EXPONENTIAL_FACTOR) * (-1 if x < 0 else 1)
        new_y = int(abs(y) ** EXPONENTIAL_FACTOR) * (-1 if y < 0 else 1)
        distance = (new_x ** 2 + new_y ** 2) ** 0.5
        steps = int(distance / MouseManager.STEP) + 1
        print('steps=', steps)
        step = (int(new_x * SCALE_FACTOR_X / steps), int(new_y * SCALE_FACTOR_Y / steps))
        print('step=', step)
        for i in range(steps):
            # random_x, random_y = (random.randrange(-20, 20), random.randrange(-20, 20)) if i < steps else (0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, step[0], step[1], 0, 0)

            pyautogui.sleep(MouseManager.STEP_DURATION)

    @staticmethod
    def click(duration=1.0):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        pyautogui.sleep(duration)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)


def aimbot():
    print('starting aimbot...')
    beeps[1].play()
    pyautogui.sleep(1)
    pyautogui.moveTo(screen_grabber.screen_w // 2, screen_grabber.screen_h // 2)
    screen_grabber.take_screen()

    for i in range(20):
        pyautogui.sleep(0.04)
        beeps[0].play()
        screen_grabber.take_screen()
        print('taking screen')
        found, x, y = screen_grabber.find_movement()
        if found:
            print(f'moving for {(x, y)}')
            beeps[2].play()
            MouseManager.move(x, y)
            MouseManager.click(0.45)
            pyautogui.sleep(0.04)
            screen_grabber.take_screen()


def aimbot2():
    print('starting aimbot...')
    pyautogui.sleep(1)
    pyautogui.moveTo(screen_grabber.screen_w // 2, screen_grabber.screen_h // 2)
    screen_grabber.take_screen()

    for i in range(500):
        beeps[0].play()
        found, x, y = enemy_detector.detect()
        if found:
            print(f'moving for {(x, y)}')
            beeps[2].play()
            MouseManager.move(x, y)
            threading.Thread(target=lambda: MouseManager.click(0.2)).start()
        else:
            pyautogui.sleep(0.005)


def test():
    for e in range(1, 4):
        enemy_detector.detect(cv2.imread(f'test_screens/test_{e}.png')[:, :, ::-1])


def handle_mouse(mouse_event: winput.MouseEvent):
    print(mouse_event.action)


screen_grabber = ScreenGrabber()
enemy_detector = EnemyDetector()
keyboard.add_hotkey('shift+alt+p', aimbot)
keyboard.add_hotkey('shift+alt+o', aimbot2)
keyboard.add_hotkey('shift+alt+y', test)
keyboard.add_hotkey('shift+alt+u', lambda: screen_grabber.perform_tracking())
keyboard.add_hotkey('shift+alt+q', lambda: os._exit(0))
print('waiting for key...')
keyboard.wait()
