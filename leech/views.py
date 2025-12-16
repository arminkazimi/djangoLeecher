import json
import threading
import time
from pathlib import Path

import libtorrent as lt
from django.conf import settings
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import LeechJob


DOWNLOAD_POLL_SECONDS = 1


def _simulate_leech(job_id: str) -> None:
    job = LeechJob.objects.get(pk=job_id)
    downloads_dir = Path(settings.MEDIA_ROOT) / 'downloads'
    downloads_dir.mkdir(parents=True, exist_ok=True)

    session = lt.session()
    session.listen_on(6881, 6891)

    try:
        params = {'save_path': str(downloads_dir)}
        if job.source_type == LeechJob.SOURCE_MAGNET:
            if not job.magnet_link:
                raise ValueError('Missing magnet link for job')
            handle = lt.add_magnet_uri(session, job.magnet_link, params)
        else:
            if not job.torrent_file:
                raise ValueError('Missing torrent file for job')
            torrent_path = Path(job.torrent_file.path)
            torrent_info = lt.torrent_info(str(torrent_path))
            handle = session.add_torrent({**params, 'ti': torrent_info})
    except Exception as exc:  # noqa: BLE001
        job.status = LeechJob.STATUS_FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return

    job.status = LeechJob.STATUS_DOWNLOADING
    job.progress = 0
    job.error_message = ''
    job.save(update_fields=['status', 'progress', 'error_message', 'updated_at'])

    while True:
        status = handle.status()
        progress = max(0.0, min(status.progress * 100, 100.0))

        job.refresh_from_db()
        if job.status == LeechJob.STATUS_FAILED:
            session.pause()
            return

        if status.errc.value():
            job.status = LeechJob.STATUS_FAILED
            job.error_message = status.errc.message()
            job.save(update_fields=['status', 'error_message', 'updated_at'])
            return

        job.progress = progress
        job.status = LeechJob.STATUS_DOWNLOADING
        job.save(update_fields=['progress', 'status', 'updated_at'])

        if status.is_seeding:
            break

        time.sleep(DOWNLOAD_POLL_SECONDS)

    try:
        torrent_info = handle.get_torrent_info()
        files = torrent_info.files()
        status = handle.status()
        download_root = Path(status.save_path)

        if files.num_files() > 1:
            downloaded_path = download_root / torrent_info.name()
        else:
            downloaded_path = download_root / files.file_path(0)

        if not downloaded_path.exists():
            raise FileNotFoundError(f'Downloaded content not found at {downloaded_path}')

        relative_path = downloaded_path.relative_to(settings.MEDIA_ROOT)
        job.download.name = str(relative_path)
        job.status = LeechJob.STATUS_COMPLETED
        job.progress = 100
        job.save(update_fields=['download', 'status', 'progress', 'updated_at'])
    except Exception as exc:  # noqa: BLE001
        job.status = LeechJob.STATUS_FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])


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
