from ultralytics import YOLO
import cv2, serial, time, threading, torch
import numpy as np


# ===== MAIN CONFIG (change your variables here...) =====
ARDUINO_PORT = "COM16" # - will change on different usb ports and computers
BAUD_RATE = 9600
CAMERA_INDICES = [0, 1, 2, 3] # number of cameras used
DETECT_CLASSES = ["car", "truck", "bus", "motorbike", "person", "toy-cars"]
YOLO_MODEL = "best.pt" # (Should be your own Database link... It will be a local file)
TOTAL_CYCLE_TIME = 20   # seconds per full rotation (will be distributed across all intesections)
START_DELAY_SECONDS = 1
road1 = CAMERA_INDICES[0]
road2 = CAMERA_INDICES[1]
road3 = CAMERA_INDICES[2]
road4 = CAMERA_INDICES[3]


model = YOLO(YOLO_MODEL)
print("✅ YOLO model created — device:", "GPU" if torch.cuda.is_available() else "CPU")



# warmup the model
model_lock = threading.Lock()
def warmup_model():
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    with model_lock:
        try:
            _ = model(dummy, verbose=False)
            print("⚡ Model warmup OK")
        except Exception as e:
            print("⚠️ Model warmup error:", e)
warmup_model()




# arduino (change if you are using a differennt board)
try:
    arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"✅ Connected to Arduino on {ARDUINO_PORT}")
except Exception as e:
    print(f"⚠️ Arduino not connected: {e}")
    arduino = None




# detect how many cameras present (can use as many as needed)
valid_cams = []
for idx in CAMERA_INDICES:
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if cap.isOpened():
        valid_cams.append(idx)
        cap.release()
print("✅ Active cameras:", valid_cams)
if not valid_cams:
    print("❌ No cameras detected — exiting.")
    exit()



counts = {}
running = True
start_event = threading.Event()
camera_ready = {}
camera_ready_lock = threading.Lock()




def camera_loop(cam_id):
    global counts, running
    cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)    # change according to what res you want
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)    # change according to what res you want
    if not cap.isOpened():
        print(f"❌ Camera {cam_id} not opened")
        return




    with camera_ready_lock:
        camera_ready[cam_id] = True




    win = f"Camera {cam_id}"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)




    while running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue



        if not start_event.is_set():
            preview = frame.copy()
            cv2.putText(preview, "Waiting to start detection...", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
            cv2.imshow(win, preview)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                break
            continue



        with model_lock:
            results = model(frame, verbose=False)




        count = sum(1 for box in results[0].boxes
                    if model.names[int(box.cls[0])].lower() in DETECT_CLASSES)
        counts[cam_id] = count




        annotated = results[0].plot()
        cv2.putText(annotated, f"Count: {count}", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
        cv2.putText(annotated, f"Camera {cam_id}", (20,80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)




        cv2.imshow(win, annotated)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            running = False
            break




    cap.release()
    try: cv2.destroyWindow(win)
    except: pass




def send_arduino_loop():
    global counts, running
    start_event.wait()
    while running:
        if counts:
            active_cams = [road1, road2, road3, road4]
            active_cams = [c for c in active_cams if c in counts]


            cam_counts = [counts[c] for c in active_cams]




            total_counts = sum(cam_counts)
            if total_counts == 0:
                # fallback
                per_sec = int(TOTAL_CYCLE_TIME / max(1, len(cam_counts)))
                green_secs = [per_sec]*len(cam_counts)
            else:
                green_secs = [max(1, int(TOTAL_CYCLE_TIME * c / total_counts)) for c in cam_counts]




            # convert to milliseconds as glitches with seconds in serial ports
            green_ms = [int(s * 1000) for s in green_secs]




            # build send string as milliseconds so Arduino uses these units, tried with seconds and failed
            data_str = ",".join(str(ms) for ms in green_ms) + f";{len(green_ms)}\n"




            if arduino:
                try:
                    arduino.write(data_str.encode())
                except Exception as e:
                    print("⚠️ Arduino write error:", e)




            print("📊 Sent to Arduino (ms):", data_str.strip(), "  (sec)", green_secs)




            # sleep for the longest green time (convert ms -> sec) - ensure that you change this according to your board
            wait_seconds = max(green_ms) / 1000.0
            # ensure at least 1 second sleep to avoid extremely tight loops - change due to glitch
            time.sleep(max(1.0, wait_seconds))
        else:
            time.sleep(0.1)




# start camera threads
threads = []
for cam in valid_cams:
    with camera_ready_lock:
        camera_ready[cam] = False
    t = threading.Thread(target=camera_loop, args=(cam,))
    t.start()
    threads.append(t)




# wait for all cameras to be ready (wait to ensure smooth start at same time)
print("⏳ Waiting for camera threads to open...")
while True:
    with camera_ready_lock:
        all_ready = all(camera_ready.get(c, False) for c in valid_cams)
    if all_ready:
        break
    time.sleep(0.05)




# start delay countdown (counted in terminal)
print(f"✅ All cameras opened. Starting countdown {START_DELAY_SECONDS}s before detection/sending.")
for i in range(START_DELAY_SECONDS, 0, -1):
    print(f"⏳ Starting detection in {i}s", end="\r")
    time.sleep(1)
print("\n✅ Starting detection & Arduino updates now.")
start_event.set()



if arduino:
    t2 = threading.Thread(target=send_arduino_loop)
    t2.start()
    threads.append(t2)

for t in threads:
    t.join()

if arduino:
    arduino.close()
cv2.destroyAllWindows()
print("✅ Closed cleanly") # - close message, change acc.
