import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai_service import AIConfigurationError, AIExecutionConflictError, generate_collisions
from app.auth import (
    COOKIE_NAME,
    authenticate_password,
    create_operator_session,
    csrf_token,
    current_session,
    require_session,
    token_hash,
    validate_csrf,
)
from app.config import Settings, get_settings
from app.database import build_engine, build_session_factory, get_db
from app.logging import configure_logging
from app.manual_loop import (
    GATE_NAMES,
    ManualLoopError,
    active_runs,
    approve_learning,
    archive_signal,
    close_creative_run,
    create_creative_run,
    create_experiment,
    create_signal,
    decide_concept,
    finalize_experiment,
    save_challenge,
    save_concept,
    save_learning,
    save_results,
    shortlist_concept,
    transition_experiment,
    update_experiment,
    update_signal,
)
from app.models import (
    AIExecution,
    ChallengeRecommendation,
    Concept,
    ConceptStatus,
    CreativeRun,
    Experiment,
    ExperimentStatus,
    Learning,
    LearningStatus,
    OperatorSession,
    Signal,
    TruthVersion,
)
from app.seed import seed_leasedesk
from app.services import (
    TruthConflictError,
    approve_draft,
    create_draft,
    current_truth,
    leasedesk,
    truth_history,
    update_draft,
)
from app.truth_schema import TRUTH_LABELS, TruthContent
from app.workflow import progression

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        with application.state.session_factory() as session:
            seed_leasedesk(session)
        logger.info("Takaven Go ready", extra={"event": "application.ready"})
        yield
        engine.dispose()

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    def base_context(request: Request, db: Session, active_area: str) -> dict:
        product = leasedesk(db)
        active_truth = current_truth(db, product.id)
        return {
            "request": request,
            "product": product,
            "active_truth": active_truth,
            "active_area": active_area,
            "csrf_token": csrf_token(request, settings),
            "truth_labels": TRUTH_LABELS,
            "progress": progression(db, product, active_truth.version),
        }

    def loop_error(request: Request, db: Session, area: str, message: str, location: str):
        context = base_context(request, db, area)
        context.update({"error": message, "back": location})
        return templates.TemplateResponse(request, "loop_error.html", context, status_code=422)

    def form_values(form, fields: tuple[str, ...]) -> dict[str, str]:
        return {field: str(form.get(field, "")) for field in fields}

    @application.exception_handler(403)
    async def forbidden(request: Request, exc: HTTPException):
        return templates.TemplateResponse(
            request,
            "error.html",
            {"status_code": 403, "message": str(exc.detail)},
            status_code=403,
        )

    @application.exception_handler(404)
    async def not_found(request: Request, exc: HTTPException):
        return templates.TemplateResponse(
            request,
            "error.html",
            {"status_code": 404, "message": "That Takaven Go record does not exist."},
            status_code=404,
        )

    @application.exception_handler(409)
    async def conflict(request: Request, exc: HTTPException):
        return templates.TemplateResponse(
            request,
            "error.html",
            {"status_code": 409, "message": str(exc.detail)},
            status_code=409,
        )

    @application.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, db: Session = Depends(get_db)):
        if current_session(request, db):
            return RedirectResponse("/truth", status_code=303)
        return templates.TemplateResponse(request, "login.html", {"error": None})

    @application.post("/login")
    def login(
        request: Request,
        password: str = Form(...),
        db: Session = Depends(get_db),
    ):
        if not authenticate_password(password, settings):
            logger.warning("Authentication failed", extra={"event": "auth.failed"})
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "That password was not accepted."},
                status_code=401,
            )
        raw_token, _ = create_operator_session(db, settings)
        response = RedirectResponse("/truth", status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            raw_token,
            max_age=settings.session_hours * 3600,
            secure=settings.cookie_secure,
            httponly=True,
            samesite="strict",
            path="/",
        )
        logger.info("Operator authenticated", extra={"event": "auth.succeeded"})
        return response

    @application.post("/logout")
    def logout(
        request: Request,
        csrf: str = Form(...),
        db: Session = Depends(get_db),
    ):
        require_session(request, db)
        validate_csrf(request, csrf, settings)
        raw_token = request.cookies.get(COOKIE_NAME, "")
        db.execute(
            delete(OperatorSession).where(OperatorSession.token_hash == token_hash(raw_token))
        )
        db.commit()
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @application.get("/")
    def root():
        return RedirectResponse("/truth", status_code=303)

    @application.get("/truth", response_class=HTMLResponse)
    def truth_page(request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        context = base_context(request, db, "truth")
        context["history"] = truth_history(db, context["product"].id)
        context["draft"] = next(
            (item for item in context["history"] if item.status == "draft"), None
        )
        context["learnings"] = list(
            db.scalars(
                select(Learning)
                .join(Experiment)
                .where(
                    Experiment.product_id == context["product"].id,
                    Learning.status == LearningStatus.APPROVED,
                )
                .order_by(Learning.approved_at.desc())
            )
        )
        return templates.TemplateResponse(request, "truth/index.html", context)

    @application.post("/truth/drafts")
    def new_draft(
        request: Request,
        csrf: str = Form(...),
        db: Session = Depends(get_db),
    ):
        require_session(request, db)
        validate_csrf(request, csrf, settings)
        draft = create_draft(db, leasedesk(db))
        return RedirectResponse(f"/truth/drafts/{draft.id}/edit", status_code=303)

    @application.get("/truth/drafts/{truth_id}/edit", response_class=HTMLResponse)
    def edit_draft_page(truth_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        draft = db.get(TruthVersion, truth_id)
        if draft is None or draft.product_id != leasedesk(db).id or draft.status != "draft":
            raise HTTPException(status_code=404, detail="Draft not found")
        context = base_context(request, db, "truth")
        context.update({"draft": draft, "errors": [], "form_content": draft.content})
        return templates.TemplateResponse(request, "truth/edit.html", context)

    @application.post("/truth/drafts/{truth_id}")
    async def save_draft(truth_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        draft = db.get(TruthVersion, truth_id)
        if draft is None or draft.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Draft not found")
        raw_content = {
            key: {
                "value": str(form.get(f"{key}__value", "")),
                "confidence": str(form.get(f"{key}__confidence", "")),
                "basis": str(form.get(f"{key}__basis", "")),
            }
            for key in TRUTH_LABELS
        }
        try:
            content = TruthContent.model_validate(raw_content)
            update_draft(db, draft, content, str(form.get("change_note", "")))
        except ValidationError as exc:
            context = base_context(request, db, "truth")
            context.update(
                {
                    "draft": draft,
                    "errors": [error["msg"] for error in exc.errors()],
                    "form_content": raw_content,
                }
            )
            return templates.TemplateResponse(request, "truth/edit.html", context, status_code=422)
        except TruthConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RedirectResponse(f"/truth/versions/{draft.id}", status_code=303)

    @application.post("/truth/drafts/{truth_id}/approve")
    def approve(
        truth_id: str,
        request: Request,
        csrf: str = Form(...),
        db: Session = Depends(get_db),
    ):
        require_session(request, db)
        validate_csrf(request, csrf, settings)
        draft = db.get(TruthVersion, truth_id)
        if draft is None or draft.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Draft not found")
        try:
            approve_draft(db, draft)
        except TruthConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RedirectResponse(f"/truth/versions/{draft.id}?approved=1", status_code=303)

    @application.get("/truth/versions/{truth_id}", response_class=HTMLResponse)
    def truth_version_page(
        truth_id: str, request: Request, approved: int = 0, db: Session = Depends(get_db)
    ):
        require_session(request, db)
        truth = db.get(TruthVersion, truth_id)
        if truth is None or truth.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Truth version not found")
        context = base_context(request, db, "truth")
        context.update({"truth": truth, "just_approved": bool(approved)})
        return templates.TemplateResponse(request, "truth/version.html", context)

    @application.get("/radar", response_class=HTMLResponse)
    def radar_page(request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        context = base_context(request, db, "radar")
        context["signals"] = list(
            db.scalars(
                select(Signal)
                .where(Signal.product_id == context["product"].id)
                .order_by(Signal.updated_at.desc())
            )
        )
        return templates.TemplateResponse(request, "radar/index.html", context)

    @application.post("/radar/signals")
    async def new_signal(request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        try:
            create_signal(
                db,
                leasedesk(db).id,
                form_values(
                    form,
                    (
                        "source",
                        "evidence",
                        "url",
                        "audience",
                        "tension_pain",
                        "why_now",
                        "product_relevance",
                        "buying_trigger",
                        "half_life",
                    ),
                ),
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "radar", str(exc), "/radar")
        return RedirectResponse("/radar", status_code=303)

    @application.get("/radar/signals/{signal_id}/edit", response_class=HTMLResponse)
    def edit_signal_page(signal_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        signal = db.get(Signal, signal_id)
        if signal is None or signal.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Signal not found")
        context = base_context(request, db, "radar")
        context["signal"] = signal
        return templates.TemplateResponse(request, "radar/edit.html", context)

    @application.post("/radar/signals/{signal_id}")
    async def save_signal(signal_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        signal = db.get(Signal, signal_id)
        if signal is None or signal.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Signal not found")
        try:
            update_signal(
                db,
                signal,
                form_values(
                    form,
                    (
                        "source",
                        "evidence",
                        "url",
                        "audience",
                        "tension_pain",
                        "why_now",
                        "product_relevance",
                        "buying_trigger",
                        "half_life",
                    ),
                ),
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "radar", str(exc), f"/radar/signals/{signal_id}/edit")
        return RedirectResponse("/radar", status_code=303)

    @application.post("/radar/signals/{signal_id}/archive")
    def archive_signal_route(
        signal_id: str, request: Request, csrf: str = Form(...), db: Session = Depends(get_db)
    ):
        require_session(request, db)
        validate_csrf(request, csrf, settings)
        signal = db.get(Signal, signal_id)
        if signal is None or signal.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Signal not found")
        archive_signal(db, signal)
        return RedirectResponse("/radar", status_code=303)

    @application.post("/creative/runs")
    async def new_creative_run(request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        try:
            run = create_creative_run(
                db, leasedesk(db), [str(item) for item in form.getlist("signal_ids")]
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "radar", str(exc), "/radar")
        return RedirectResponse(f"/creative/runs/{run.id}", status_code=303)

    @application.get("/creative", response_class=HTMLResponse)
    def creative_page(request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        context = base_context(request, db, "creative")
        context["runs"] = active_runs(db, context["product"].id)
        context["learnings"] = list(
            db.scalars(
                select(Learning)
                .join(Experiment)
                .where(
                    Experiment.product_id == context["product"].id,
                    Learning.status == LearningStatus.APPROVED,
                )
            )
        )
        return templates.TemplateResponse(request, "creative/index.html", context)

    @application.get("/creative/runs/{run_id}", response_class=HTMLResponse)
    def creative_run_page(run_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        run = db.get(CreativeRun, run_id)
        if run is None or run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Creative run not found")
        context = base_context(request, db, "creative")
        executions = list(
            db.scalars(
                select(AIExecution)
                .where(AIExecution.origin_type == "creative_run", AIExecution.origin_id == run.id)
                .order_by(AIExecution.created_at.desc())
            )
        )
        context.update({"run": run, "concept_status": ConceptStatus, "executions": executions})
        return templates.TemplateResponse(request, "creative/run.html", context)

    @application.post("/creative/runs/{run_id}/generate")
    async def generate_run(run_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        run = db.get(CreativeRun, run_id)
        if run is None or run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Creative run not found")
        previous = list(
            db.scalars(
                select(AIExecution)
                .where(AIExecution.origin_type == "creative_run", AIExecution.origin_id == run.id)
                .order_by(AIExecution.created_at.desc())
            )
        )
        retry_index = len(previous)
        try:
            generate_collisions(db, settings, run, f"{run.id}:generate:{retry_index}")
        except (AIConfigurationError, AIExecutionConflictError, ValueError) as exc:
            return loop_error(request, db, "creative", str(exc), f"/creative/runs/{run_id}")
        return RedirectResponse(f"/creative/runs/{run_id}", status_code=303)

    @application.post("/creative/runs/{run_id}/concepts")
    async def new_concept(run_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        run = db.get(CreativeRun, run_id)
        if run is None or run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Creative run not found")
        try:
            save_concept(
                db,
                run,
                form_values(
                    form,
                    (
                        "tension",
                        "creative_mechanic",
                        "artifact",
                        "product_proof",
                        "participation",
                        "distribution",
                        "commercial_bridge",
                        "dangerous_assumption",
                    ),
                ),
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "creative", str(exc), f"/creative/runs/{run_id}")
        return RedirectResponse(f"/creative/runs/{run_id}", status_code=303)

    @application.get("/creative/concepts/{concept_id}/edit", response_class=HTMLResponse)
    def concept_edit_page(concept_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        concept = db.get(Concept, concept_id)
        if concept is None or concept.creative_run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Concept not found")
        context = base_context(request, db, "creative")
        context["concept"] = concept
        return templates.TemplateResponse(request, "creative/concept_edit.html", context)

    @application.post("/creative/concepts/{concept_id}")
    async def save_concept_route(concept_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        concept = db.get(Concept, concept_id)
        if concept is None or concept.creative_run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Concept not found")
        try:
            save_concept(
                db,
                concept.creative_run,
                form_values(
                    form,
                    (
                        "tension",
                        "creative_mechanic",
                        "artifact",
                        "product_proof",
                        "participation",
                        "distribution",
                        "commercial_bridge",
                        "dangerous_assumption",
                    ),
                ),
                concept,
            )
        except ManualLoopError as exc:
            return loop_error(
                request, db, "creative", str(exc), f"/creative/concepts/{concept_id}/edit"
            )
        return RedirectResponse(f"/creative/runs/{concept.creative_run_id}", status_code=303)

    @application.post("/creative/concepts/{concept_id}/shortlist")
    def shortlist_concept_route(
        concept_id: str, request: Request, csrf: str = Form(...), db: Session = Depends(get_db)
    ):
        require_session(request, db)
        validate_csrf(request, csrf, settings)
        concept = db.get(Concept, concept_id)
        if concept is None or concept.creative_run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Concept not found")
        try:
            shortlist_concept(db, concept)
        except ManualLoopError as exc:
            return loop_error(
                request, db, "creative", str(exc), f"/creative/runs/{concept.creative_run_id}"
            )
        return RedirectResponse(f"/creative/runs/{concept.creative_run_id}", status_code=303)

    @application.get("/creative/concepts/{concept_id}/challenge", response_class=HTMLResponse)
    def challenge_page(concept_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        concept = db.get(Concept, concept_id)
        if concept is None or concept.creative_run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Concept not found")
        context = base_context(request, db, "creative")
        context.update(
            {
                "concept": concept,
                "gate_names": GATE_NAMES,
                "recommendations": ChallengeRecommendation,
            }
        )
        return templates.TemplateResponse(request, "creative/challenge.html", context)

    @application.post("/creative/concepts/{concept_id}/challenge")
    async def save_challenge_route(
        concept_id: str, request: Request, db: Session = Depends(get_db)
    ):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        concept = db.get(Concept, concept_id)
        if concept is None or concept.creative_run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Concept not found")
        gates = {
            gate: {
                "verdict": str(form.get(f"gate_{index}", "")),
                "reasoning": str(form.get(f"reason_{index}", "")),
            }
            for index, gate in enumerate(GATE_NAMES)
        }
        try:
            save_challenge(
                db,
                concept,
                gates,
                form_values(
                    form,
                    (
                        "strongest_reason",
                        "strongest_objection",
                        "unsupported_claims",
                        "smallest_repair",
                        "recommendation",
                    ),
                ),
                form.get("unsupported_resolved") == "on",
            )
        except ManualLoopError as exc:
            return loop_error(
                request, db, "creative", str(exc), f"/creative/concepts/{concept_id}/challenge"
            )
        return RedirectResponse(f"/creative/runs/{concept.creative_run_id}", status_code=303)

    @application.post("/creative/concepts/{concept_id}/decision")
    async def concept_decision(concept_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        concept = db.get(Concept, concept_id)
        if concept is None or concept.creative_run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Concept not found")
        try:
            decide_concept(db, concept, str(form.get("decision", "")))
        except ManualLoopError as exc:
            return loop_error(
                request, db, "creative", str(exc), f"/creative/runs/{concept.creative_run_id}"
            )
        return RedirectResponse(f"/creative/runs/{concept.creative_run_id}", status_code=303)

    @application.post("/creative/runs/{run_id}/close")
    async def close_run_route(run_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        run = db.get(CreativeRun, run_id)
        if run is None or run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Creative run not found")
        try:
            close_creative_run(
                db, run, str(form.get("closure_learning", "")), form.get("abandoned") == "on"
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "creative", str(exc), f"/creative/runs/{run_id}")
        return RedirectResponse("/creative", status_code=303)

    @application.get("/experiments", response_class=HTMLResponse)
    def experiments_page(request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        context = base_context(request, db, "experiments")
        context["experiments"] = list(
            db.scalars(
                select(Experiment)
                .where(Experiment.product_id == context["product"].id)
                .order_by(Experiment.updated_at.desc())
            )
        )
        return templates.TemplateResponse(request, "experiments/index.html", context)

    @application.post("/experiments/from-concept/{concept_id}")
    def experiment_from_concept(
        concept_id: str, request: Request, csrf: str = Form(...), db: Session = Depends(get_db)
    ):
        require_session(request, db)
        validate_csrf(request, csrf, settings)
        concept = db.get(Concept, concept_id)
        if concept is None or concept.creative_run.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Concept not found")
        try:
            experiment = create_experiment(db, concept)
        except ManualLoopError as exc:
            return loop_error(
                request, db, "creative", str(exc), f"/creative/runs/{concept.creative_run_id}"
            )
        return RedirectResponse(f"/experiments/{experiment.id}", status_code=303)

    @application.get("/experiments/{experiment_id}", response_class=HTMLResponse)
    def experiment_detail(experiment_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        experiment = db.get(Experiment, experiment_id)
        if experiment is None or experiment.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Experiment not found")
        context = base_context(request, db, "experiments")
        context.update({"experiment": experiment, "statuses": ExperimentStatus})
        return templates.TemplateResponse(request, "experiments/detail.html", context)

    @application.post("/experiments/{experiment_id}")
    async def save_experiment(experiment_id: str, request: Request, db: Session = Depends(get_db)):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        experiment = db.get(Experiment, experiment_id)
        if experiment is None or experiment.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Experiment not found")
        try:
            update_experiment(
                db,
                experiment,
                form_values(
                    form,
                    (
                        "hypothesis",
                        "dangerous_assumption",
                        "smoke_test",
                        "seed_targets",
                        "product_magic_moment",
                        "measures",
                        "success_thresholds",
                        "test_window",
                        "execution_references",
                    ),
                ),
                form.get("thresholds_approved") == "on",
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "experiments", str(exc), f"/experiments/{experiment_id}")
        return RedirectResponse(f"/experiments/{experiment_id}", status_code=303)

    @application.post("/experiments/{experiment_id}/transition")
    async def experiment_transition(
        experiment_id: str, request: Request, db: Session = Depends(get_db)
    ):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        experiment = db.get(Experiment, experiment_id)
        if experiment is None or experiment.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Experiment not found")
        try:
            transition_experiment(db, experiment, str(form.get("target", "")))
        except ManualLoopError as exc:
            return loop_error(request, db, "experiments", str(exc), f"/experiments/{experiment_id}")
        return RedirectResponse(f"/experiments/{experiment_id}", status_code=303)

    @application.post("/experiments/{experiment_id}/results")
    async def experiment_results(
        experiment_id: str, request: Request, db: Session = Depends(get_db)
    ):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        experiment = db.get(Experiment, experiment_id)
        if experiment is None or experiment.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Experiment not found")
        try:
            save_results(
                db,
                experiment,
                str(form.get("observed_facts", "")),
                str(form.get("interpretation", "")),
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "experiments", str(exc), f"/experiments/{experiment_id}")
        return RedirectResponse(f"/experiments/{experiment_id}", status_code=303)

    @application.post("/experiments/{experiment_id}/decision")
    async def experiment_decision(
        experiment_id: str, request: Request, db: Session = Depends(get_db)
    ):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        experiment = db.get(Experiment, experiment_id)
        if experiment is None or experiment.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Experiment not found")
        try:
            finalize_experiment(
                db,
                experiment,
                str(form.get("decision", "")),
                str(form.get("reason", "")),
                str(form.get("postmortem", "")),
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "experiments", str(exc), f"/experiments/{experiment_id}")
        return RedirectResponse(f"/experiments/{experiment_id}", status_code=303)

    @application.post("/experiments/{experiment_id}/learning")
    async def experiment_learning(
        experiment_id: str, request: Request, db: Session = Depends(get_db)
    ):
        require_session(request, db)
        form = await request.form()
        validate_csrf(request, str(form.get("csrf", "")), settings)
        experiment = db.get(Experiment, experiment_id)
        if experiment is None or experiment.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Experiment not found")
        try:
            learning = save_learning(
                db, experiment, form_values(form, ("content", "confidence", "qualification"))
            )
        except ManualLoopError as exc:
            return loop_error(request, db, "experiments", str(exc), f"/experiments/{experiment_id}")
        return RedirectResponse(
            f"/experiments/{experiment_id}?learning={learning.id}", status_code=303
        )

    @application.post("/learnings/{learning_id}/approve")
    def approve_learning_route(
        learning_id: str, request: Request, csrf: str = Form(...), db: Session = Depends(get_db)
    ):
        require_session(request, db)
        validate_csrf(request, csrf, settings)
        learning = db.get(Learning, learning_id)
        if learning is None or learning.experiment.product_id != leasedesk(db).id:
            raise HTTPException(status_code=404, detail="Learning not found")
        try:
            approve_learning(db, learning)
        except ManualLoopError as exc:
            return loop_error(
                request, db, "experiments", str(exc), f"/experiments/{learning.experiment_id}"
            )
        return RedirectResponse(f"/experiments/{learning.experiment_id}", status_code=303)

    return application


app = create_app()
