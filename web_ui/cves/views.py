import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from .models import CVE, CVESource, CVEDashboardWidget
from .sync import sync_source


@login_required
def dashboard(request):
    widgets = CVEDashboardWidget.objects.filter(user=request.user).order_by('position')
    sources = CVESource.objects.filter(enabled=True)

    # Summary stats
    qs = CVE.objects.all()
    stats = {
        'total': qs.count(),
        'unacknowledged': qs.filter(acknowledged=False).count(),
        'critical': qs.filter(severity='critical', acknowledged=False).count(),
        'important': qs.filter(severity='important', acknowledged=False).count(),
    }

    return render(request, 'cves/dashboard.html', {
        'widgets': widgets,
        'sources': sources,
        'stats': stats,
        'widget_types': CVEDashboardWidget.WIDGET_TYPES,
    })


@login_required
def cve_list(request):
    qs = CVE.objects.select_related('source', 'acknowledged_by')

    severity = request.GET.get('severity', '')
    source_id = request.GET.get('source', '')
    acknowledged = request.GET.get('acknowledged', '')
    search = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if severity:
        qs = qs.filter(severity=severity)
    if source_id:
        qs = qs.filter(source_id=source_id)
    if acknowledged == '0':
        qs = qs.filter(acknowledged=False)
    elif acknowledged == '1':
        qs = qs.filter(acknowledged=True)
    if search:
        qs = qs.filter(
            Q(cve_id__icontains=search) |
            Q(description__icontains=search) |
            Q(bugzilla_description__icontains=search)
        )
    if date_from:
        qs = qs.filter(public_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(public_date__date__lte=date_to)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'cves/cve_list.html', {
        'page': page,
        'sources': CVESource.objects.all(),
        'severity_choices': CVE.SEVERITY_CHOICES,
        'filters': {
            'severity': severity,
            'source': source_id,
            'acknowledged': acknowledged,
            'q': search,
            'date_from': date_from,
            'date_to': date_to,
        },
    })


@login_required
def cve_detail(request, cve_id):
    cve = get_object_or_404(CVE, pk=cve_id)
    return render(request, 'cves/cve_detail.html', {'cve': cve})


