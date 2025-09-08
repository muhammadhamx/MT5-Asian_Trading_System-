from django.db import models
from django.utils import timezone


class SystemLog(models.Model):
    """Model to store system logs"""
    LOG_LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    level = models.CharField(max_length=20, choices=LOG_LEVEL_CHOICES)
    component = models.CharField(max_length=50)
    message = models.TextField()
    data = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'system_log'
        ordering = ['-timestamp']


