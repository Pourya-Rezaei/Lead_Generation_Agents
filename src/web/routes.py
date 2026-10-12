from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import json

from ..errors import ApifyError
from ..service import _safe_error_summary
from .schemas import CampaignForm

router = APIRouter()


@router.get("/health/live")
def health_live():
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready(request: Request):
    database_path = Path(request.app.state.settings.database_path)
    if not database_path.exists():
        raise HTTPException(status_code=503, detail={"code": "database_unavailable"})
    try:
        with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            required = {"leads", "jobs", "schema_metadata"}
            if not required.issubset(tables):
                raise HTTPException(status_code=503, detail={"code": "database_schema_unavailable"})
            version = connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if version is None:
                raise HTTPException(status_code=503, detail={"code": "database_schema_unavailable"})
    except HTTPException:
        raise
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail={"code": "database_unavailable"})
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as heartbeat_connection:
        heartbeat = heartbeat_connection.execute(
            "SELECT heartbeat_at FROM worker_heartbeats ORDER BY heartbeat_at DESC LIMIT 1"
        ).fetchone()
    worker = False
    if heartbeat is not None:
        try:
            worker = (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat[0]).replace(tzinfo=timezone.utc)).total_seconds() <= 120
        except ValueError:
            worker = False
    return {"status": "ready", "database": True, "worker": worker if heartbeat else "not_required"}


@router.post("/api/jobs")
def api_submit_job(request: Request, payload: dict):
    from ..execution.service import JobService
    from ..search_requests import validate_job_request
    try:
        validate_job_request(payload)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid or unsupported source-specific request") from None
    key = str(payload.get("idempotency_key", "")).strip()
    if not key:
        raise HTTPException(status_code=422, detail="idempotency_key is required")
    try:
        job = JobService(request.app.state.settings.database_path).submit(payload, key)
    except ValueError:
        raise HTTPException(status_code=422, detail="Select an existing source-specific campaign") from None
    return {"job_id": job.job_id, "state": job.state}


@router.get("/api/jobs/{job_id}")
def api_job_status(request: Request, job_id: str):
    from ..execution.service import JobService
    job = JobService(request.app.state.settings.database_path).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    service = JobService(request.app.state.settings.database_path)
    return {
        "job_id": job.job_id, "state": job.state, "progress": job.progress,
        "error_code": job.error_code, "provider_attempts": service.provider_attempts(job_id),
    }


@router.post("/api/jobs/{job_id}/resolve")
def api_resolve_job_review(request: Request, job_id: str, payload: dict):
    from ..execution.service import JobService
    action = payload.get("action")
    source = payload.get("source")
    if action == "attach_run":
        if not isinstance(source, str):
            raise HTTPException(status_code=422, detail="source is required to attach a run")
        try:
            request.app.state.service.registry.validate_source(source)
        except ValueError:
            raise HTTPException(status_code=422, detail="source is invalid") from None
    try:
        job = JobService(request.app.state.settings.database_path).resolve_needs_review(
            job_id,
            action,
            source=source if isinstance(source, str) else None,
            provider_run_id=payload.get("provider_run_id") if isinstance(payload.get("provider_run_id"), str) else None,
            confirmed_no_remote_run=payload.get("confirmed_no_remote_run") is True,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Request cannot be resumed or retried safely; verify the source and provider-run confirmation") from None
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.job_id, "state": job.state, "progress": job.progress}


@router.post("/api/jobs/{job_id}/retry")
def api_retry_job(request: Request, job_id: str):
    from ..execution.service import JobService
    import uuid
    service = JobService(request.app.state.settings.database_path)
    job = service.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state not in {"failed", "partial", "cancelled"}:
        raise HTTPException(status_code=409, detail="job is not retryable")
    retry_key = f"retry:{job_id}:{uuid.uuid4().hex}"
    retry_request = dict(job.request)
    from ..search_requests import validate_job_request
    try:
        validate_job_request(retry_request)
    except ValueError:
        raise HTTPException(status_code=409, detail="unsupported_source") from None
    try:
        retried = service.submit(retry_request, retry_key)
    except ValueError:
        raise HTTPException(status_code=409, detail="Select an existing source-specific campaign") from None
    return {"job_id": retried.job_id, "state": retried.state, "retry_of": job_id}


@router.post("/api/jobs/{job_id}/cancel")
def api_cancel_job(request: Request, job_id: str):
    from ..execution.service import JobService
    job = JobService(request.app.state.settings.database_path).cancel(
        job_id, abort_provider_run=request.app.state.service.abort_provider_run
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.job_id, "state": job.state}


