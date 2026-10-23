import json

import httpx

from mealplan.integrations.mstodo import (
    GraphTodoClient,
    TodoTask,
    parse_task,
    push_shopping,
    task_body,
    task_title,
)
from mealplan.shopping import Line, ShoppingList


def line(item, qty, unit, aisle, staple=False, recipes=("A",)):
    return Line(
        item=item, qty=qty, exact=qty, unit=unit, aisle=aisle, staple=staple, recipes=list(recipes)
    )


SL = ShoppingList(
    week="2026-W44",
    servings=4.59,
    buy=[
        line("tomato", 19, "pc", "produce", recipes=("Rasam", "Egg Roast")),
        line("sardines (mathi)", 14, "pc", "fish"),
        line("matta rice", 1500, "g", "grains"),
    ],
    pantry=[
        line("salt", 81, "tsp", "pantry", staple=True),
        line("curry leaves", 166, "sprig", "produce", staple=True),
    ],
)


class FakeClient:
    def __init__(self, existing):
        self.lists = {"Weekly Basket": "L1"}
        self.tasks_by_list = {"L1": list(existing)}
        self.created = []
        self.deleted = []

    def find_or_create_list(self, name):
        return self.lists.setdefault(name, f"L{len(self.lists) + 1}")

    def tasks(self, list_id):
        return self.tasks_by_list.get(list_id, [])

    def create_task(self, list_id, title, body, checklist=None):
        self.created.append((title, body, checklist))
        return f"T{len(self.created)}"

    def delete_task(self, list_id, task_id):
        self.deleted.append(task_id)


def test_push_replaces_only_our_open_tasks_and_orders_for_the_store_walk():
    existing = [
        TodoTask("old1", "onion — 3 pcs", "notStarted", "Produce · meal-plan:2026-W43"),
        TodoTask("done", "eggs — 12 pcs", "completed", "Dairy · meal-plan:2026-W43"),
        TodoTask("hand", "birthday candles", "notStarted", ""),
    ]
    client = FakeClient(existing)
    result = push_shopping(client, SL, "Weekly Basket")
    assert client.deleted == ["old1"], "only our open task is removed"
    assert result.removed == 1
    titles = [t for t, _, _ in client.created]
    # created newest-first-friendly: pantry first, then last aisle ... first aisle
    assert titles == [
        "Check pantry — 2026-W44",
        "matta rice — 1.5 kg",
        "sardines (mathi) — 14 pcs",
        "tomato — 19 pcs",
    ]
    assert result.created[0] == "tomato — 19 pcs"
    pantry = client.created[0]
    assert pantry[2] == ["salt — about 81 tsp", "curry leaves — about 166 sprigs"]
    assert "meal-plan:2026-W44" in pantry[1]
    assert (
        task_body(SL.buy[0], "2026-W44")
        == "Produce · used in: Rasam, Egg Roast · meal-plan:2026-W44"
    )
    assert task_title(SL.buy[2]) == "matta rice — 1.5 kg"


def test_push_creates_list_when_missing():
    client = FakeClient([])
    push_shopping(client, SL, "Another List")
    assert "Another List" in client.lists


def test_parse_task_and_marker():
    t = parse_task(
        {
            "id": "x",
            "title": " tomato ",
            "status": "notStarted",
            "body": {"content": "p · meal-plan:2026-W44"},
        }
    )
    assert t.title == "tomato" and t.is_open and t.is_ours
    assert not parse_task({"id": "y", "title": "t", "status": "completed"}).is_ours


def test_graph_client_paths_and_pagination():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.url.query.decode()))
        assert request.headers["Authorization"] == "Bearer tok"
        if request.url.path == "/v1.0/me/todo/lists" and request.method == "GET":
            return httpx.Response(200, json={"value": [{"id": "L1", "displayName": "Groceries"}]})
        if request.url.path == "/v1.0/me/todo/lists" and request.method == "POST":
            assert json.loads(request.content) == {"displayName": "Weekly Basket"}
            return httpx.Response(201, json={"id": "L9", "displayName": "Weekly Basket"})
        if request.url.path == "/v1.0/me/todo/lists/L9/tasks" and request.method == "GET":
            if "skip" in request.url.query.decode():
                return httpx.Response(
                    200, json={"value": [{"id": "t2", "title": "b", "status": "notStarted"}]}
                )
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "t1", "title": "a", "status": "completed"}],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/todo/lists/L9/tasks?skip=1",
                },
            )
        if request.url.path == "/v1.0/me/todo/lists/L9/tasks" and request.method == "POST":
            body = json.loads(request.content)
            assert body["body"]["contentType"] == "text"
            return httpx.Response(201, json={"id": "new", **body})
        if request.url.path == "/v1.0/me/todo/lists/L9/tasks/t2" and request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404)

    client = GraphTodoClient(None, transport=httpx.MockTransport(handler), token="tok")
    assert client.find_or_create_list("Weekly Basket") == "L9"
    tasks = client.tasks("L9")
    assert [t.id for t in tasks] == ["t1", "t2"]
    assert client.create_task("L9", "x — 1 pc", "body", checklist=["a", "b"]) == "new"
    client.delete_task("L9", "t2")
    assert ("DELETE", "/v1.0/me/todo/lists/L9/tasks/t2", "") in calls
