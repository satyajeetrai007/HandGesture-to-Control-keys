import cv2
from flask import Flask, Response, render_template
import cvzone
from cvzone.HandTrackingModule import HandDetector
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import datetime
import time
import numpy as np
import pyautogui
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------
# Audio Setup with Pycaw
# ---------------------------
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume_control = cast(interface, POINTER(IAudioEndpointVolume))

# Get the current volume level (scalar: 0.0 to 1.0)
current_volume = volume_control.GetMasterVolumeLevelScalar()
logger.info(f"Initial Volume: {int(current_volume * 100)}%")

# ---------------------------
# Hand Detector Setup
# ---------------------------
detector = HandDetector(detectionCon=0.6, maxHands=2)

# ---------------------------
# Gesture State Variables
# ---------------------------
last_screenshot_time_right = 0
screenshot_cooldown_right = 5  # seconds

last_space_time_left = 0
space_cooldown_left = 1  # seconds

last_volume_change_time_right = 0
volume_cooldown_right = 0.2  # seconds

# ---------------------------
# Flask Routes
# ---------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_frames():
    global current_volume
    global last_screenshot_time_right, last_space_time_left
    global last_volume_change_time_right

    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)  # Width
    cap.set(4, 720)   # Height

    while True:
        success, img = cap.read()
        if not success:
            logger.error("Failed to read from webcam.")
            break

        img = cv2.flip(img, 1)  # Flip the image horizontally for a mirror view

        # Detect hands
        hands, img = detector.findHands(img, flipType=False)  # flipType=False to get correct hand type

        if hands:
            for hand in hands:
                hand_type = hand['type']  # 'Left' or 'Right'
                lm_list = hand['lmList']  # List of 21 landmarks
                fingers = detector.fingersUp(hand)  # List of finger states

                # Draw hand type on the image
                cvzone.putTextRect(img, f'{hand_type} Hand', (hand['bbox'][0], hand['bbox'][1] - 20),
                                   scale=1, thickness=2, colorR=(255, 0, 255))

                if hand_type == 'Right':
                    # ---------------------------
                    # Volume Control and Screenshot (Right Hand)
                    # ---------------------------
                    current_time = time.time()

                    # Volume Increase: Only Thumb is up
                    if fingers == [1, 0, 0, 0, 0]:
                        if current_time - last_volume_change_time_right > volume_cooldown_right:
                            logger.info("Right Hand: Thumb is up - Increasing volume")
                            current_volume = min(current_volume + 0.01, 1.0)
                            volume_control.SetMasterVolumeLevelScalar(current_volume, None)
                            last_volume_change_time_right = current_time
                            cvzone.putTextRect(img, f'Volume: {int(current_volume * 100)}%', (10, 60),
                                               scale=1, thickness=2, colorR=(0, 255, 0))

                    # Volume Decrease: Only Little Finger is up
                    elif fingers == [0, 0, 0, 0, 1]:
                        if current_time - last_volume_change_time_right > volume_cooldown_right:
                            logger.info("Right Hand: Little finger is up - Decreasing volume")
                            current_volume = max(current_volume - 0.01, 0.0)
                            volume_control.SetMasterVolumeLevelScalar(current_volume, None)
                            last_volume_change_time_right = current_time
                            cvzone.putTextRect(img, f'Volume: {int(current_volume * 100)}%', (10, 60),
                                               scale=1, thickness=2, colorR=(0, 255, 0))

                    # Screenshot: Victory Pose (Index and Middle fingers up)
                    elif fingers == [0, 1, 1, 0, 0]:
                        if current_time - last_screenshot_time_right > screenshot_cooldown_right:
                            logger.info("Right Hand: Victory Pose Detected - Taking Screenshot")
                            take_screenshot(img)
                            last_screenshot_time_right = current_time
                            cvzone.putTextRect(img, 'Screenshot Taken!', (10, 60),
                                               scale=1, thickness=2, colorR=(0, 255, 0))

                elif hand_type == 'Left':
                    # ---------------------------
                    # Spacebar Press (Left Hand)
                    # ---------------------------
                    current_time = time.time()

                    # Palm Open: All fingers are up
                    if fingers == [1, 1, 1, 1, 1]:
                        if current_time - last_space_time_left > space_cooldown_left:
                            logger.info("Left Hand: Palm Open Detected - Pressing Spacebar")
                            pyautogui.press('space')
                            last_space_time_left = current_time
                            cvzone.putTextRect(img, 'Space Pressed!', (10, 60),
                                               scale=1, thickness=2, colorR=(255, 0, 0))

        # Encode the frame in JPEG format
        ret, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()

        # Yield the output frame in byte format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

# ---------------------------
# Helper Functions
# ---------------------------

def take_screenshot(img):
    # Create a filename with the current date and time
    filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    cv2.imwrite(filename, img)  # Save the frame as a screenshot
    logger.info(f"Screenshot taken: {filename}")

# ---------------------------
# Run Flask App
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