def _templates(request: Request):
    return request.app.state.templates


def _source_capabilities(request: Request):
    capabilities = request.app.state.service.source_capabilities()
    return capabilities if isinstance(capabilities, tuple) else ()


@router.get("/api/source-contracts")
def api_source_contracts():
    return [{"platform": "places", "actor": "compass~crawler-google-places", "status": "enabled"}, {"platform": "instagram", "actor": "apify~instagram-search-scraper", "status": "standard_only"}]


@router.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="sources.html",
        context={"contracts": api_source_contracts()},
    )


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request):
    from ..execution.service import JobService
    return _templates(request).TemplateResponse(
        request=request,
        name="jobs.html",
        context={"jobs": JobService(request.app.state.settings.database_path).recent()},
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(request: Request, job_id: str):
    from ..execution.service import JobService
    job = JobService(request.app.state.settings.database_path).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    import sqlite3
    service = JobService(request.app.state.settings.database_path)
    attempts = service.provider_attempts(job_id)
    refs = job.progress.get("persisted_refs", {})
    run_ids = {item["provider_run_id"] for item in attempts if item.get("provider_run_id") and item["source"] == "instagram"}
    if isinstance(refs, dict) and isinstance(refs.get("run_id"), str):
        run_ids.add(refs["run_id"])
    if job.request.get("source") == "instagram" and job.provider_run_id:
        run_ids.add(job.provider_run_id)
    profiles, counts = [], None
    independent_run_id = None
    with sqlite3.connect(request.app.state.settings.database_path) as db:
        for run_id in sorted(run_ids):
            row = db.execute("SELECT payload, status FROM instagram_campaign_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                row = db.execute("SELECT payload, status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row or row[1] != "succeeded":
                continue
            payload = json.loads(row[0])
            if payload.get("source") != "instagram" or payload.get("contract_version") != "instagram-search-standard-v1":
                continue
            counts = {key: payload.get(key, 0) for key in ("received_count", "accepted_count", "rejected_count")}
            independent_run_id = run_id
            profiles = request.app.state.store.instagram_profiles(run_id)
    from ..search_requests import validate_job_request
    try:
        validate_job_request(job.request)
        can_execute = True
    except ValueError:
        can_execute = False
    return _templates(request).TemplateResponse(request=request, name="job_detail.html", context={"job": job, "can_execute": can_execute, "instagram_profiles": profiles, "instagram_counts": counts, "instagram_run_id": independent_run_id, "provider_attempts": attempts})


@router.get("/api/instagram-runs/{run_id}/export/{format}")
def export_instagram_run(request: Request, run_id: str, format: str):
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=422, detail="format must be json or csv")
    try:
        profiles = request.app.state.store.instagram_profiles(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Independent Instagram run not found") from None
    from ..exporters import render_instagram_profiles
    return Response(render_instagram_profiles(profiles, format), media_type="application/json" if format == "json" else "text/csv", headers={"Content-Disposition": f'attachment; filename="instagram-profiles.{format}"'})


@router.get("/profiles/{lead_id}", response_class=HTMLResponse)
def profile_review_page(request: Request, lead_id: str):
    import sqlite3
    with sqlite3.connect(request.app.state.settings.database_path) as db:
        rows = db.execute("SELECT candidate_id, platform, url, status, confidence, evidence, review_reason FROM profile_candidates WHERE lead_id = ? ORDER BY created_at", (lead_id,)).fetchall()
    candidates = [{"candidate_id": r[0], "platform": r[1], "url": r[2], "status": r[3], "confidence": r[4], "evidence": r[5], "review_reason": r[6]} for r in rows]
    return _templates(request).TemplateResponse(request=request, name="profiles.html", context={"lead_id": lead_id, "candidates": candidates})


@router.get("/api/profile-candidates/{lead_id}")
def api_profile_candidates(request: Request, lead_id: str):
    import sqlite3
    with sqlite3.connect(request.app.state.settings.database_path) as db:
        rows = db.execute("SELECT candidate_id, platform, url, status, confidence, evidence, review_reason FROM profile_candidates WHERE lead_id = ? ORDER BY created_at", (lead_id,)).fetchall()
    return [{"candidate_id": r[0], "platform": r[1], "url": r[2], "status": r[3], "confidence": r[4], "evidence": r[5], "review_reason": r[6]} for r in rows]


@router.post("/api/profile-candidates/{candidate_id}/review")
def api_review_profile(request: Request, candidate_id: str, payload: dict):
    raise HTTPException(status_code=409, detail="Historical profile candidates are read-only")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    store = request.app.state.store
    return _templates(request).TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"campaign_count": len(store.campaigns()), "lead_count": len(store.all())},
    )