@login_required
@require_POST
def acknowledge_cve(request, cve_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    cve = get_object_or_404(CVE, pk=cve_id)
    data = json.loads(request.body)
    cve.acknowledged = True
    cve.acknowledged_by = request.user
    cve.acknowledged_at = timezone.now()
    cve.acknowledgement_note = data.get('note', '')
    cve.save(update_fields=['acknowledged', 'acknowledged_by', 'acknowledged_at', 'acknowledgement_note'])
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def unacknowledge_cve(request, cve_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    cve = get_object_or_404(CVE, pk=cve_id)
    cve.acknowledged = False
    cve.acknowledged_by = None
    cve.acknowledged_at = None
    cve.acknowledgement_note = ''
    cve.save(update_fields=['acknowledged', 'acknowledged_by', 'acknowledged_at', 'acknowledgement_note'])
    return JsonResponse({'status': 'ok'})


@login_required
def api_widget_data(request, widget_id):
    widget = get_object_or_404(CVEDashboardWidget, pk=widget_id, user=request.user)
    cfg = widget.config

    qs = CVE.objects.all()
    if cfg.get('severity'):
        qs = qs.filter(severity=cfg['severity'])
    if cfg.get('source'):
        qs = qs.filter(source_id=cfg['source'])
    if cfg.get('acknowledged') is not None:
        qs = qs.filter(acknowledged=cfg['acknowledged'])

    wtype = widget.widget_type

    if wtype == 'cve_table':
        items = list(qs.values(
            'id', 'cve_id', 'severity', 'cvss3_score', 'public_date', 'acknowledged',
            'description', 'cwe'
        )[:100])
        return JsonResponse({'type': wtype, 'data': items})

    elif wtype == 'severity_chart':
        counts = qs.values('severity').annotate(count=Count('id')).order_by('severity')
        return JsonResponse({'type': wtype, 'data': list(counts)})

    elif wtype == 'timeline_chart':
        from django.db.models.functions import TruncMonth
        data = (
            qs.annotate(month=TruncMonth('public_date'))
            .values('month').annotate(count=Count('id')).order_by('month')
        )
        result = [{'month': str(d['month'])[:7] if d['month'] else None, 'count': d['count']} for d in data]
        return JsonResponse({'type': wtype, 'data': result})

    elif wtype == 'unacked_count':
        count = qs.filter(acknowledged=False).count()
        return JsonResponse({'type': wtype, 'data': count})

    elif wtype == 'top_packages':
        from django.db.models import Func, IntegerField
        # Count across JSON arrays - aggregate in Python for MariaDB compatibility
        pkg_counts = {}
        for cve in qs.only('affected_packages'):
            for pkg in (cve.affected_packages or []):
                name = pkg if isinstance(pkg, str) else pkg.get('name', str(pkg))
                pkg_counts[name] = pkg_counts.get(name, 0) + 1
        top = sorted(pkg_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        return JsonResponse({'type': wtype, 'data': [{'package': k, 'count': v} for k, v in top]})

    return JsonResponse({'error': 'Unknown widget type'}, status=400)


@login_required
@require_POST
def add_widget(request):
    data = json.loads(request.body)
    count = CVEDashboardWidget.objects.filter(user=request.user).count()
    size = data.get('size', 'half')
    if size not in ('full', 'half', 'quarter'):
        size = 'half'
    widget = CVEDashboardWidget.objects.create(
        user=request.user,
        widget_type=data.get('widget_type', 'cve_table'),
        title=data.get('title', 'CVE Widget'),
        position=count,
        size=size,
        config=data.get('config', {}),
    )
    return JsonResponse({'id': str(widget.id), 'status': 'created'})


@login_required
@require_POST
def update_widget_layout(request):
    """Bulk-update positions and sizes for all widgets belonging to the current user."""
    data = json.loads(request.body)
    widgets_data = data.get('widgets', [])
    for entry in widgets_data:
        wid = entry.get('id')
        pos = entry.get('position')
        size = entry.get('size')
        if not wid:
            continue
        update = {}
        if pos is not None:
            update['position'] = int(pos)
        if size in ('full', 'half', 'quarter'):
            update['size'] = size
        if update:
            CVEDashboardWidget.objects.filter(pk=wid, user=request.user).update(**update)
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def remove_widget(request, widget_id):
    widget = get_object_or_404(CVEDashboardWidget, pk=widget_id, user=request.user)
    widget.delete()
    return JsonResponse({'status': 'deleted'})


@login_required
@require_POST
def sync_now(request, source_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    source = get_object_or_404(CVESource, pk=source_id)
    days_back = None
    try:
        body = json.loads(request.body)
        days_back_raw = body.get('days_back')
        if days_back_raw is not None:
            days_back = int(days_back_raw)
    except Exception:
        pass
    try:
        count = sync_source(source, days_back=days_back)
        return JsonResponse({'status': 'ok', 'imported': count})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def sources_list(request):
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    if request.method == 'POST':
        days_back = request.POST.get('default_days_back', '365')
        try:
            days_back = max(0, int(days_back))
        except (ValueError, TypeError):
            days_back = 365
        CVESource.objects.create(
            name=request.POST.get('name', '').strip(),
            source_type=request.POST.get('source_type', 'custom'),
            api_url=request.POST.get('api_url', '').strip(),
            default_days_back=days_back,
        )
        from django.contrib import messages
        messages.success(request, 'Source added.')
        from django.shortcuts import redirect
        return redirect('cves:sources')
    sources = CVESource.objects.all()
    return render(request, 'cves/sources.html', {'sources': sources})

