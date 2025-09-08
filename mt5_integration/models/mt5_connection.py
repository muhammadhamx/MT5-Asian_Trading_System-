from django.db import models
from django.utils import timezone


class MT5Connection(models.Model):
    """Model to store MT5 connection history"""
    account = models.IntegerField()
    server = models.CharField(max_length=100, default='MetaQuotes-Demo')
    connected_at = models.DateTimeField(default=timezone.now)
    disconnected_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='connected')

    class Meta:
        db_table = 'mt5_connection'
        ordering = ['-connected_at']