@router.get("/campaigns", response_class=HTMLResponse)
@router.get("/google-places-campaigns", response_class=HTMLResponse)
def campaigns(request: Request):
    if request.url.path == "/campaigns":
        return RedirectResponse(str(request.url.replace(path="/google-places-campaigns")), status_code=307)
    return _templates(request).TemplateResponse(
        request=request,
        name="campaigns.html",
        context={"campaigns": request.app.state.store.campaigns()},
    )


@router.post("/campaigns")
@router.post("/google-places-campaigns")
def create_campaign(
    request: Request,
    campaign_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
):
    try:
        form = CampaignForm.from_form(campaign_id, name, description)
        request.app.state.store.create_campaign(
            form.name, form.description, form.campaign_id
        )
    except ValueError as exc:
        return _templates(request).TemplateResponse(
            request=request,
            name="campaigns.html",
            context={
                "campaigns": request.app.state.store.campaigns(),
                "error": str(exc),
            },
            status_code=400,
        )
    return RedirectResponse(f"/google-places-campaigns/{form.campaign_id}", status_code=303)


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
@router.get("/google-places-campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(request: Request, campaign_id: str):
    if request.url.path.startswith("/campaigns/"):
        return RedirectResponse(str(request.url.replace(path=request.url.path.replace("/campaigns/", "/google-places-campaigns/", 1))), status_code=307)
    store = request.app.state.store
    campaign = store.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _templates(request).TemplateResponse(
        request=request,
        name="campaign_detail.html",
        context={
            "campaign": campaign,
            "stats": store.campaign_stats(campaign_id),
            "leads": store.leads_for_campaign(campaign_id),
        },
    )


@router.get("/campaigns/{campaign_id}/export")
@router.get("/google-places-campaigns/{campaign_id}/export")
def export_campaign(request: Request, campaign_id: str, format: str = "json"):
    if request.url.path.startswith("/campaigns/"):
        return RedirectResponse(str(request.url.replace(path=request.url.path.replace("/campaigns/", "/google-places-campaigns/", 1))), status_code=307)
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="format must be json or csv")
    if request.app.state.store.get_campaign(campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    from ..exporters import render_leads
    content = render_leads(request.app.state.store.leads_for_campaign(campaign_id), format)
    media_type = "application/json" if format == "json" else "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{campaign_id}.{format}"'
        },
    )


@router.get("/search", response_class=HTMLResponse)
def search_form(request: Request, source: str = "places"):
    if source not in {"places", "instagram"}:
        raise HTTPException(status_code=422, detail="unsupported_source")
    return _templates(request).TemplateResponse(
        request=request,
        name="search.html",
        context={
            "campaigns": request.app.state.store.instagram_campaigns() if source == "instagram" else request.app.state.store.campaigns(),
            "source": source,
            "sources": _source_capabilities(request),
        },
    )


