import json
import shutil
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mealplan import build as b
from mealplan.config import Paths
from mealplan.generate import generate

NOW = datetime(2026, 10, 24, 6, 0, tzinfo=ZoneInfo("Australia/Melbourne"))


def _tmp_root(tmp_path, root_paths: Paths) -> Paths:
    shutil.copytree(root_paths.config_dir, tmp_path / "config")
    shutil.copytree(root_paths.cuisines_dir, tmp_path / "cuisines")
    return Paths(tmp_path)


def test_select_weeks_prefers_today_then_next(kerala, household):
    w44 = generate("2026-W44", [kerala], household, now=NOW)
    w45 = generate("2026-W45", [kerala], household, now=NOW)
    cur, nxt, embed = b.select_weeks([w44, w45], date(2026, 10, 28))
    assert (cur, nxt) == ("2026-W44", "2026-W45")
    assert [p.week for p in embed] == ["2026-W44", "2026-W45"]
    # Saturday before W44 starts: nothing current, W44 is "next", and it is what we show.
    cur, nxt, embed = b.select_weeks([w44, w45], date(2026, 10, 24))
    assert cur is None and nxt == "2026-W44"
    assert [p.week for p in embed] == ["2026-W44"]
    # Long after: most recent started plan is current.
    cur, nxt, embed = b.select_weeks([w44, w45], date(2026, 12, 1))
    assert cur == "2026-W45" and nxt is None


def test_render_inlines_json_and_escapes_script_close(root_paths):
    tpl = root_paths.template_file.read_text()
    html = b.render_page(tpl, {"version": "abc", "note": "</script>"})
    assert b.PLACEHOLDER not in html
    start = html.index('<script id="plan-data" type="application/json">') + len(
        '<script id="plan-data" type="application/json">'
    )
    end = html.index("</script>", start)
    blob = html[start:end]
    assert json.loads(blob) == {"version": "abc", "note": "</script>"}
    assert "<\\/script>" in blob


def test_build_is_deterministic_and_stale_check_works(tmp_path, root_paths, kerala, household):
    p = _tmp_root(tmp_path, root_paths)
    b.save_plan(p, generate("2026-W44", [kerala], household, now=NOW))
    html1, man1 = b.build(p, today=date(2026, 10, 27))
    html2, man2 = b.build(p, today=date(2026, 10, 27))
    assert html1 == html2 and man1 == man2
    assert p.index_html.exists() and p.manifest_file.exists()
    assert not b.is_stale(p, today=date(2026, 10, 27))
    b.save_plan(p, generate("2026-W45", [kerala], household, now=NOW))
    assert b.is_stale(p, today=date(2026, 10, 27))
    _, man3 = b.build(p, today=date(2026, 10, 27))
    assert man3["next"] == "2026-W45" and man3["version"] != man1["version"]
