from session import SharedSession
import httpx


async def send(event, config):
    session = await SharedSession.get_session()
    payload = event.model_dump(exclude_none=True, by_alias=True)
    async with session.post(
        f"{config.base_url}/events", json=payload,
        headers={"Authorization": "Bearer SYNTHETIC_SECRET_MUST_NOT_APPEAR"},
    ) as response:
        return await response.json()


def direct():
    return httpx.get("https://example.invalid/widgets?token=SYNTHETIC_QUERY_MUST_NOT_APPEAR")


def sensitive_url():
    return httpx.get("https://user:SYNTHETIC_PASSWORD_MUST_NOT_APPEAR@example.invalid/widgets")


def unrelated(mapping):
    return mapping.get("not-an-http-call")
