import cv2
import numpy as np
import time
import os
import argparse
from datetime import datetime

CLIP_DIR = '/home/orange/gym/videos/'
RECORD_SECONDS = 30
CAMERA_INDEX = 0  # Change if your USB camera is not at index 0

# Ensure the clips directory exists
os.makedirs(CLIP_DIR, exist_ok=True)

def detect_motion(prev_frame, curr_frame, min_area=5000):
    # Convert frames to grayscale
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
    # Blur to reduce noise
    prev_blur = cv2.GaussianBlur(prev_gray, (21, 21), 0)
    curr_blur = cv2.GaussianBlur(curr_gray, (21, 21), 0)
    # Compute absolute difference
    frame_delta = cv2.absdiff(prev_blur, curr_blur)
    thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
    # Dilate the thresholded image to fill in holes
    thresh = cv2.dilate(thresh, None, iterations=2)
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        if cv2.contourArea(contour) > min_area:
            return True
    return False

def record_clip(cap, fps, frame_size, show_preview=False):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(CLIP_DIR, f'clip_{timestamp}.mp4')
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, frame_size)
    print(f'Recording started: {filename}')
    start_time = time.time()
    while (time.time() - start_time) < RECORD_SECONDS:
        ret, frame = cap.read()
        if not ret:
            print('Error: Failed to read frame during recording.')
            break
        out.write(frame)
        if show_preview:
            cv2.imshow('Recording...', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print('Recording stopped by user.')
                break
    out.release()
    print(f'Recording saved: {filename}')

def main():
    parser = argparse.ArgumentParser(description='Motion detection and recording script')
    parser.add_argument('--show_preview', type=str, default='false', 
                       help='Show video preview windows (true/false)')
    args = parser.parse_args()
    
    # Convert string argument to boolean
    show_preview = args.show_preview.lower() == 'true'
    
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print('Error: Could not open camera.')
        return
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps is None or fps < 1:
        fps = 15  # fallback
    else:
        fps = int(fps)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_size = (frame_width, frame_height)
    
    if show_preview:
        print('Watching for motion with preview. Press Ctrl+C to exit.')
    else:
        print('Watching for motion (no preview). Press Ctrl+C to exit.')
    
    ret, prev_frame = cap.read()
    if not ret:
        print('Error: Could not read from camera.')
        cap.release()
        return
    try:
        while True:
            ret, curr_frame = cap.read()
            if not ret:
                print('Error: Could not read from camera.')
                break
            motion = detect_motion(prev_frame, curr_frame)
            if show_preview:
                cv2.imshow('Camera Feed', curr_frame)
            if motion:
                print('Motion detected! Recording...')
                record_clip(cap, fps, frame_size, show_preview)
                # After recording, grab a fresh frame for motion detection
                ret, prev_frame = cap.read()
                if not ret:
                    break
                continue
            prev_frame = curr_frame
            if show_preview and (cv2.waitKey(1) & 0xFF == ord('q')):
                print('Exiting.')
                break
    except KeyboardInterrupt:
        print('Interrupted by user.')
    cap.release()
    if show_preview:
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main() 