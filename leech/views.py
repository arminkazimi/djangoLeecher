import json
import threading
import time
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import LeechJob


SIMULATED_SPEED_SECONDS = 0.8
PROGRESS_STEP = 8


def _simulate_leech(job_id: str) -> None:
    job = LeechJob.objects.get(pk=job_id)
    job.status = LeechJob.STATUS_DOWNLOADING
    job.progress = 0
    job.save(update_fields=['status', 'progress', 'updated_at'])

    for progress in range(PROGRESS_STEP, 101, PROGRESS_STEP):
        time.sleep(SIMULATED_SPEED_SECONDS)
        job.refresh_from_db()
        if job.status == LeechJob.STATUS_FAILED:
            return
        job.progress = min(progress, 100)
        job.status = LeechJob.STATUS_DOWNLOADING if progress < 100 else LeechJob.STATUS_COMPLETED
        job.save(update_fields=['progress', 'status', 'updated_at'])

    if job.status == LeechJob.STATUS_COMPLETED:
        downloads_dir = Path(settings.MEDIA_ROOT) / 'downloads'
        downloads_dir.mkdir(parents=True, exist_ok=True)
        output_path = downloads_dir / f"{job.id}.txt"
        output_path.write_text('Simulated leech result for job ' + str(job.id))
        relative_path = output_path.relative_to(settings.MEDIA_ROOT)
        job.download.name = str(relative_path)
        job.save(update_fields=['download', 'updated_at'])


def _start_simulation(job_id: str) -> None:
    thread = threading.Thread(target=_simulate_leech, args=(job_id,), daemon=True)
    thread.start()


def home(request: HttpRequest) -> HttpResponse:
    jobs = LeechJob.objects.all()
    if request.method == 'POST':
        magnet_link = request.POST.get('magnet_link', '').strip()
        torrent_file = request.FILES.get('torrent_file')

        if not magnet_link and not torrent_file:
            return render(
                request,
                'leech/home.html',
                {
                    'jobs': jobs,
                    'error': 'Provide a magnet link or upload a .torrent file.',
                },
                status=400,
            )

        source_type = LeechJob.SOURCE_MAGNET if magnet_link else LeechJob.SOURCE_TORRENT
        job = LeechJob.objects.create(
            source_type=source_type,
            magnet_link=magnet_link,
            torrent_file=torrent_file,
            status=LeechJob.STATUS_QUEUED,
            progress=0,
        )
        _start_simulation(str(job.id))
        return redirect(reverse('leech:detail', kwargs={'job_id': job.id}))

    return render(request, 'leech/home.html', {'jobs': jobs})


def detail(request: HttpRequest, job_id: str) -> HttpResponse:
    job = get_object_or_404(LeechJob, pk=job_id)
    download_url = job.download.url if job.download and job.download.name else ''
    return render(
        request,
        'leech/detail.html',
        {
            'job': job,
            'download_url': download_url,
        },
    )


def stream(request: HttpRequest, job_id: str) -> StreamingHttpResponse:
    job = get_object_or_404(LeechJob, pk=job_id)

    def event_stream():
        while True:
            job.refresh_from_db()
            payload = {
                'status': job.status,
                'status_display': job.get_status_display(),
                'progress': job.progress,
                'download_url': job.download.url if job.download else '',
                'error': job.error_message,
            }
            yield f"data: {json.dumps(payload)}\n\n"
            if job.is_finished:
                break
            time.sleep(1)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response
