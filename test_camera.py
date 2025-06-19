import cv2
import time
from datetime import datetime

def record_video():
    # Initialize the camera
    cap = cv2.VideoCapture(0)
    
    # Check if camera opened successfully
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    # Get camera properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cam_fps = cap.get(cv2.CAP_PROP_FPS)
    if cam_fps is None or cam_fps <= 1:
        fps = 15  # fallback if camera doesn't report FPS
    else:
        fps = int(cam_fps)
    print(f"Using FPS: {fps}")
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"video_{timestamp}.mp4"
    
    # Create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (frame_width, frame_height))
    
    print("Recording started... Press 'q' to stop early.")
    start_time = time.time()
    frame_count = 0
    
    while (time.time() - start_time) < 10:
        ret, frame = cap.read()
        if not ret:
            print("Error: Can't receive frame")
            break
        out.write(frame)
        frame_count += 1
        cv2.imshow('Recording...', frame)
        # Wait for the correct time and check for 'q' key
        if cv2.waitKey(int(1000 / fps)) & 0xFF == ord('q'):
            print("Recording stopped by user.")
            break
        elapsed = time.time() - start_time
        print(f"Recording... {elapsed:.1f} seconds", end='\r')
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"\nRecording completed. Video saved as: {filename}")
    print(f"Total frames recorded: {frame_count}")

if __name__ == "__main__":
    record_video()
