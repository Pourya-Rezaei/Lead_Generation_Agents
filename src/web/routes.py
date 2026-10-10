from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..errors import (
    ApifyCredentialError,
    ApifyMalformedResponseError,
    ApifyNotFoundError,
    ApifyTransientError,
)
from ..service import _safe_error_summary
from ..registry import DisabledSourceError
from ..social_service import SocialSearchRequest
from .schemas import CampaignForm

router = APIRouter()


@router.post("/api/social-searches")
def api_submit_social_search(request: Request, payload: SocialSearchRequest):
    """Validate a public social request without activating disabled Actors."""
    try:
        selected = request.app.state.social_service.validate(payload)
        results = request.app.state.social_service.search(payload)
    except DisabledSourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "mode": payload.mode,
        "sources": [capability.name for capability in selected],
        "results": results,
    }


@router.post("/api/jobs")
def api_submit_job(request: Request, payload: dict):
    from ..execution.service import JobService
    required = {"query", "location"}
    if not required <= payload.keys():
        raise HTTPException(status_code=422, detail="query and location are required")
    key = str(payload.get("idempotency_key", "")).strip()
    if not key:
        raise HTTPException(status_code=422, detail="idempotency_key is required")
    job = JobService(request.app.state.settings.database_path).submit(payload, key)
    return {"job_id": job.job_id, "state": job.state}


@router.get("/api/jobs/{job_id}")
def api_job_status(request: Request, job_id: str):
    from ..execution.service import JobService
    job = JobService(request.app.state.settings.database_path).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.job_id, "state": job.state, "progress": job.progress, "error_code": job.error_code}


@router.post("/api/jobs/{job_id}/cancel")
def api_cancel_job(request: Request, job_id: str):
    from ..execution.service import JobService
    job = JobService(request.app.state.settings.database_path).cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.job_id, "state": job.state}


def _templates(request: Request):
    return request.app.state.templates


@router.get("/api/profile-candidates/{lead_id}")
def api_profile_candidates(request: Request, lead_id: str):
    import sqlite3
    with sqlite3.connect(request.app.state.settings.database_path) as db:
        rows = db.execute("SELECT candidate_id, platform, url, status, confidence, evidence, review_reason FROM profile_candidates WHERE lead_id = ? ORDER BY created_at", (lead_id,)).fetchall()
    return [{"candidate_id": r[0], "platform": r[1], "url": r[2], "status": r[3], "confidence": r[4], "evidence": r[5], "review_reason": r[6]} for r in rows]


@router.post("/api/profile-candidates/{candidate_id}/review")
def api_review_profile(request: Request, candidate_id: str, payload: dict):
    from ..quality.profiles import ProfileRepository
    import sqlite3
    status = str(payload.get("status", ""))
    reason = str(payload.get("reason", ""))
    with sqlite3.connect(request.app.state.settings.database_path) as db:
        try:
            ProfileRepository(db).review(candidate_id, status, reason)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if db.execute("SELECT changes()").fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="Profile candidate not found")
    return {"candidate_id": candidate_id, "status": status}


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    store = request.app.state.store
    return _templates(request).TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"campaign_count": len(store.campaigns()), "lead_count": len(store.all())},
    )


@router.get("/campaigns", response_class=HTMLResponse)
def campaigns(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="campaigns.html",
        context={"campaigns": request.app.state.store.campaigns()},
    )


@router.post("/campaigns")
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
    return RedirectResponse(f"/campaigns/{form.campaign_id}", status_code=303)


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(request: Request, campaign_id: str):
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
def export_campaign(request: Request, campaign_id: str, format: str = "json"):
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="format must be json or csv")
    if request.app.state.store.get_campaign(campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    suffix = f".{format}"
    with NamedTemporaryFile(suffix=suffix) as temporary:
        request.app.state.store.export(temporary.name, format, campaign_id=campaign_id)
        content = Path(temporary.name).read_bytes()
    media_type = "application/json" if format == "json" else "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{campaign_id}.{format}"'
        },
    )


@router.get("/search", response_class=HTMLResponse)
def search_form(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="search.html",
        context={
            "campaigns": request.app.state.store.campaigns(),
            "source": "places",
            "sources": request.app.state.service.source_capabilities(),
        },
    )


@router.post("/search", response_class=HTMLResponse)
def run_search(
    request: Request,
    query: str = Form(...),
    location: str = Form(...),
    campaign_id: str = Form(...),
    limit: str = Form("20"),
    source: str = Form("places"),
):
    form = {
        "query": query,
        "location": location,
        "campaign_id": campaign_id,
        "limit": limit,
    }
    campaigns = request.app.state.store.campaigns()
    try:
        if source != "places":
            raise ValueError("Only the places source is enabled.")
        parsed_limit = int(limit)
        if not query.strip() or not location.strip():
            raise ValueError("Query and location are required.")
        result = request.app.state.service.search(
            query,
            location,
            source=source,
            limit=parsed_limit,
            campaign_id=campaign_id,
        )
    except (ValueError, ApifyCredentialError, ApifyNotFoundError,
            ApifyTransientError, ApifyMalformedResponseError) as exc:
        status_code = 400 if isinstance(exc, ValueError) else 502
        return _templates(request).TemplateResponse(
            request=request,
            name="search.html",
            context={
                "campaigns": campaigns,
                "form": form,
                "source": source,
                "error": _safe_error_summary(exc),
            },
            status_code=status_code,
        )
    if result.status.value in {"failed", "aborted", "timed_out"}:
        return _templates(request).TemplateResponse(
            request=request,
            name="search.html",
            context={
                "campaigns": campaigns,
                "form": form,
                "source": source,
                "error": "Search did not complete successfully.",
            },
            status_code=502,
        )
    return RedirectResponse(
        f"/campaigns/{campaign_id}?message=Search+completed", status_code=303
    )
