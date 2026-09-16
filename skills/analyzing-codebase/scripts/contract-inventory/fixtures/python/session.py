import aiohttp


class SharedSession:
    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        return aiohttp.ClientSession()
