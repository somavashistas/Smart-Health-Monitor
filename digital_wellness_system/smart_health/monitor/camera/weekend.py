import cv2
import mediapipe as mp
import math
import time
from .base_camera import VideoCamera

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

class WeekendCamera(VideoCamera):
    def __init__(self):
        super().__init__()
        print("🎯 WeekendCamera initialized!")

        self.pose = mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.5,
            model_complexity=1
        )

        self.previous_pose = "Unknown Pose"
        self.pose_counter = 0
        self.POSE_STABILITY_THRESHOLD = 5

        self.pose_locked = False
        self.hold_start_time = None
        self.HOLD_DURATION = 5
        self.final_pose = "Unknown Pose"

    def release(self):
        """Cleanup MediaPipe and camera"""
        try:
            if hasattr(self, 'pose') and self.pose:
                self.pose.close()
            print("🧹 WeekendCamera MediaPipe cleaned up")
        except Exception as e:
            print(f"Warning during MediaPipe cleanup: {e}")
        
        # Call parent release
        super().release()

    # ---------- ANGLE CALCULATION ----------
    def calculateAngle(self, a, b, c):
        x1, y1, _ = a
        x2, y2, _ = b
        x3, y3, _ = c
        angle = math.degrees(math.atan2(y3 - y2, x3 - x2) -
                             math.atan2(y1 - y2, x1 - x2))
        angle = abs(angle)
        if angle > 180:
            angle = 360 - angle
        return angle

    # ---------- YOGA CLASSIFICATION ----------
    def classifyPose(self, landmarks):
        label = "Unknown Pose"
        L = mp_pose.PoseLandmark

        left_elbow_angle = self.calculateAngle(landmarks[L.LEFT_SHOULDER.value],
                                               landmarks[L.LEFT_ELBOW.value],
                                               landmarks[L.LEFT_WRIST.value])

        right_elbow_angle = self.calculateAngle(landmarks[L.RIGHT_SHOULDER.value],
                                                landmarks[L.RIGHT_ELBOW.value],
                                                landmarks[L.RIGHT_WRIST.value])

        left_shoulder_angle = self.calculateAngle(landmarks[L.LEFT_ELBOW.value],
                                                  landmarks[L.LEFT_SHOULDER.value],
                                                  landmarks[L.LEFT_HIP.value])

        right_shoulder_angle = self.calculateAngle(landmarks[L.RIGHT_HIP.value],
                                                   landmarks[L.RIGHT_SHOULDER.value],
                                                   landmarks[L.RIGHT_ELBOW.value])

        left_knee_angle = self.calculateAngle(landmarks[L.LEFT_HIP.value],
                                             landmarks[L.LEFT_KNEE.value],
                                             landmarks[L.LEFT_ANKLE.value])

        right_knee_angle = self.calculateAngle(landmarks[L.RIGHT_HIP.value],
                                              landmarks[L.RIGHT_KNEE.value],
                                              landmarks[L.RIGHT_ANKLE.value])

        left_hip_angle = self.calculateAngle(landmarks[L.LEFT_SHOULDER.value],
                                            landmarks[L.LEFT_HIP.value],
                                            landmarks[L.LEFT_KNEE.value])

        right_hip_angle = self.calculateAngle(landmarks[L.RIGHT_SHOULDER.value],
                                             landmarks[L.RIGHT_HIP.value],
                                             landmarks[L.RIGHT_KNEE.value])

        # -------- Virabhadrasana II or T Pose --------
        if 165 < left_elbow_angle < 195 and 165 < right_elbow_angle < 195:
            if 80 < left_shoulder_angle < 110 and 80 < right_shoulder_angle < 110:
                if 165 < left_knee_angle < 195 or 165 < right_knee_angle < 195:
                    if 90 < left_knee_angle < 120 or 90 < right_knee_angle < 120:
                        label = "Virabhadrasana II"
                        print("Virabhadrasana II Detected")

                if 160 < left_knee_angle < 195 and 160 < right_knee_angle < 195:
                    label = "T Pose"

        # -------- Vrikshasana (Tree Pose) --------
        if 165 < left_knee_angle < 195 or 165 < right_knee_angle < 195:
            if 315 < left_knee_angle < 335 or 25 < right_knee_angle < 45:
                label = "Vrikshasana"

        # -------- Adho Mukha Svanasana (Downward Dog) --------
        if 165 < left_elbow_angle < 195 and 165 < right_elbow_angle < 195:
            if 165 < left_knee_angle < 195 and 165 < right_knee_angle < 195:
                if 60 < left_hip_angle < 120 and 60 < right_hip_angle < 120:

                    left_wrist_y = landmarks[L.LEFT_WRIST.value][1]
                    left_ankle_y = landmarks[L.LEFT_ANKLE.value][1]
                    right_wrist_y = landmarks[L.RIGHT_WRIST.value][1]
                    right_ankle_y = landmarks[L.RIGHT_ANKLE.value][1]

                    if left_wrist_y > left_ankle_y or right_wrist_y > right_ankle_y:
                        label = "Adho Mukha Svanasana"

        # -------- Uttanasana (Forward Bend) --------
        if 165 < left_knee_angle < 195 and 165 < right_knee_angle < 195:
            if 20 < left_hip_angle < 60 and 20 < right_hip_angle < 60:

                left_wrist_y = landmarks[L.LEFT_WRIST.value][1]
                left_ankle_y = landmarks[L.LEFT_ANKLE.value][1]
                right_wrist_y = landmarks[L.RIGHT_WRIST.value][1]
                right_ankle_y = landmarks[L.RIGHT_ANKLE.value][1]

                if abs(left_wrist_y - left_ankle_y) < 50 or abs(right_wrist_y - right_ankle_y) < 50:
                    label = "Uttanasana"

        # -------- Utkatasana (Chair Pose) --------
        if 80 < left_knee_angle < 120 and 80 < right_knee_angle < 120:
            if 80 < left_hip_angle < 120 and 80 < right_hip_angle < 120:
                if 160 < left_shoulder_angle < 200 and 160 < right_shoulder_angle < 200:
                    if 165 < left_elbow_angle < 195 and 165 < right_elbow_angle < 195:
                        label = "Utkatasana"

        # -------- Urdhva Hastasana (Raised Hands Pose) --------
        if 165 < left_knee_angle < 195 and 165 < right_knee_angle < 195:
            if 160 < left_hip_angle < 195 and 160 < right_hip_angle < 195:
                if 160 < left_shoulder_angle < 200 and 160 < right_shoulder_angle < 200:
                    if 165 < left_elbow_angle < 195 and 165 < right_elbow_angle < 195:
                        label = "Urdhva Hastasana"

        return label

    # ---------- GENERATE CAMERA FRAME ----------
    def get_frame(self):
        frame = self.get_raw_frame()

        if frame is None:
            return None

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = None
        try:
            results = self.pose.process(rgb)
        except Exception as e:
            print(f"⚠️ MediaPipe processing error: {e}")
            ret, jpeg = cv2.imencode(".jpg", frame)
            return jpeg.tobytes() if ret else None

        label = "Unknown Pose"

        if results and results.pose_landmarks:
            mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            h, w, _ = frame.shape
            lm = results.pose_landmarks.landmark
            pts = [(int(p.x*w), int(p.y*h), p.z*w) for p in lm]

            label = self.classifyPose(pts)

            if not self.pose_locked:
                if label == self.previous_pose:
                    self.pose_counter += 1
                else:
                    self.pose_counter = 0
                    self.previous_pose = label

                if self.pose_counter >= self.POSE_STABILITY_THRESHOLD and label != "Unknown Pose":
                    self.pose_locked = True
                    self.final_pose = label
                    self.hold_start_time = time.time()

                # Display current pose
                cv2.putText(frame, label, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 0), 3)

            else:
                elapsed = int(time.time() - self.hold_start_time)
                remaining = self.HOLD_DURATION - elapsed

                if remaining > 0:
                    cv2.putText(frame, f"HOLD {remaining}s", (150, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                    cv2.putText(frame, self.final_pose, (140, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                else:
                    self.pose_locked = False
                    self.pose_counter = 0
                    self.previous_pose = "Unknown Pose"

        h, w, _ = frame.shape
        # Add mode indicator
        cv2.putText(frame, "WEEKEND MODE", (20, h - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

        ret, jpeg = cv2.imencode(".jpg", frame)
        if not ret:
            return None
        return jpeg.tobytes()