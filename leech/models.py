import uuid
from django.db import models


class LeechJob(models.Model):
    SOURCE_MAGNET = 'magnet'
    SOURCE_TORRENT = 'torrent'
    SOURCE_CHOICES = [
        (SOURCE_MAGNET, 'Magnet'),
        (SOURCE_TORRENT, 'Torrent file'),
    ]

    STATUS_QUEUED = 'queued'
    STATUS_DOWNLOADING = 'downloading'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_DOWNLOADING, 'Downloading'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    magnet_link = models.TextField(blank=True)
    torrent_file = models.FileField(upload_to='torrents/', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    progress = models.FloatField(default=0)
    download = models.FileField(upload_to='downloads/', blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        label = self.magnet_link[:30] if self.magnet_link else self.torrent_file.name
        return f"Job {self.pk} ({label})"

    @property
    def is_finished(self) -> bool:
        return self.status in {self.STATUS_COMPLETED, self.STATUS_FAILED}

    @property
    def percent_display(self) -> str:
        return f"{self.progress:.0f}%"
