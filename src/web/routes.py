from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..errors import CampaignNotFoundError
from .schemas import CampaignForm

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


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


@router.get("/search", response_class=HTMLResponse)
def search_form(request: Request):
    return _templates(request).TemplateResponse(
        request=request,
        name="search.html",
        context={"campaigns": request.app.state.store.campaigns(), "source": "places"},
    )
