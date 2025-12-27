from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse
import json
import threading
import time

from .models import YogaSession, WeekdaySession
from .camera.weekday import WeekdayCamera
from .camera.weekend import WeekendCamera

# Global camera instances with lock
weekday_cam = None
weekend_cam = None
camera_lock = threading.Lock()
current_camera = None
video_stream_active = False


# =========================
# CLEANUP FUNCTION
# =========================
def cleanup_all_cameras():
    """Cleanup all camera instances and their MediaPipe models"""
    global weekday_cam, weekend_cam, current_camera, video_stream_active
    
    # Stop video stream first
    video_stream_active = False
    time.sleep(0.3)
    
    with camera_lock:
        print("🧹 Starting complete camera cleanup...")
        
        # Cleanup weekday camera
        if weekday_cam is not None:
            print("🧹 Cleaning up weekday camera")
            try:
                if hasattr(weekday_cam, 'face_mesh') and weekday_cam.face_mesh:
                    weekday_cam.face_mesh.close()
                if hasattr(weekday_cam, 'pose') and weekday_cam.pose:
                    weekday_cam.pose.close()
                weekday_cam.release()
            except Exception as e:
                print(f"Warning during weekday cleanup: {e}")
            weekday_cam = None
        
        # Cleanup weekend camera
        if weekend_cam is not None:
            print("🧹 Cleaning up weekend camera")
            try:
                if hasattr(weekend_cam, 'pose') and weekend_cam.pose:
                    weekend_cam.pose.close()
                weekend_cam.release()
            except Exception as e:
                print(f"Warning during weekend cleanup: {e}")
            weekend_cam = None
        
        current_camera = None
        time.sleep(0.5)  # Extra delay for camera hardware
        print("✅ All cameras cleaned up and released")


# =========================
# FRAME GENERATOR
# =========================
def frame_generator(camera):
    """Generate frames from the camera object"""
    global video_stream_active
    video_stream_active = True
    
    try:
        while video_stream_active:
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
    except GeneratorExit:
        print("🛑 Frame generator stopped")
    except Exception as e:
        print(f"❌ Frame generator error: {e}")
    finally:
        video_stream_active = False


# =========================
# STREAM VIEW
# =========================
def video_feed(request):
    global weekday_cam, weekend_cam, current_camera, video_stream_active

    mode = request.GET.get("mode", "weekday")
    print(f"🔹 VIDEO FEED REQUEST: {mode}")

    # Stop any existing stream
    video_stream_active = False
    time.sleep(0.5)

    with camera_lock:
        if mode == "weekday":
            print("✅ Initializing WeekdayCamera")
            
            # Clean up weekend camera if active
            if weekend_cam is not None:
                print("🧹 Cleaning up weekend camera")
                try:
                    if hasattr(weekend_cam, 'pose') and weekend_cam.pose:
                        weekend_cam.pose.close()
                    weekend_cam.release()
                except Exception as e:
                    print(f"Warning during weekend cleanup: {e}")
                weekend_cam = None
                time.sleep(0.5)
            
            # Clean up old weekday camera if exists
            if weekday_cam is not None:
                print("🧹 Cleaning up old weekday camera")
                try:
                    if hasattr(weekday_cam, 'face_mesh') and weekday_cam.face_mesh:
                        weekday_cam.face_mesh.close()
                    if hasattr(weekday_cam, 'pose') and weekday_cam.pose:
                        weekday_cam.pose.close()
                    weekday_cam.release()
                except Exception as e:
                    print(f"Warning during old weekday cleanup: {e}")
                weekday_cam = None
                time.sleep(0.5)
            
            # Create new weekday camera
            print("🎬 Creating new WeekdayCamera")
            weekday_cam = WeekdayCamera()
            camera = weekday_cam
            current_camera = "weekday"
            
        else:  # weekend mode
            print("✅ Initializing WeekendCamera")
            
            # Clean up weekday camera if active
            if weekday_cam is not None:
                print("🧹 Cleaning up weekday camera")
                try:
                    if hasattr(weekday_cam, 'face_mesh') and weekday_cam.face_mesh:
                        weekday_cam.face_mesh.close()
                    if hasattr(weekday_cam, 'pose') and weekday_cam.pose:
                        weekday_cam.pose.close()
                    weekday_cam.release()
                except Exception as e:
                    print(f"Warning during weekday cleanup: {e}")
                weekday_cam = None
                time.sleep(0.5)
            
            # Clean up old weekend camera if exists
            if weekend_cam is not None:
                print("🧹 Cleaning up old weekend camera")
                try:
                    if hasattr(weekend_cam, 'pose') and weekend_cam.pose:
                        weekend_cam.pose.close()
                    weekend_cam.release()
                except Exception as e:
                    print(f"Warning during old weekend cleanup: {e}")
                weekend_cam = None
                time.sleep(0.5)
            
            # Create new weekend camera
            print("🎬 Creating new WeekendCamera")
            weekend_cam = WeekendCamera()
            camera = weekend_cam
            current_camera = "weekend"

    return StreamingHttpResponse(
        frame_generator(camera),
        content_type="multipart/x-mixed-replace; boundary=frame"
    )


