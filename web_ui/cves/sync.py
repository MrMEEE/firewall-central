"""
CVE sync services for fetching data from external sources.
"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import CVE, CVESource


REDHAT_API_URL = 'https://access.redhat.com/hydra/rest/securitydata/cve.json'
REDHAT_CVE_DETAIL_URL = 'https://access.redhat.com/hydra/rest/securitydata/cve/{cve_id}.json'
MAX_WORKERS = 10


def sync_source(source: CVESource, days_back: int = None) -> int:
    """
    Fetch CVEs from a source and upsert into the database.
    days_back overrides the source's default_days_back setting (0 = all time).
    Returns the number of records created/updated.
    """
    if days_back is None:
        days_back = source.default_days_back

    if source.source_type == 'redhat':
        count = _sync_redhat(source, days_back=days_back)
    else:
        raise ValueError(f"Unsupported source type: {source.source_type}")

    source.last_sync = timezone.now()
    source.save(update_fields=['last_sync'])
    return count


def _fetch_redhat_detail(session: requests.Session, cve_id: str) -> dict:
    """Fetch full detail for a single CVE from the Red Hat per-CVE API."""
    url = REDHAT_CVE_DETAIL_URL.format(cve_id=cve_id)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def _sync_redhat(source: CVESource, days_back: int = 365) -> int:
    """Fetch CVEs from Red Hat Security Data API with full per-CVE detail."""
    url = source.api_url or REDHAT_API_URL
    params = {'per_page': 1000}

    if days_back and days_back > 0:
        after_date = date.today() - timedelta(days=days_back)
        params['after'] = after_date.isoformat()

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    items = response.json()

    # Build a lookup CVE-ID → summary item
    cve_map = {}
    for item in items:
        cve_id = item.get('CVE', '')
        if cve_id:
            cve_map[cve_id] = item

    # Fetch individual details concurrently
    session = requests.Session()
    detail_map = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_cve = {
            executor.submit(_fetch_redhat_detail, session, cve_id): cve_id
            for cve_id in cve_map
        }
        for future in as_completed(future_to_cve):
            cve_id = future_to_cve[future]
            detail = future.result()
            if detail:
                detail_map[cve_id] = detail

    def _list(v):
        if isinstance(v, list):
            return v
        return [v] if v else []

    count = 0
    for cve_id, item in cve_map.items():
        detail = detail_map.get(cve_id, {})

        severity = (
            detail.get('threat_severity')
            or item.get('severity')
            or 'unknown'
        ).lower()
        if severity not in dict(CVE.SEVERITY_CHOICES):
            severity = 'unknown'

        cvss3_score = None
        try:
            raw = item.get('cvss3_score') or detail.get('cvss3_score')
            if raw is not None:
                cvss3_score = float(raw)
        except (TypeError, ValueError):
            pass

        cvss2_score = None
        try:
            raw = item.get('cvss_score') or detail.get('cvss_score')
            if raw is not None:
                cvss2_score = float(raw)
        except (TypeError, ValueError):
            pass

        pub_date = None
        try:
            raw_date = item.get('public_date') or detail.get('public_date')
            if raw_date:
                pub_date = parse_datetime(raw_date)
        except Exception:
            pass

        affected_packages = _list(item.get('affected_packages') or detail.get('affected_packages'))
        advisories = _list(item.get('advisories') or detail.get('advisories'))
        affected_releases = _list(detail.get('affected_release'))
        package_state = _list(detail.get('package_state'))

        refs = detail.get('references') or []
        if isinstance(refs, str):
            refs = [r.strip() for r in refs.splitlines() if r.strip()]
        elif not isinstance(refs, list):
            refs = []

        description = (
            detail.get('details')
            or item.get('bugzilla_description')
            or ''
        )

        defaults = {
            'severity': severity,
            'cvss3_score': cvss3_score,
            'cvss3_vector': (
                item.get('cvss3_scoring_vector')
                or detail.get('cvss3_scoring_vector') or ''
            ),
            'cvss2_score': cvss2_score,
            'cvss2_vector': (
                item.get('cvss_scoring_vector')
                or detail.get('cvss_scoring_vector') or ''
            ),
            'public_date': pub_date,
            'description': description,
            'affected_packages': affected_packages,
            'advisories': advisories,
            'affected_releases': affected_releases,
            'package_state': package_state,
            'cwe': item.get('CWE') or detail.get('CWE') or '',
            'bugzilla': item.get('bugzilla') or detail.get('bugzilla') or '',
            'bugzilla_description': (
                item.get('bugzilla_description')
                or detail.get('bugzilla_description') or ''
            ),
            'resource_url': item.get('resource_url') or detail.get('resource_url') or '',
            'statement': detail.get('statement') or '',
            'mitigation': detail.get('mitigation') or '',
            'upstream_fix': detail.get('upstream_fix') or '',
            'details': detail.get('details') or '',
            'references': refs,
            'details_fetched': bool(detail),
            'raw_data': {**item, **detail},
        }

        CVE.objects.update_or_create(
            cve_id=cve_id,
            source=source,
            defaults=defaults,
        )
        count += 1

    return count
