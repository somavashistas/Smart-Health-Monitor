from django.db import models

class YogaSession(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    duration = models.IntegerField()  # seconds

    @property
    def duration_minutes(self):
        return round(self.duration / 60, 2)

    def __str__(self):
        return f"{self.date} - {self.duration}s"


class WeekdaySession(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    duration = models.IntegerField()  # seconds
    blink_count = models.IntegerField(default=0)
    bad_posture_time = models.IntegerField(default=0)  # seconds

    @property
    def duration_minutes(self):
        return round(self.duration / 60, 2)

    @property
    def bad_posture_minutes(self):
        return round(self.bad_posture_time / 60, 2)

    def __str__(self):
        return f"{self.date} - {self.duration}s"