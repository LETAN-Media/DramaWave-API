import logging
import asyncio
from typing import Any, Optional, Dict
from curl_cffi.requests import AsyncSession, Response
from pydantic import BaseModel

logger = logging.getLogger('dramawave-api.providers.http')

class HTTPError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class ProviderSession:
    """A resilient HTTP session for providers with timeout, retry, and circuit breaker."""
    def __init__(
        self, 
        impersonate: str = "chrome", 
        timeout: int = 15, 
        max_retries: int = 2,
        cooldown: int = 60,
        name: str = "provider"
    ):
        self.impersonate = impersonate
        self.timeout = timeout
        self.max_retries = max_retries
        self.name = name
        
        self.cooldown = cooldown
        self.circuit_broken_until: float = 0
        self._session: Optional[AsyncSession] = None
        
    async def get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(impersonate=self.impersonate, timeout=self.timeout)
        return self._session
        
    def _check_circuit(self):
        if asyncio.get_event_loop().time() < self.circuit_broken_until:
            raise HTTPError(f"Circuit broken for {self.name}", 429)

    def _break_circuit(self):
        logger.warning(f"Circuit broken for {self.name} for {self.cooldown} seconds")
        self.circuit_broken_until = asyncio.get_event_loop().time() + self.cooldown

    async def request(
        self, 
        method: str, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        data: Optional[Any] = None, 
        json_data: Optional[Any] = None
    ) -> Response:
        self._check_circuit()
        session = await self.get_session()
        
        for attempt in range(self.max_retries + 1):
            try:
                if method.upper() == 'GET':
                    resp = await session.get(url, headers=headers)
                elif method.upper() == 'POST':
                    resp = await session.post(url, headers=headers, data=data, json=json_data)
                else:
                    resp = await session.request(method, url, headers=headers, data=data, json=json_data)
                    
                if resp.status_code in (429, 403, 500, 502, 503, 504):
                    if resp.status_code in (429, 403):
                        self._break_circuit()
                        raise HTTPError(f"{self.name} returned {resp.status_code}", resp.status_code)
                    if attempt < self.max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                        
                resp.raise_for_status()
                return resp
            except HTTPError:
                raise
            except Exception as e:
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.error(f"Request failed for {self.name}: {url} - {str(e)}")
                raise HTTPError(f"Request failed: {str(e)}")
        
        raise HTTPError(f"Max retries exceeded for {self.name}")

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

