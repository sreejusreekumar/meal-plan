"""Microsoft To Do via Microsoft Graph.

Auth mirrors shopping-assistant: MSAL device-code flow against the same public-client app
registration, refresh token cached in a file outside the repo (`MEALPLAN_MS_TOKEN_CACHE`,
default ~/.config/meal-plan/ms_token_cache.json, mode 600). `mealplan todo login` once; later
runs are silent.

Push semantics (ADR 0003): one dedicated list ("Weekly Basket"), created if missing. Every task
we create carries a marker `meal-plan:<week>` in its body. Before pushing, open tasks carrying
any `meal-plan:` marker are deleted; tasks the family typed by hand are never touched. Tasks are
created in reverse aisle order so the list reads top-to-bottom as the store walk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx

from mealplan.shopping import Line, ShoppingList, fmt_qty

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Tasks.ReadWrite"]
MARKER_PREFIX = "meal-plan:"


class NotLoggedIn(RuntimeError):
    pass


@dataclass(slots=True)
class TodoTask:
    id: str
    title: str
    status: str
    body: str = ""

    @property
    def is_open(self) -> bool:
        return self.status != "completed"

    @property
    def is_ours(self) -> bool:
        return MARKER_PREFIX in self.body


class TodoClient(Protocol):
    def find_or_create_list(self, name: str) -> str: ...
    def tasks(self, list_id: str) -> list[TodoTask]: ...
    def create_task(
        self, list_id: str, title: str, body: str, checklist: list[str] | None = None
    ) -> str: ...
    def delete_task(self, list_id: str, task_id: str) -> None: ...


def parse_task(raw: dict[str, Any]) -> TodoTask:
    body = ((raw.get("body") or {}).get("content") or "").strip()
    return TodoTask(
        id=raw["id"],
        title=(raw.get("title") or "").strip(),
        status=raw.get("status", ""),
        body=body,
    )


# --------------------------------------------------------------------------- real client


class GraphTodoClient:
    """Talks to Graph. `msal` is imported lazily so the rest of the CLI never needs it."""

    def __init__(
        self,
        client_id: str | None,
        tenant: str = "consumers",
        cache_path: Path | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        token: str | None = None,
    ) -> None:
        self.client_id = client_id
        self.tenant = tenant
        self.cache_path = (
            cache_path or Path.home() / ".config" / "meal-plan" / "ms_token_cache.json"
        )
        self._fixed_token = token
        self._app = None
        self._cache = None
        self.http = httpx.Client(base_url=GRAPH, timeout=timeout, transport=transport)

    # ---- auth
    def _msal(self):
        if self._app is None:
            if not self.client_id:
                raise NotLoggedIn("MEALPLAN_MS_CLIENT_ID is not set; see README → Microsoft To Do")
            import msal

            self._cache = msal.SerializableTokenCache()
            if self.cache_path.exists():
                self._cache.deserialize(self.cache_path.read_text())
            self._app = msal.PublicClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{self.tenant}",
                token_cache=self._cache,
            )
        return self._app

    def _save_cache(self) -> None:
        if self._cache is not None and self._cache.has_state_changed:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(self._cache.serialize())
            self.cache_path.chmod(0o600)

    def login(self, prompt=print) -> str:
        app = self._msal()
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow failed: {flow.get('error_description') or flow}")
        prompt(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(result.get("error_description") or "login failed")
        self._save_cache()
        return (result.get("id_token_claims") or {}).get("preferred_username", "signed in")

    def account(self) -> str | None:
        if self._fixed_token:
            return "token"
        accounts = self._msal().get_accounts()
        return accounts[0].get("username") if accounts else None

    def _token(self) -> str:
        if self._fixed_token:
            return self._fixed_token
        app = self._msal()
        accounts = app.get_accounts()
        result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
        self._save_cache()
        if not result or "access_token" not in result:
            raise NotLoggedIn("No cached Microsoft login; run `mealplan todo login` first")
        return result["access_token"]

    # ---- http with 429 back-off
    def _request(self, method: str, url: str, **kw: Any) -> httpx.Response:
        for attempt in range(5):
            resp = self.http.request(
                method, url, headers={"Authorization": f"Bearer {self._token()}"}, **kw
            )
            if resp.status_code in (429, 503) and attempt < 4:
                time.sleep(float(resp.headers.get("Retry-After", "2")))
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError("unreachable")

    def _get_all(self, url: str, **params: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        first = True
        while url:
            page = self._request("GET", url, params=params if first else None).json()
            first = False
            items.extend(page.get("value") or [])
            url = page.get("@odata.nextLink")
        return items

    # ---- To Do
    def lists(self) -> list[dict[str, Any]]:
        return self._get_all("/me/todo/lists")

    def find_or_create_list(self, name: str) -> str:
        for lst in self.lists():
            if (lst.get("displayName") or "").strip().lower() == name.strip().lower():
                return lst["id"]
        created = self._request("POST", "/me/todo/lists", json={"displayName": name}).json()
        return created["id"]

    def tasks(self, list_id: str) -> list[TodoTask]:
        raw = self._get_all(f"/me/todo/lists/{list_id}/tasks", **{"$top": 100})
        return [parse_task(t) for t in raw if t.get("id")]

    def create_task(
        self, list_id: str, title: str, body: str, checklist: list[str] | None = None
    ) -> str:
        payload: dict[str, Any] = {
            "title": title,
            "body": {"content": body, "contentType": "text"},
        }
        if checklist:
            payload["checklistItems"] = [{"displayName": c} for c in checklist]
        try:
            created = self._request("POST", f"/me/todo/lists/{list_id}/tasks", json=payload).json()
        except httpx.HTTPStatusError as exc:
            if not checklist or exc.response.status_code != 400:
                raise
            # Some tenants reject nested checklistItems on create: add them one by one.
            payload.pop("checklistItems")
            created = self._request("POST", f"/me/todo/lists/{list_id}/tasks", json=payload).json()
            for c in checklist:
                self._request(
                    "POST",
                    f"/me/todo/lists/{list_id}/tasks/{created['id']}/checklistItems",
                    json={"displayName": c},
                )
        return created["id"]

    def delete_task(self, list_id: str, task_id: str) -> None:
        self._request("DELETE", f"/me/todo/lists/{list_id}/tasks/{task_id}")


# --------------------------------------------------------------------------- push


@dataclass
class PushResult:
    list_name: str
    week: str
    removed: int = 0
    created: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "list": self.list_name,
            "week": self.week,
            "removed": self.removed,
            "created": len(self.created),
        }


def task_title(line: Line) -> str:
    return f"{line.item} — {fmt_qty(line.qty, line.unit)}"


def task_body(line: Line, week: str) -> str:
    uses = ", ".join(line.recipes[:6]) + (" …" if len(line.recipes) > 6 else "")
    return f"{line.aisle.title()} · used in: {uses} · {MARKER_PREFIX}{week}"


def push_shopping(client: TodoClient, sl: ShoppingList, list_name: str) -> PushResult:
    """Replace the planner's tasks in `list_name` with this week's list. Idempotent."""
    list_id = client.find_or_create_list(list_name)
    result = PushResult(list_name=list_name, week=sl.week)
    for task in client.tasks(list_id):
        if task.is_open and task.is_ours:
            client.delete_task(list_id, task.id)
            result.removed += 1
    marker = f"{MARKER_PREFIX}{sl.week}"
    # Newest tasks show first in To Do, so create the last aisle first and the pantry check
    # before everything; the list then reads produce → fish → … → pantry, top to bottom.
    if sl.pantry:
        items = [f"{line.item} — about {fmt_qty(line.qty, line.unit)}" for line in sl.pantry]
        client.create_task(
            list_id,
            f"Check pantry — {sl.week}",
            f"Staples this week's recipes use · {marker}",
            checklist=items,
        )
        result.created.append(f"Check pantry — {sl.week}")
    for line in reversed(sl.buy):
        title = task_title(line)
        client.create_task(list_id, title, task_body(line, sl.week))
        result.created.append(title)
    result.created.reverse()
    return result
