from django.contrib import admin
from .models import LeechJob


@admin.register(LeechJob)
class LeechJobAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'source_type',
        'status',
        'progress',
        'created_at',
    )
    list_filter = ('status', 'source_type', 'created_at')
    search_fields = ('magnet_link', 'torrent_file')
