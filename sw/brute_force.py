#!/usr/bin/env python3

# Refer to https://zkre.xyz/posts/indego_pin

import sys

from PyV4L2Camera.camera import Camera
from PyV4L2Camera.controls import ControlIDs
import numpy as np
from time import sleep
import csv
import readchar
from enum import IntEnum
from pyftdi.gpio import GpioSyncController
import os
import glob
import imagehash


class Target(IntEnum):
    Bosch_Indego = 0,
    Husqvarna = 1

target = Target.Bosch_Indego # TODO add cmd line arg

from enum import Enum
class Button(IntEnum):
    PowerEn = 3
    NextDigit = 0
    Increase = 2
    Fertig = 1

# Pins are active low
PIN_ON = False
PIN_OFF = True
# Power relay is active high
POWER_ON = True
POWER_OFF = False

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract

videodev = '/dev/video2'
ROI = (0, 0, 1280, 720)
#ROI2 = (0, 0, 1280, 720)
ROI = (480, 80, 900, 620)
#ROI = (280, 300, 900, 430)
#ROI2 = (300, 250, 900, 300)
#ROI_b = (374, 311, 980, 405)

pinlist = []
power = False
dockPower = False
camera = None
gpio = None
pin_state = 0xf7

def gpio_init():
    global gpio

    gpio = GpioSyncController()
    # All pins as output
    gpio.configure('ftdi:///1', 0xff)
    pin_state = 0xf7
    gpio.exchange(pin_state)

def set_pin(pin, on):
    global gpio
    global pin_state

    # Pins are active low:
    #   - if on, pull low
    #   - if off, pull high
    if (on):
        pin_state = pin_state | (1 << pin)
    else:
        pin_state = pin_state & ~(1 << pin)

    gpio.exchange(pin_state)


def toggle_pin(pin):
    set_pin(pin, PIN_ON);
    sleep(0.1)
    set_pin(pin, PIN_OFF);
    sleep(0.1)

# XXX: "and_ocr" suffix is from the original code. This script doesn't do OCR
# any longer but I was too lazy to rename the original variables. We now use image
# hashes.
def take_image_and_ocr(savename, do_ocr, ROI_, image2):
    camera_init()
    camera = Camera(videodev, 1280, 720)
    sleep(2)
    #global camera
    frame = camera.get_frame()
    image = Image.frombytes('RGB', (camera.width, camera.height), frame, 'raw', 'RGB')
    del frame
    camera.close()
    image = image.crop(ROI_)
    image.save(str(savename) + ".png")
    if (do_ocr):
        hash = imagehash.average_hash(image)
        hash2 = imagehash.average_hash(image2)
        return hash - hash2
    del image
    return None

def enter_number_bosch(num):
    print("Entering pin: ", num)
    digits = []
    digits.append(num // 1000)
    digits.append((num % 1000) // 100)
    digits.append((num % 100) // 10)
    digits.append((num % 10))

    for digit in digits:
        #print("Entering digit: ", digit)
        for step in range(digit):
            toggle_pin(Button.Increase)
            sleep(0.2)
        toggle_pin(Button.NextDigit) # jump to next digit
        sleep(0.2)

    toggle_pin(Button.Fertig)

def dictionary_init(startPIN) :
    global pinlist
    skipStartPIN = False
    if (startPIN == ''):
        folder_path = "."
        files_path = os.path.join(folder_path, '*.png')
        files = sorted(glob.iglob(files_path), key=os.path.getctime, reverse=True)
        skipStartPIN = True
        # if a e.g. 1234.png exists, then this is where we left off so resume from here
        #startPIN = os.path.basename(files[0]).split('.')[0]
        print(startPIN)

    with open('four-digit-pin-codes-sorted-by-frequency-withcount.csv', newline='') as csvfile:
        pins_w_probability = csv.reader(csvfile, delimiter=',')

        firstPinFound = (len(startPIN) == 0)
        for row in pins_w_probability:
            if (firstPinFound) :
                pinlist.append(int(row[0]))
            else :
                if (int(row[0]) == int(startPIN)):
                    firstPinFound = True
                    if (not skipStartPIN) :
                        pinlist.append(int(row[0]))
        print("Loaded %d PINS" % len(pinlist))
        if (len(pinlist) <= 1) :
            input("All entries tried.... Press enter to continue")

def camera_init():
    os.system("v4l2-ctl -d 2 -c auto_exposure=1")
    os.system("v4l2-ctl -d 2 -c brightness=40")
    os.system("v4l2-ctl -d 2 -c gamma=100")
    os.system("v4l2-ctl -d 2 -c contrast=95")
    os.system("v4l2-ctl -d 2 -c sharpness=5")
    os.system("v4l2-ctl -d 2 -c saturation=0")
    os.system("v4l2-ctl -d 2 -c backlight_compensation=0")

def power_cycle():
    print("Power cycling...")
    set_pin(Button.PowerEn, POWER_OFF)
    sleep(1)
    set_pin(Button.PowerEn, POWER_ON)
    sleep(15)
    print("Mower ready!")
    # Acknowledge error (alarm button triggered)
    toggle_pin(Button.Fertig)
    sleep(0.5)

def do_bruteforce():
    global camera
    global target
    pin_index = 0
    rebootCounter = 0
    power_cycle()


    while pin_index < len(pinlist):
        print(f"Trying pin {pinlist[pin_index]}")
        enter_number_bosch(pinlist[pin_index])
        # let focus stabilize before taking picture
        sleep(2)

        image_name = 'locked.png'
        if rebootCounter == 2:
            image_name = 'error.png'

        hamming_distance = take_image_and_ocr(pinlist[pin_index], True, ROI, Image.open(image_name))
        print(f"hamming distance: {hamming_distance}")

        if hamming_distance > 10:
            print(f"### FOUND: {pinlist[pin_index]}")
            break

        pin_index = pin_index + 1
        rebootCounter = rebootCounter + 1
        if (rebootCounter == 3) :
            rebootCounter = 0
            power_cycle()
            continue

        toggle_pin(Button.Fertig)
        sleep(0.5)

    print("Done, shutting down")
    set_pin(Button.PowerEn, POWER_OFF)

if __name__ == '__main__':
    try:
        if (len(sys.argv) == 1 or sys.argv[1] == "bruteforce"):
            gpio_init()
            startPin = ''
            if (len(sys.argv) == 3):
                startPin = sys.argv[2]
            dictionary_init(startPin)
            do_bruteforce()
        else:
            if (sys.argv[1] == 'take_image'):
                take_image_and_ocr("test", False, ROI)
            elif (sys.argv[1] == 'take_image_ocr'):
                hamming_distance = take_image_and_ocr("test", True, ROI, Image.open('locked.png'))
                print(f"hamming distance: {hamming_distance}")
            else:
                print("Usage:")
                print(" No arguments: start brute force")
                print(" bruteforce [start_pin]: start brute force from the pin passed in the 2nd arg")
                print(" take_image:  Take a test image and write it to test.png")
                print(" take_image_ocr:  Take a test image and write it to test.png and hash it")
    except Exception as e:
        set_pin(Button.PowerEn, POWER_OFF)
        raise e
