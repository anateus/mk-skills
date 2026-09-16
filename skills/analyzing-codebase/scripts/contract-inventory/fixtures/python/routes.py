from fastapi import APIRouter
from models import StartRequest, StartResponse

router = APIRouter(prefix="/calls")
unmounted = APIRouter(prefix="/legacy")
conditional = APIRouter(prefix="/conditional")


@router.post("/start", status_code=202, response_model_exclude_none=True)
async def start(request: StartRequest) -> StartResponse:
    return StartResponse(accepted=True)


@unmounted.get("/unused")
async def unused() -> dict[str, str]:
    return {}


@router.get(dynamic_path)
async def dynamic() -> StartResponse:
    return StartResponse(accepted=True)


@router.get("/dual", response_model=StartRequest)
@router.post("/dual", response_model=StartResponse)
async def dual():
    return {}


@conditional.get("/candidate")
async def conditional_candidate() -> StartResponse:
    return StartResponse(accepted=True)