# =========================
# HOME PAGE
# =========================
def home_page(request):
    """Home page - cleanup cameras and release hardware"""
    print("🏠 Loading Home Page - Stopping streams and cleaning up cameras")
    cleanup_all_cameras()
    return render(request, "monitor/home.html")


# =========================
# PAGE VIEWS
# =========================
def weekday_page(request):
    print("🌐 Loading Weekday Page")
    return render(request, "monitor/weekday.html")


def weekend_page(request):
    print("🌐 Loading Weekend Page")
    return render(request, "monitor/weekend.html")


# =========================
# SAVE WEEKDAY SESSION
# =========================
def reset_weekday_session(request):
    """Reset session-specific counters when starting a new session"""
    global weekday_cam
    
    if request.method == "POST":
        try:
            if weekday_cam is not None:
                weekday_cam.session_blink_count = 0
                weekday_cam.total_bad_posture_time = 0
                weekday_cam.bad_posture_start = None
                print("🔄 Session counters reset")
            return JsonResponse({"status": "reset"})
        except Exception as e:
            print(f"Warning: Reset error: {e}")
            return JsonResponse({"status": "error"})
    
    return JsonResponse({"status": "invalid"})


def save_weekday_session(request):
    global weekday_cam
    
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            duration = data.get("duration")

            if duration is None:
                return JsonResponse({"status": "error", "message": "No duration"})

            # Get stats from camera if available
            blink_count = 0
            bad_posture_time = 0
            
            if weekday_cam is not None:
                # Use session-specific blink count
                blink_count = getattr(weekday_cam, 'session_blink_count', 0)
                bad_posture_time = int(getattr(weekday_cam, 'total_bad_posture_time', 0))
                
                # Cap bad posture time to session duration
                if bad_posture_time > duration:
                    bad_posture_time = duration

            WeekdaySession.objects.create(
                duration=int(duration),
                blink_count=blink_count,
                bad_posture_time=bad_posture_time
            )
            
            # Reset session-specific counters for next session
            if weekday_cam is not None:
                weekday_cam.session_blink_count = 0
                weekday_cam.total_bad_posture_time = 0
                weekday_cam.bad_posture_start = None
            
            print(f"💾 Weekday session saved: {duration}s, blinks: {blink_count}, bad posture: {bad_posture_time}s")
            return JsonResponse({
                "status": "saved",
                "blink_count": blink_count,
                "bad_posture_time": bad_posture_time
            })

        except Exception as e:
            print(f"❌ Error saving weekday session: {e}")
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "invalid"})


# =========================
# SAVE YOGA SESSION
# =========================
def save_session(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            duration = data.get("duration")

            if duration is None:
                return JsonResponse({"status": "error", "message": "No duration"})

            YogaSession.objects.create(duration=int(duration))
            print(f"💾 Yoga session saved: {duration} seconds")
            return JsonResponse({"status": "saved"})

        except Exception as e:
            print(f"❌ Error saving yoga session: {e}")
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "invalid"})


# =========================
# SESSION HISTORY
# =========================
def session_history(request):
    sessions = YogaSession.objects.all().order_by("-date")
    print(f"📊 Loading {sessions.count()} yoga sessions")
    return render(request, "monitor/history.html", {"sessions": sessions})


def weekday_history(request):
    sessions = WeekdaySession.objects.all().order_by("-date")
    print(f"📊 Loading {sessions.count()} weekday sessions")
    return render(request, "monitor/history_weekday.html", {"sessions": sessions})

def combined_history(request):
    """Combined history view showing both weekday and weekend sessions"""
    weekday_sessions = WeekdaySession.objects.all().order_by("-date")
    weekend_sessions = YogaSession.objects.all().order_by("-date")
    
    print(f"📊 Loading combined history - Weekday: {weekday_sessions.count()}, Weekend: {weekend_sessions.count()}")
    
    context = {
        'weekday_sessions': weekday_sessions,
        'weekend_sessions': weekend_sessions,
    }
    
    return render(request, "monitor/combined_history.html", context)