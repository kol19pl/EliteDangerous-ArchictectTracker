"""
RavenColonial — klient HTTP i modele danych w Pythonie.

Ten moduł zawiera uproszczony, bezstanowy klient do API RavenColonial
oraz podstawowe modele (dataclass). Kod ma na celu zachować czytelny
interfejs podobny do oryginału w C#, ułatwiając integrację z resztą
aplikacji.

- Główne zależności: `aiohttp` (asynchroniczne HTTP), `dataclasses` (modele),
  `json` do serializacji/deserializacji.
- Integracja z aplikacją hosta: jeśli w środowisku dostępny jest moduł
  `Game` lub `Program`, klient spróbuje użyć tamtejszych ustawień/logowania.

Dostosuj ścieżki i nagłówki w razie potrzeby.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import aiohttp

logger = logging.getLogger(__name__)


def _log(msg: str) -> None:
    """Loguje komunikaty — najpierw próbuje użyć `Game.log`, potem loggera.

    Dzięki temu integracja z hostem (aplikacją) jest bezbolesna,
    ale moduł nadal działa samodzielnie podczas testów.
    """
    try:
        from Game import log  # type: ignore

        log(msg)
    except Exception:
        logger.info(msg)


def _get_program_user_agent() -> str:
    """Pobiera nagłówek `User-Agent` z hosta (`Program.userAgent`) lub
    zwraca wartość domyślną.
    """
    try:
        from Program import userAgent  # type: ignore

        return userAgent
    except Exception:
        return "RavenColonial-Python/1.0"


DEFAULT_SVC_URI = "https://ravencolonial100-awcbdvabgze4c5cq.canadacentral-01.azurewebsites.net"
UX_URI = "https://ravencolonial.com"


@dataclass
class ColonyCost2:
    """Reprezentuje koszt kolonizacji jednego typu budowli.

    Pola odpowiadają strukturze JSON zwracanej przez serwis.
    """
    buildType: str
    category: str
    tier: int
    location: str
    displayName: str
    layouts: List[str]
    cargo: Dict[str, int]

    def __str__(self) -> str:
        return f"Tier {self.tier}: {self.displayName} ({', '.join(self.layouts)})"


@dataclass
class ProjectCore:
    """Wspólne pole dla definicji projektu (Project / Create / Update).

    Domyślne wartości są bezpieczne do tworzenia instancji bez pełnych danych
    i mogą być nadpisywane przez deserializację z JSON.
    """
    buildType: str = ""
    buildName: str = ""

    marketId: int = 0
    systemAddress: int = 0
    systemName: str = ""
    starPos: Optional[List[float]] = None
    bodyNum: Optional[int] = None
    bodyName: Optional[str] = None

    factionName: Optional[str] = None
    architectName: Optional[str] = None
    maxNeed: int = 0
    discordLink: Optional[str] = None
    isPrimaryPort: bool = False
    commanders: Dict[str, Set[str]] = field(default_factory=dict)

    notes: Optional[str] = None


@dataclass
class ProjectCreate(ProjectCore):
    """Model używany przy tworzeniu projektu (request do serwisu).

    Zawiera dodatkowe pole `systemSiteId` oraz mapę `commodities`.
    """
    systemSiteId: Optional[str] = None
    commodities: Dict[str, int] = field(default_factory=dict)
    colonisationConstructionDepot: Optional[Dict[str, Any]] = None


@dataclass
class Project(ProjectCore):
    """Model reprezentujący projekt pobrany z serwisu.

    Pola są zgodne z API RavenColonial; pola opcjonalne mogą być puste.
    """
    Timestamp: Optional[str] = None
    ETag: Optional[str] = None
    buildId: str = ""
    sumNeed: int = 0
    sumTotal: int = 0
    complete: bool = False
    commodities: Dict[str, int] = field(default_factory=dict)
    ready: Optional[Set[str]] = None
    linkedFC: Optional[List[Dict[str, Any]]] = None

    def __str__(self) -> str:
        return f"{self.systemName}: {self.buildName}"


@dataclass
class ProjectUpdate:
    buildId: str
    Timestamp: Optional[str] = None
    ETag: Optional[str] = None

    buildType: Optional[str] = None
    buildName: Optional[str] = None
    bodyNum: Optional[int] = None
    bodyName: Optional[str] = None
    factionName: Optional[str] = None
    architectName: Optional[str] = None
    notes: Optional[str] = None
    maxNeed: Optional[int] = None
    commodities: Optional[Dict[str, int]] = None
    colonisationConstructionDepot: Optional[Dict[str, Any]] = None


@dataclass
class FleetCarrier:
    """Prosty model floty (Fleet Carrier) z informacją o ładunku.

    Używany do odczytu / zapisu stanu FC w API.
    """
    marketId: int
    name: str
    displayName: str
    cargo: Dict[str, int]

    def __str__(self) -> str:
        return f"{self.displayName} - {self.name} ({self.marketId})"


class BodyFeature(Enum):
    bio = "bio"
    geo = "geo"
    rings = "rings"
    volcanism = "volcanism"
    terraformable = "terraformable"
    tidal = "tidal"
    landable = "landable"
    atmosphere = "atmosphere"


class RavenColonial:
    colonization_costs_path = os.path.join(os.getcwd(), "colonization-costs2.json")
    uxUri = UX_URI

    @property
    def svcUri(self) -> str:
        try:
            # prefer external Game.settings if available
            import Game  # type: ignore

            if getattr(Game, "settings", None) and getattr(Game.settings, "buildProjectsUrl_TEST", None):
                return Game.settings.buildProjectsUrl_TEST
        except Exception:
            pass

        # If a local development environment is detected via env var, prefer localhost
        if os.getenv("RAVEN_LOCAL") == "1":
            return "https://localhost:7007"

        return DEFAULT_SVC_URI

    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self) -> None:
        self._ensure_session()

    def _ensure_session(self) -> None:
        if RavenColonial._session is None:
            headers = {"user-agent": _get_program_user_agent()}
            RavenColonial._session = aiohttp.ClientSession(headers=headers)

    async def close(self) -> None:
        if RavenColonial._session:
            await RavenColonial._session.close()
            RavenColonial._session = None

    def loadDefaultCosts(self) -> List[ColonyCost2]:
        """Wczytuje lokalny plik `colonization-costs2.json` i zwraca listę kosztów.

        Jeśli plik nie istnieje lub nie można go odczytać, zwraca pustą listę
        i loguje błąd.
        """
        try:
            with open(self.colonization_costs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [ColonyCost2(**d) for d in data]
        except Exception as ex:
            _log(f"loadDefaultCosts failed: {ex}")
            return []

    async def create(self, row: ProjectCreate) -> Optional[Dict[str, Any]]:
        """Utwórz nowy projekt na serwisie RavenColonial.

        Zwraca słownik z obiektem projektu przy sukcesie, w przeciwnym wypadku
        `None` i loguje odpowiedź serwera.
        """
        json1 = json.dumps(asdict(row))
        _log(f"RCC.create:\r\n{json1}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/"
        async with RavenColonial._session.put(url, data=json1.encode("utf-8"), headers={"Content-Type": "application/json"}) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            text = await resp.text()
            if resp.status == 200:
                return json.loads(text)
            else:
                _log(f"RCC.create: failed:\n\t{text}")
                return None

    async def updateProject(self, row: ProjectUpdate) -> Optional[Dict[str, Any]]:
        _log(f"RCC.update: {row}")
        json1 = json.dumps(asdict(row))
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{aiohttp.helpers.quote(row.buildId, safe='')}"
        async with RavenColonial._session.post(url, data=json1.encode("utf-8"), headers={"Content-Type": "application/json"}) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            text = await resp.text()
            if not resp.status == 200:
                _log(f"RCC.updateProject '{row.buildId}' failed: HTTP:{resp.status}: {text}")
            try:
                return json.loads(text)
            except Exception:
                return None

    async def markComplete(self, buildId: str) -> None:
        _log(f"RCC.markComplete: {buildId}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{aiohttp.helpers.quote(buildId, safe='')}/complete"
        async with RavenColonial._session.post(url) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            await resp.text()

    async def linkCmdr(self, buildId: str, cmdr: str) -> None:
        _log(f"RCC.link: {cmdr} => {buildId}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{aiohttp.helpers.quote(buildId, safe='')}/link/{aiohttp.helpers.quote(cmdr, safe='')}"
        async with RavenColonial._session.put(url) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            await resp.text()

    async def unlinkCmdr(self, buildId: str, cmdr: str) -> None:
        _log(f"RCC.unlink: {cmdr} => {buildId}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{aiohttp.helpers.quote(buildId, safe='')}/link/{aiohttp.helpers.quote(cmdr, safe='')}"
        async with RavenColonial._session.delete(url) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            await resp.text()

    async def assign(self, buildId: str, cmdr: str, commodity: str) -> None:
        _log(f"RCC.assign: {cmdr} => {commodity}=> {buildId}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{aiohttp.helpers.quote(buildId, safe='')}/assign/{aiohttp.helpers.quote(cmdr, safe='')}/{aiohttp.helpers.quote(commodity, safe='')}"
        async with RavenColonial._session.put(url) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            txt = await resp.text()
            _log(f"{txt}")

    async def unAssign(self, buildId: str, cmdr: str, commodity: str) -> None:
        _log(f"RCC.unAssign: {cmdr} => {commodity}=> {buildId}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{aiohttp.helpers.quote(buildId, safe='')}/assign/{aiohttp.helpers.quote(cmdr, safe='')}/{aiohttp.helpers.quote(commodity, safe='')}"
        async with RavenColonial._session.delete(url) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            txt = await resp.text()
            _log(f"{txt}")

    async def load(self, id64: int, marketId: int) -> Optional[Dict[str, Any]]:
        _log(f"RCC.load: {id64}/{marketId}")
        try:
            url = f"{self.svcUri}/api/system/{id64}/{marketId}"
            _log(f"RCC.load: {url}")
            assert RavenColonial._session
            async with RavenColonial._session.get(url) as resp:
                if resp.status == 404:
                    return None
                text = await resp.text()
                if not text:
                    return None
                return json.loads(text)
        except Exception as ex:
            _log(f"RCC.load exception: {ex}")
            return None

    async def contribute(self, buildId: str, cmdr: str, diff: Dict[str, int]) -> None:
        _log(f"{diff} -> RCC.contribute: {buildId}")
        json1 = json.dumps(diff)
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{buildId}/contribute/{aiohttp.helpers.quote(cmdr, safe='')}"
        async with RavenColonial._session.post(url, data=json1.encode("utf-8"), headers={"Content-Type": "application/json"}) as resp:
            _log(f"RCC.contribute: HTTP:{resp.status}({resp.reason})")

    async def supplyFC(self, marketId: int, cargo: Any, delta: Optional[int] = None) -> Dict[str, int]:
        """Zaktualizuj zapas cargo Fleet Carrier na serwerze.

        Przyjmuje albo `(marketId, cargo_str, delta)` albo `(marketId, diff_dict)`.
        Zwraca zserializowany słownik z nowym stanem cargo.
        """
        # cargo może być stringiem (pojedynczy rodzaj + delta) lub dict'em
        if isinstance(cargo, str) and delta is not None:
            diff = {cargo: delta}
        elif isinstance(cargo, dict):
            diff = cargo
        else:
            raise ValueError("supplyFC expects (marketId, cargo:str, delta:int) or (marketId, diff:dict)")

        _log(f"RCC.supplyFC: {marketId} -> {diff}")
        json1 = json.dumps(diff)
        assert RavenColonial._session
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        try:
            import Game  # type: ignore
            if getattr(Game.activeGame, "cmdr", None) and getattr(Game.activeGame.cmdr, "rccApiKey", None):
                headers["rcc-key"] = Game.activeGame.cmdr.rccApiKey
        except Exception:
            pass

        url = f"{self.svcUri}/api/fc/{marketId}/cargo"
        async with RavenColonial._session.patch(url, data=json1.encode("utf-8"), headers=headers) as resp:
            _log(f"RCC.supplyFC: HTTP:{resp.status}({resp.reason})")
            text = await resp.text()
            return json.loads(text)

    async def updateCargoFC(self, marketId: int, cargo: Dict[str, int]) -> Optional[Dict[str, int]]:
        _log(f"RCC.updateCargoFC: {marketId} -> {cargo}")
        json1 = json.dumps(cargo)
        assert RavenColonial._session
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        try:
            import Game  # type: ignore
            if getattr(Game.activeGame, "cmdr", None) and getattr(Game.activeGame.cmdr, "rccApiKey", None):
                headers["rcc-key"] = Game.activeGame.cmdr.rccApiKey
        except Exception:
            pass

        url = f"{self.svcUri}/api/fc/{marketId}/cargo"
        async with RavenColonial._session.post(url, data=json1.encode("utf-8"), headers=headers) as resp:
            _log(f"HTTP:{resp.status}({resp.reason})")
            text = await resp.text()
            if not (200 <= resp.status < 300):
                _log(f"RCC.updateCargoFC: '{marketId}' failed: HTTP:{resp.status}: {text}")
                return None
            return json.loads(text)

    async def getFC(self, marketId: int) -> Optional[Dict[str, Any]]:
        _log(f"RCC.getFC: {marketId}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/fc/{marketId}"
        async with RavenColonial._session.get(url) as resp:
            text = await resp.text()
            if not (200 <= resp.status < 300):
                _log(f"RCC.getFC: HTTP:{resp.status}({resp.reason}): failed: {text}")
                return None
            return json.loads(text)

    async def publishFC(self, fc: FleetCarrier) -> Optional[Dict[str, Any]]:
        _log(f"RCC.updateFleetCarrier: {fc}")
        json1 = json.dumps(asdict(fc))
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        try:
            import Game  # type: ignore
            if getattr(Game, "activeGame", None) and getattr(Game.activeGame, "Commander", None):
                headers["rcc-cmdr"] = Game.activeGame.Commander
            if getattr(Game.activeGame, "cmdr", None) and getattr(Game.activeGame.cmdr, "rccApiKey", None):
                headers["rcc-key"] = Game.activeGame.cmdr.rccApiKey
        except Exception:
            pass

        assert RavenColonial._session
        url = f"{self.svcUri}/api/fc/{fc.marketId}"
        async with RavenColonial._session.put(url, data=json1.encode("utf-8"), headers=headers) as resp:
            text = await resp.text()
            if not (200 <= resp.status < 300):
                _log(f"RCC.updateFleetCarrier: HTTP:{resp.status}({resp.reason}): failed: {text}")
                return None
            return json.loads(text)

    # Pozostałe metody (getAllCmdrFCs, getProject, getCmdrProjects, itp.)
    # są analogiczne do powyższych: robią żądanie HTTP i zwracają JSON jako dict/list.
    # Dla zwięzłości implementuję kilka ważnych przykładów, resztę można dodać
    # według tego wzorca jeśli chcesz.

    async def getProject(self, buildId: str) -> Optional[Dict[str, Any]]:
        _log(f"RCC.getProject: {buildId}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/project/{aiohttp.helpers.quote(buildId, safe='')}"
        async with RavenColonial._session.get(url) as resp:
            text = await resp.text()
            if resp.status == 200:
                return json.loads(text)
            else:
                _log(f"RCC.getProject: failed:\n\t{text}")
                return None

    async def getCmdrProjects(self, cmdr: str) -> List[Dict[str, Any]]:
        _log(f"RCC.getCmdrProjects: {cmdr}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/cmdr/{aiohttp.helpers.quote(cmdr, safe='')}"
        async with RavenColonial._session.get(url) as resp:
            text = await resp.text()
            return json.loads(text)

    async def getPrimary(self, cmdr: str) -> Optional[str]:
        _log(f"RCC.getPrimary: {cmdr}")
        assert RavenColonial._session
        url = f"{self.svcUri}/api/cmdr/{aiohttp.helpers.quote(cmdr, safe='')}/primary"
        async with RavenColonial._session.get(url) as resp:
            text = await resp.text()
            if resp.status == 200:
                return json.loads(text)
            return None


__all__ = ["RavenColonial", "ColonyCost2", "ProjectCreate", "Project", "ProjectUpdate", "FleetCarrier"]
