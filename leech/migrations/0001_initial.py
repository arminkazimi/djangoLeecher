from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='LeechJob',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_type', models.CharField(choices=[('magnet', 'Magnet'), ('torrent', 'Torrent file')], max_length=20)),
                ('magnet_link', models.TextField(blank=True)),
                ('torrent_file', models.FileField(blank=True, upload_to='torrents/')),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('downloading', 'Downloading'), ('completed', 'Completed'), ('failed', 'Failed')], default='queued', max_length=20)),
                ('progress', models.FloatField(default=0)),
                ('download', models.FileField(blank=True, upload_to='downloads/')),
                ('error_message', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