@router.post("/search", response_class=HTMLResponse)
def run_search(
    request: Request,
    query: str | None = Form(None),
    location: str | None = Form(None),
    search: str | None = Form(None),
    searchLimit: str | None = Form(None),
    campaign_id: str = Form(...),
    limit: str | None = Form(None),
    source: list[str] = Form(default=["places"]),
):
    sources = source
    form = {
        "search": search or "",
        "searchLimit": searchLimit or "10",
        "query": query or "",
        "location": location or "",
        "campaign_id": campaign_id,
        "limit": limit or "20",
        "sources": sources,
    }
    campaigns = request.app.state.store.instagram_campaigns() if sources == ["instagram"] else request.app.state.store.campaigns()
    try:
        parsed_limit = int(limit or "20")
        if len(sources) != 1 or sources[0] not in {"places", "instagram"}:
            raise ValueError("Selected source is not enabled.")
        request.app.state.service.select_sources(sources)
        if sources == ["places"] and (search is not None or searchLimit is not None):
            raise ValueError("Places does not accept Instagram fields")
        if sources == ["places"] and (not (query or "").strip() or not (location or "").strip()):
            raise ValueError("Query and location are required.")
        # Apify-backed sources are asynchronous provider jobs.  Do not run their
        # polling loop inside the browser request: a slow actor would otherwise
        # make this route appear hung for up to the provider timeout.
        if any(item != "places" for item in sources):
            from ..execution.service import JobService
            import hashlib

            from ..search_requests import InstagramSearchRequest
            if query is not None or location is not None or limit is not None:
                raise ValueError("Instagram accepts only its search phrase")
            validated = InstagramSearchRequest(search=search or "", searchLimit=int(searchLimit or "10"))
            request_payload = {**validated.model_dump(), "campaign_id": campaign_id}
            idempotency_key = "web-search-" + hashlib.sha256(
                json.dumps(request_payload, sort_keys=True).encode("utf-8")
            ).hexdigest()
            job = JobService(request.app.state.settings.database_path).submit(
                {key: value for key, value in request_payload.items() if value is not None},
                idempotency_key,
            )
            return RedirectResponse(f"/jobs/{job.job_id}", status_code=303)
        if len(sources) == 1:
            request.app.state.service.search(
                query, location, source=sources[0], limit=parsed_limit, campaign_id=campaign_id
            )
            result = {"state": "succeeded", "completed_steps": sources}
    except (ValueError, ApifyError) as exc:
        status_code = 400 if isinstance(exc, ValueError) else 502
        return _templates(request).TemplateResponse(
            request=request,
            name="search.html",
            context={
                "campaigns": campaigns,
                "form": form,
                "source": sources[0] if len(sources) == 1 else "places",
                "sources": _source_capabilities(request),
                "error": ("ورودی منبع معتبر نیست؛ Instagram یک عبارت بدون کاما و سقف ۱ تا ۲۵۰ می‌پذیرد." if isinstance(exc, ValueError) else _safe_error_summary(exc)),
            },
            status_code=status_code,
        )
    if result["state"] == "partial":
        completed = ", ".join(result["completed_steps"]) or "هیچ منبعی"
        return _templates(request).TemplateResponse(
            request=request,
            name="search.html",
            context={
                "campaigns": campaigns,
                "form": form,
                "sources": _source_capabilities(request),
                "notice": f"نتایج ناقص ذخیره شد؛ منابع موفق: {completed}",
            },
            status_code=207,
        )
    return RedirectResponse(
        f"/google-places-campaigns/{campaign_id}?message=Search+completed", status_code=303
    )


@router.get("/instagram-campaigns", response_class=HTMLResponse)
def instagram_campaigns_page(request: Request):
    return _templates(request).TemplateResponse(request=request, name="instagram_campaigns.html", context={"campaigns": request.app.state.store.instagram_campaigns()})


@router.post("/instagram-campaigns")
def create_instagram_campaign(request: Request, campaign_id: str = Form(...), name: str = Form(...), description: str = Form("")):
    try:
        form = CampaignForm.from_form(campaign_id, name, description)
        request.app.state.store.create_instagram_campaign(form.name, form.description, form.campaign_id)
    except ValueError:
        return _templates(request).TemplateResponse(request=request, name="instagram_campaigns.html", context={"campaigns": request.app.state.store.instagram_campaigns(), "error": "نام یا شناسهٔ فهرست معتبر نیست."}, status_code=400)
    return RedirectResponse(f"/instagram-campaigns/{form.campaign_id}", status_code=303)


@router.get("/instagram-campaigns/{campaign_id}", response_class=HTMLResponse)
def instagram_campaign_detail(request: Request, campaign_id: str):
    store = request.app.state.store
    campaign = store.get_instagram_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Instagram campaign not found")
    return _templates(request).TemplateResponse(request=request, name="instagram_campaign_detail.html", context={"campaign": campaign, "profiles": store.instagram_campaign_profiles(campaign_id), "runs": store.instagram_campaign_runs(campaign_id)})


@router.get("/instagram-campaigns/{campaign_id}/export")
def export_instagram_campaign(request: Request, campaign_id: str, format: str = "json"):
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=422, detail="format must be json or csv")
    if request.app.state.store.get_instagram_campaign(campaign_id) is None:
        raise HTTPException(status_code=404, detail="Instagram campaign not found")
    from ..exporters import render_instagram_profiles
    return Response(render_instagram_profiles(request.app.state.store.instagram_campaign_profiles(campaign_id), format), media_type="application/json" if format == "json" else "text/csv", headers={"Content-Disposition": f'attachment; filename="instagram-campaign.{format}"'})


@router.get("/api/instagram-campaigns")
def api_instagram_campaigns(request: Request):
    return request.app.state.store.instagram_campaigns()


@router.post("/api/instagram-campaigns", status_code=201)
def api_create_instagram_campaign(request: Request, payload: dict):
    try:
        name = payload.get("name")
        campaign_id = payload.get("campaign_id")
        description = payload.get("description")
        if not isinstance(name, str) or (campaign_id is not None and not isinstance(campaign_id, str)) or (description is not None and not isinstance(description, str)):
            raise ValueError("Invalid campaign")
        return request.app.state.store.create_instagram_campaign(name, description, campaign_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid or duplicate Instagram campaign") from None
