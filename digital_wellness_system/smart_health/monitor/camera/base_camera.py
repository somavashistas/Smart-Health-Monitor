import cv2
import threading
import time

class VideoCamera:
    _instance = None
    _lock = threading.Lock()
    _current_mode = None

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.cap = None
            return cls._instance

    def _init_camera(self):
        """Initialize camera if not already initialized"""
        if self.cap is None or not self.cap.isOpened():
            print("📷 Opening camera...")
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("❌ Camera failed to open")
            else:
                print("✅ Camera opened successfully")

    def get_raw_frame(self):
        if not self.cap or not self.cap.isOpened():
            self._init_camera()
            if not self.cap or not self.cap.isOpened():
                return None

        success, frame = self.cap.read()
        if not success:
            return None
        return frame

    def release(self):
        """Release the camera properly"""
        with self._lock:
            if self.cap is not None and self.cap.isOpened():
                print("🔒 Releasing camera...")
                self.cap.release()
                self.cap = None
                # Small delay to ensure camera is fully released
                time.sleep(0.3)
                print("✅ Camera released successfully")
    
    @classmethod
    def reset_camera(cls):
        """Force reset the camera"""
        with cls._lock:
            if cls._instance and cls._instance.cap:
                print("🔄 Resetting camera...")
                cls._instance.cap.release()
                cls._instance.cap = None
                time.sleep(0.3)
                print("✅ Camera reset complete")
    
    @classmethod
    def force_cleanup(cls):
        """Force cleanup of camera instance"""
        with cls._lock:
            if cls._instance:
                if cls._instance.cap is not None:
                    try:
                        cls._instance.cap.release()
                    except:
                        pass
                    cls._instance.cap = None
                cls._instance = None
                print("🧹 Camera instance cleaned up")