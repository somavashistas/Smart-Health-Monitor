import cv2
import mediapipe as mp
import math
import time
import pyttsx3
from collections import deque
from .base_camera import VideoCamera
import threading


# =================== VOICE ===================
try:
    engine = pyttsx3.init()
    engine.setProperty("rate", 165)
except:
    engine = None
    print("⚠️ TTS engine failed to initialize")

def speak(text):
    if engine:
        threading.Thread(
            target=lambda: (engine.say(text), engine.runAndWait()),
            daemon=True
        ).start()

# =================== HELPERS ===================
def dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def EAR(eye):
    A = dist(eye[1], eye[5])
    B = dist(eye[2], eye[4])
    C = dist(eye[0], eye[3])
    return (A + B) / (2.0 * C) if C != 0 else 0

def head_tilt_angle(left_eye, right_eye):
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    return abs(math.degrees(math.atan2(dy, dx)))

# =================== CAMERA CLASS ===================
class WeekdayCamera(VideoCamera):
    def __init__(self):
        super().__init__()
        print("💼 WeekdayCamera initialized!")

        self.mp_face = mp.solutions.face_mesh
        self.mp_pose = mp.solutions.pose

        self.face_mesh = self.mp_face.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        # self.face_mesh = self.mp_face.FaceMesh(
        # static_image_mode=False,
        # max_num_faces=1,
        # min_detection_confidence=0.7
        # )

        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        self.LEFT_EYE = [33, 159, 158, 133, 153, 145]
        self.RIGHT_EYE = [362, 386, 385, 263, 380, 374]

        # -------- Blink / Drowsy --------
        self.EAR_THRESHOLD = 0.23
        self.EYE_CLOSED_FRAMES = 3
        self.DROWSY_TIME = 10

        self.frames_closed = 0
        self.blink_count = 0
        self.ear_buffer = deque(maxlen=5)
        self.drowsy_start = None
        self.drowsy_alert = False

        self.blink_times = deque()
        self.BLINK_RATE_THRESHOLD = 15
        self.BLINK_ALERT_DELAY = 120
        self.low_blink_start = None
        self.blink_rate_alert = False

        # -------- Distance / Posture --------
        self.DISTANCE_CLOSE_FACTOR = 0.65
        self.DISTANCE_CONFIRM_TIME = 2.0
        self.HEAD_TILT_IGNORE = 8
        self.close_start = None

        self.BASELINE_TIME = 3
        self.baseline_start = time.time()
        self.baseline_ready = False

        self.base_shoulder_nose = 0
        self.base_shoulder_diff = 0
        self.base_eye_dist = 0
        self.base_shoulder_mid = 0
        self.samples = 0

        self.bad_posture_start = None
        self.POSTURE_SOUND_DELAY = 120
        self.posture_alert = False
        
        # -------- Session Tracking --------
        self.total_bad_posture_time = 0
        self.last_bad_posture_update = None
        self.session_blink_count = 0  # Blinks for current session only

    def release(self):
        """Cleanup MediaPipe and camera"""
        try:
            if hasattr(self, 'face_mesh') and self.face_mesh:
                self.face_mesh.close()
            if hasattr(self, 'pose') and self.pose:
                self.pose.close()
            print("🧹 WeekdayCamera MediaPipe cleaned up")
        except Exception as e:
            print(f"Warning during MediaPipe cleanup: {e}")
        
        # Call parent release
        super().release()

    def get_frame(self):
        frame = self.get_raw_frame()
        if frame is None:
            return None

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_res = None
        pose_res = None
        
        try:
            face_res = self.face_mesh.process(rgb)
            pose_res = self.pose.process(rgb)
        except Exception as e:
            print(f"⚠️ MediaPipe processing error: {e}")
            ret, jpeg = cv2.imencode(".jpg", frame)
            return jpeg.tobytes() if ret else None

        status = "GOOD POSTURE"
        color = (0, 255, 0)
        bad = False

        # ================= FACE / BLINK =================
        if face_res and face_res.multi_face_landmarks:
            lm = face_res.multi_face_landmarks[0].landmark
            left_eye = [(int(lm[i].x*w), int(lm[i].y*h)) for i in self.LEFT_EYE]
            right_eye = [(int(lm[i].x*w), int(lm[i].y*h)) for i in self.RIGHT_EYE]

            avgEAR = (EAR(left_eye) + EAR(right_eye)) / 2
            self.ear_buffer.append(avgEAR)
            smoothEAR = sum(self.ear_buffer) / len(self.ear_buffer)

            if smoothEAR < self.EAR_THRESHOLD:
                self.frames_closed += 1
                if self.drowsy_start is None:
                    self.drowsy_start = time.time()
            else:
                if self.frames_closed >= self.EYE_CLOSED_FRAMES:
                    self.blink_count += 1
                    self.session_blink_count += 1  # Track session blinks separately
                    self.blink_times.append(time.time())
                self.frames_closed = 0
                self.drowsy_start = None
                self.drowsy_alert = False

            if self.drowsy_start and time.time() - self.drowsy_start >= self.DROWSY_TIME:
                status, color = "DROWSY", (0, 0, 255)
                if not self.drowsy_alert:
                    speak("You look drowsy")
                    self.drowsy_alert = True

            now = time.time()
            while self.blink_times and now - self.blink_times[0] > 60:
                self.blink_times.popleft()

            blink_rate = len(self.blink_times)
            cv2.putText(frame, f"Blinks: {self.blink_count}", (30, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)
            cv2.putText(frame, f"Blink Rate: {blink_rate}/min", (30, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

        # ================= POSTURE =================
        if face_res and face_res.multi_face_landmarks and pose_res and pose_res.pose_landmarks:
            flm = face_res.multi_face_landmarks[0].landmark
            plm = pose_res.pose_landmarks.landmark

            # Get key points
            NOSE = int(flm[1].y*h)
            L_EYE = (int(flm[33].x*w), int(flm[33].y*h))
            R_EYE = (int(flm[263].x*w), int(flm[263].y*h))
            L_SH = int(plm[11].y*h)
            R_SH = int(plm[12].y*h)

            shoulder_mid = (L_SH + R_SH) // 2
            shoulder_nose = NOSE - shoulder_mid
            shoulder_diff = abs(L_SH - R_SH)
            eye_dist = dist(L_EYE, R_EYE)
            tilt = head_tilt_angle(L_EYE, R_EYE)

            # Baseline calibration
            if not self.baseline_ready:
                if time.time() - self.baseline_start < self.BASELINE_TIME:
                    self.base_shoulder_nose += shoulder_nose
                    self.base_shoulder_diff += shoulder_diff
                    self.base_eye_dist += eye_dist
                    self.base_shoulder_mid += shoulder_mid
                    self.samples += 1
                    
                    # Show calibration message
                    cv2.putText(frame, "CALIBRATING...", (30, 200),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)
                else:
                    if self.samples > 0:
                        self.base_shoulder_nose /= self.samples
                        self.base_shoulder_diff /= self.samples
                        self.base_eye_dist /= self.samples
                        self.base_shoulder_mid /= self.samples
                        self.baseline_ready = True
                        print(f"✅ Baseline set - Eye dist: {self.base_eye_dist:.1f}, Shoulder-Nose: {self.base_shoulder_nose:.1f}")
            else:
                # Check posture only after baseline is ready
                if eye_dist < self.base_eye_dist * self.DISTANCE_CLOSE_FACTOR:
                    status, color, bad = "TOO CLOSE", (0,0,255), True
                elif tilt > 10 and tilt < 170:  # Ignore extreme angles
                    status, color, bad = "HEAD TILTED", (255,0,255), True
                elif shoulder_mid > self.base_shoulder_mid + 20:
                    status, color, bad = "SLOUCHED", (128,0,128), True
                elif shoulder_diff > self.base_shoulder_diff + 25:
                    status, color, bad = "SHOULDERS TILTED", (255,0,0), True
                elif shoulder_nose > self.base_shoulder_nose + 20:
                    status, color, bad = "FORWARD HEAD", (0,0,255), True

        # ================= ALERT TIMER & TRACKING =================
        if bad:
            if self.bad_posture_start is None:
                self.bad_posture_start = time.time()
            
            elapsed = int(time.time() - self.bad_posture_start)
            cv2.putText(frame, f"Bad posture: {elapsed}s", (30, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,255), 2)

            if elapsed >= self.POSTURE_SOUND_DELAY and not self.posture_alert:
                speak("Bad posture detected")
                self.posture_alert = True
        else:
            # Only add to total if we were previously in bad posture
            if self.bad_posture_start is not None:
                elapsed_bad = time.time() - self.bad_posture_start
                self.total_bad_posture_time += elapsed_bad
            
            self.bad_posture_start = None
            self.posture_alert = False

        # Display status
        cv2.putText(frame, status, (30, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)

        # Add mode indicator
        cv2.putText(frame, "WEEKDAY MODE", (30, h - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        ret, jpeg = cv2.imencode(".jpg", frame)
        if not ret:
            return None
        return jpeg.tobytes()