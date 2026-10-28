"""Isolated regressions for the discovery / personal-list / interaction tools."""
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_sugar_bili_scroll_tasks import host  # noqa: F401


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "sugar-bili-scroll"
BV1 = "BV1aEnA6JECB"
BV2 = "BV19Rn26CExe"


@pytest.fixture
def client(monkeypatch):
    name = "test_sugar_bili_scroll_client"
    spec = importlib.util.spec_from_file_location(name, PLUGIN_ROOT / "bili_client.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "get_cred", lambda home: SimpleNamespace(dedeuserid="9"))
    return module


def archive(bvid, **extra):
    row = {"bvid": bvid, "aid": 1, "title": "标题", "owner": {"mid": 9, "name": "UP"},
           "duration": 100, "pubdate": 17, "stat": {"view": 5, "like": 2, "danmaku": 1}}
    row.update(extra)
    return row


def test_resolve_bvid_accepts_every_shape_users_paste(client, monkeypatch):
    async def get_info():
        return {"bvid": BV2}

    monkeypatch.setattr(client.video, "Video", lambda *args, **kwargs: SimpleNamespace(get_info=get_info))
    async def follow(url):
        return BV2

    monkeypatch.setattr(client, "_follow_short_link", follow)

    assert asyncio.run(client.resolve_bvid(BV1))["bvid"] == BV1
    url = f"https://www.bilibili.com/video/{BV1}/?p=3&spm_id_from=x"
    assert asyncio.run(client.resolve_bvid(url)) == {"ok": True, "bvid": BV1, "page": 3, "how": "bvid"}
    assert asyncio.run(client.resolve_bvid("av170001"))["bvid"] == BV2
    assert asyncio.run(client.resolve_bvid("https://b23.tv/abcd"))["bvid"] == BV2
    assert asyncio.run(client.resolve_bvid("随便一句话"))["ok"] is False
    assert asyncio.run(client.resolve_bvid(""))["ok"] is False


def test_discover_normalizes_each_source(client, monkeypatch):
    async def hot_videos(pn=1, ps=20):
        return {"list": [archive(BV1)]}

    async def weekly(week=1):
        return {"list": [archive(BV2)]}

    async def rank_list(_type):
        return {"list": [archive(BV1, score=999)]}

    async def up_videos(pn=1, ps=30, **kwargs):
        return {"list": {"vlist": [{"bvid": BV2, "author": "UP", "created": 3, "play": 7}]}}

    async def feed(cred, _type=None, pn=1):
        return {"items": [
            {"modules": {"module_dynamic": {"major": {"archive": archive(BV1)}},
                         "module_author": {"pub_time": "10-01 12:00"}}},
            {"modules": {"module_dynamic": {"major": {"opus": {"title": "图文"}}}}},
        ]}

    async def related():
        return [archive(BV2)]  # 17.4.2 直接返回 list

    monkeypatch.setattr(client.hot, "get_hot_videos", hot_videos)
    monkeypatch.setattr(client.hot, "get_weekly_hot_videos", weekly)
    monkeypatch.setattr(client.rank, "get_rank", rank_list)
    monkeypatch.setattr(client.user, "User", lambda mid, credential=None: SimpleNamespace(get_videos=up_videos))
    monkeypatch.setattr(client.dynamic, "get_dynamic_page_info", feed)
    monkeypatch.setattr(client.video, "Video", lambda *a, **k: SimpleNamespace(get_related=related))

    hot = asyncio.run(client.discover("home", "hot", 10))
    assert hot["videos"][0]["bvid"] == BV1 and hot["videos"][0]["author"] == "UP"
    assert hot["videos"][0]["url"].endswith(BV1)

    assert asyncio.run(client.discover("home", "weekly"))["videos"][0]["bvid"] == BV2
    ranked = asyncio.run(client.discover("home", "rank", 5, "technology"))
    assert ranked["tid"] == "technology" and ranked["videos"][0]["score"] == 999
    assert asyncio.run(client.discover("home", "up", 5, mid=9))["videos"][0]["view"] == 7
    assert asyncio.run(client.discover("home", "up", 5))["ok"] is False
    feed_out = asyncio.run(client.discover("home", "feed"))
    assert feed_out["count"] == 1 and feed_out["skipped"] == 1 and feed_out["videos"][0]["published"] == "10-01 12:00"
    assert asyncio.run(client.discover("home", "related", 5, bvid=BV1))["videos"][0]["bvid"] == BV2
    assert asyncio.run(client.discover("home", "nope"))["ok"] is False


def test_my_list_reads_toview_favorites_and_history(client, monkeypatch):
    async def toview(cred):
        return {"count": 2, "list": [archive(BV1)]}

    async def content(media_id, page=1, credential=None):
        assert media_id == 42
        return {"medias": [archive(BV2)], "info": {"title": "夹子", "media_count": 3}, "has_more": True}

    async def history(cred, ps=20):
        return {"list": [{"title": "看过的", "uri": f"https://www.bilibili.com/video/{BV1}",
                          "history": {"oid": 11, "business": "archive"}, "duration": 60,
                          "progress": 30, "is_finish": False, "view_at": 111, "author_name": "UP"}]}

    monkeypatch.setattr(client.user, "get_toview_list", toview)
    monkeypatch.setattr(client.favorite_list, "get_video_favorite_list_content", content)
    monkeypatch.setattr(client.user, "get_self_history_new", history)

    out = asyncio.run(client.my_list("home", "toview"))
    assert out["total"] == 2 and out["videos"][0]["bvid"] == BV1
    fav = asyncio.run(client.my_list("home", "favorites", 42))
    assert fav["title"] == "夹子" and fav["has_more"] is True
    assert asyncio.run(client.my_list("home", "favorites"))["ok"] is False
    hist = asyncio.run(client.my_list("home", "history"))["videos"][0]
    assert hist["bvid"] == BV1 and hist["progress"] == 30 and hist["finished"] is False
    assert asyncio.run(client.my_list("home", "nope"))["ok"] is False


def test_highlights_buckets_danmaku_by_window(client, monkeypatch):
    marks = [SimpleNamespace(dm_time=1.0, text="a"), SimpleNamespace(dm_time=2.0, text="b"),
             SimpleNamespace(dm_time=35.0, text="c"), SimpleNamespace(dm_time=36.0, text="d"),
             SimpleNamespace(dm_time=37.0, text="e")]

    async def get_info():
        return {"title": "标题", "duration": 60}

    async def get_danmakus(page_index=0):
        return marks if page_index == 0 else []

    monkeypatch.setattr(client.video, "Video",
                        lambda *a, **k: SimpleNamespace(get_info=get_info, get_danmakus=get_danmakus))

    out = asyncio.run(client.highlights("home", BV1, 30, 2))
    assert out["total_danmaku"] == 5
    assert out["highlights"][0] == {"at": 30, "clock": "0:30", "count": 3, "samples": ["c", "d", "e"]}
    assert out["highlights"][1]["count"] == 2


def test_watch_later_and_interact_report_failures_as_failures(client, monkeypatch):
    class Boom(Exception):
        pass

    async def get_info():
        return {"title": "标题"}

    async def add():
        return {"code": 0}

    async def like(status=True):
        if status:
            return {"code": 0}
        raise Boom("风控")

    monkeypatch.setattr(client.video, "Video",
                        lambda *a, **k: SimpleNamespace(get_info=get_info, add_to_toview=add, like=like))
    assert asyncio.run(client.watch_later_add("home", BV1))["ok"] is True
    failed = asyncio.run(client.interact("home", "unlike", BV1))
    assert failed["ok"] is False and failed["uncertain"] is True
    assert asyncio.run(client.interact("home", "like"))["ok"] is False
    assert asyncio.run(client.interact("home", "dance", BV1))["ok"] is False


def test_interactions_are_closed_by_default_and_quota_limited(host, monkeypatch):
    flow = host._flow()
    row = host.tasks_mod.new_row()
    host.tasks_mod.save(host._home(), [row])
    run_id = "bili-duty-interact"
    flow.store.start_run(run_id, "s1", {"mode": "duty", "task_id": row["id"]})
    ctx = SimpleNamespace(run_id=run_id, session_id="s1")

    monkeypatch.setattr(host, "_settings", lambda *args: {"allow_like": False, "allow_coin": True,
                                                          "coin_per_round": 1, "allow_toview": False})
    with pytest.raises(ValueError, match="没开"):
        flow.authorize(ctx, "bili_interact", {"action": "like", "bvid": BV1})
    with pytest.raises(ValueError, match="无权使用|没开"):
        flow.authorize(ctx, "bili_watch_later_add", {"bvid": BV1})

    # 值班任务没记录挑中的视频，不能投币
    with pytest.raises(ValueError, match="先用 bili_record_video"):
        flow.authorize(ctx, "bili_interact", {"action": "coin", "bvid": BV1, "num": 1})

    assert flow.record({"mode": "duty", "task_id": row["id"]}, {"bvid": BV1, "picked": True, "reason": "值得"})["ok"]
    assert flow.authorize(ctx, "bili_interact", {"action": "coin", "bvid": BV1, "num": 2})[2]["num"] == 2
    with pytest.raises(ValueError, match="投币次数已用完"):
        flow.authorize(ctx, "bili_interact", {"action": "coin", "bvid": BV1})


def test_catalog_publishes_new_tools_with_the_right_effects(host):
    rows = {row[0]["function"]["name"]: row for row in host.mcp_tool_rows()}
    assert len(rows) == 22
    for name in ("bili_discover", "bili_my_list", "bili_highlights", "bili_capabilities"):
        assert rows[name][2] == "read"
    for name in ("bili_watch_later_add", "bili_interact"):
        assert rows[name][2] == "external_write"
    for name in ("bili_cover", "bili_frame"):
        assert rows[name][2] == "workspace_write"
    assert rows["bili_discover"][0]["function"]["parameters"]["required"] == ["source"]
    assert rows["bili_my_list"][0]["function"]["parameters"]["properties"]["kind"]["enum"] == [
        "toview", "favorites", "history"]


def test_tool_arguments_resolve_links_before_permission_checks(host, monkeypatch):
    async def resolve(raw, data_dir=None):
        return {"ok": True, "bvid": BV2, "page": 0, "how": "short_link"}

    monkeypatch.setattr(host, "bili_client", SimpleNamespace(resolve_bvid=resolve))
    args = asyncio.run(host._normalized_arguments({"bvid": "https://b23.tv/xyz"}))
    assert args["bvid"] == BV2
    plain = asyncio.run(host._normalized_arguments({"bvid": BV1}))
    assert plain["bvid"] == BV1

    async def bad(raw, data_dir=None):
        return {"ok": False, "error": "认不出这个视频标识"}

    monkeypatch.setattr(host, "bili_client", SimpleNamespace(resolve_bvid=bad))
    with pytest.raises(ValueError, match="认不出"):
        asyncio.run(host._normalized_arguments({"bvid": "???"}))


def test_capabilities_reports_switches_and_scope(host, monkeypatch):
    monkeypatch.setattr(host, "_settings", lambda *args: {"allow_like": True, "auto_comment": False,
                                                          "dm_mode": "off", "fav_folder_id": 7})
    flow = host._flow()
    out = host._capabilities({"mode": "manual"}, host._settings())
    assert out["can"]["like"] is True and out["can"]["comment"] is False
    assert out["can"]["favorite_folder"] == 7
    assert "bili_discover" in out["tools"] and "bili_interact" in out["tools"]
    assert "bili_reply" not in out["tools"]
    assert flow.allowed({"mode": "manual"})  # 只读工具永远在名单里


def test_video_info_reports_tags_pages_and_optional_detail(client, monkeypatch):
    class Handle:
        async def get_info(self):
            return {"bvid": BV1, "aid": 1, "cid": 42, "title": "标题", "desc": "简介",
                    "owner": {"mid": 7, "name": "UP"}, "duration": 100, "pubdate": 17,
                    "tname": "科技", "dimension": {"width": 1920, "height": 1080},
                    "pic": "http://i0.hdslb.com/a.jpg",
                    "pages": [{"page": 1, "cid": 42, "part": "P1", "duration": 60},
                              {"page": 2, "cid": 43, "part": "P2", "duration": 40}],
                    "stat": {"view": 9, "like": 3}}

        async def get_tags(self):
            return [{"tag_name": "旅行"}, {"tag_name": "记录"}]

        async def get_online(self):
            return {"count": 12, "total": 100}

        async def get_ai_conclusion(self, cid=None):
            return {"model_result": {"summary": "一段摘要",
                                     "outline": [{"title": "开头", "timestamp": 0}]}}

    monkeypatch.setattr(client.video, "Video", lambda *a, **k: Handle())
    plain = asyncio.run(client.video_info("home", BV1))
    assert plain["tags"] == ["旅行", "记录"]          # 以前永远是空数组
    assert plain["page_count"] == 2 and plain["pages"][1]["cid"] == 43
    assert plain["cid"] == 42 and plain["cover"] == "https://i0.hdslb.com/a.jpg"
    assert "online" not in plain and "ai_summary" not in plain

    detailed = asyncio.run(client.video_info("home", BV1, True))
    assert detailed["online"]["count"] == 12
    assert detailed["ai_summary"]["summary"] == "一段摘要"
    assert detailed["ai_summary"]["outline"][0]["title"] == "开头"


def test_cover_downloads_once_then_reuses_local_file(client, monkeypatch, tmp_path):
    calls = []

    async def fake_fetch(url, limit=None):
        calls.append(url)
        return b"\xff\xd8\xff\xd9"

    class Handle:
        async def get_info(self):
            return {"pic": "http://i0.hdslb.com/b.jpg", "title": "标题"}

    monkeypatch.setattr(client, "_fetch_bytes", fake_fetch)
    monkeypatch.setattr(client, "shots_dir", lambda data_dir, bvid: tmp_path)
    monkeypatch.setattr(client.video, "Video", lambda *a, **k: Handle())

    first = asyncio.run(client.cover("home", BV1))
    second = asyncio.run(client.cover("home", BV1))
    assert first["ok"] is True and not first.get("cached")
    assert second["ok"] is True and second["cached"] is True
    assert calls == ["https://i0.hdslb.com/b.jpg"]
    assert Path(first["file"]["path"]).is_file()


def test_frame_crops_the_nearest_storyboard_cell(client, monkeypatch, tmp_path):
    image_module = pytest.importorskip("PIL.Image")
    sheet = image_module.new("RGB", (960, 540), (10, 20, 30))  # 2×2 格，每格 480×270
    sheet_path = tmp_path / "sheet.jpg"
    sheet.save(sheet_path, "JPEG")

    async def fake_fetch(url, limit=None):
        return sheet_path.read_bytes()

    class Handle:
        async def get_info(self):
            return {"cid": 42, "pages": [{"cid": 42}]}

        async def get_video_snapshot(self, cid=None, json_index=False, pvideo=True):
            return {"image": ["//bimp.hdslb.com/s.jpg"], "index": [0, 30, 60, 90],
                    "img_x_len": 2, "img_y_len": 2, "img_x_size": 480, "img_y_size": 270}

    monkeypatch.setattr(client, "_fetch_bytes", fake_fetch)
    monkeypatch.setattr(client, "shots_dir", lambda data_dir, bvid: tmp_path)
    monkeypatch.setattr(client.video, "Video", lambda *a, **k: Handle())

    out = asyncio.run(client.frame("home", BV1, at="70"))
    assert out["ok"] is True and out["source"] == "storyboard" and out["degraded"] is False
    assert out["files"][0]["at"] == 60  # 70 秒最近的是 60 秒那格
    assert out["files"][0]["width"] == 480 and out["files"][0]["height"] == 270
    assert Path(out["files"][0]["path"]).is_file()


def test_frame_falls_back_to_stream_and_says_so(client, monkeypatch):
    async def broken_storyboard(data_dir, bvid, times):
        raise RuntimeError("这条视频没有预览图")

    async def stream(data_dir, bvid, times, width):
        return [{"at": times[0], "clock": client._clock(times[0]), "path": "x.jpg",
                 "width": 1920, "height": 1080, "bytes": 1}]

    monkeypatch.setattr(client, "_storyboard_frames", broken_storyboard)
    monkeypatch.setattr(client, "_stream_frames", stream)
    out = asyncio.run(client.frame("home", BV1, at="10"))
    assert out["ok"] is True and out["degraded"] is True and out["source"] == "stream"
    assert out["notes"] and "预览图" in out["notes"][0]


def test_frame_takes_highlight_peaks_and_parses_clock(client, monkeypatch):
    async def peaks(data_dir, bvid, window=30, top=5):
        return {"highlights": [{"at": 30}, {"at": 120}]}

    async def frames(data_dir, bvid, times):
        return [{"at": t, "clock": client._clock(t), "path": "x.jpg",
                 "width": 480, "height": 270, "bytes": 1} for t in times]

    monkeypatch.setattr(client, "highlights", peaks)
    monkeypatch.setattr(client, "_storyboard_frames", frames)
    out = asyncio.run(client.frame("home", BV1, at="highlights", top=2))
    assert out["requested"] == [30, 120]
    assert client._parse_times("120, 3:30") == [120, 210]
    assert client._parse_times("auto") is None


def test_search_passes_page_and_reports_it(client, monkeypatch):
    seen = {}

    async def fake_search(**kwargs):
        seen.update(kwargs)
        return {"result": [{"bvid": BV1, "title": "标题"}]}

    monkeypatch.setattr(client.search, "search_by_type", fake_search)
    out = asyncio.run(client.search_videos("关键词", 3, "click", 2))
    assert seen["page"] == 2
    assert out["page"] == 2 and out["count"] == 1


def test_comments_supports_time_order_and_sub_replies(client, monkeypatch):
    calls = []

    async def fake_get_comments(**kwargs):
        calls.append(kwargs)
        return {"replies": [{"rpid": 11, "member": {"uname": "甲"},
                             "content": {"message": "好耶 [doge]"}, "like": 3,
                             "rcount": 0, "ctime": 2}]}

    class Handle:
        async def get_info(self):
            return {"aid": 99}

    monkeypatch.setattr(client.comment, "get_comments", fake_get_comments)
    monkeypatch.setattr(client.video, "Video", lambda *a, **k: Handle())
    hot = asyncio.run(client.comments("home", BV1, 5, "time"))
    assert hot["sort"] == "time"
    assert hot["comments"][0]["emotes"] == ["[doge]"]
    assert calls[0]["order"] is client.comment.OrderType.TIME

    class FakeApi:
        def __init__(self, **kwargs):
            pass

        def update_params(self, **kwargs):
            async def value():
                return {"replies": [{"rpid": 22, "member": {"uname": "乙"}, "parent": 11,
                                     "content": {"message": "楼中楼"}, "like": 1}]}
            return SimpleNamespace(result=value())

    monkeypatch.setattr(client, "Api", FakeApi)
    sub = asyncio.run(client.comments("home", BV1, 5, root=11))
    assert sub["root"] == 11 and sub["count"] == 1
    assert sub["comments"][0]["parent"] == 11


def test_verify_comment_reads_video_via_library_and_scans_pages(client, monkeypatch):
    class Handle:
        async def get_info(self):
            return {"aid": 99}

    async def fake_get_comments(**kwargs):
        if kwargs["order"] is client.comment.OrderType.TIME and kwargs["page_index"] == 1:
            return {"replies": [{"rpid": 555, "like": 7, "member": {}, "content": {}}]}
        return {"replies": []}

    monkeypatch.setattr(client.video, "Video", lambda *a, **k: Handle())
    monkeypatch.setattr(client.comment, "get_comments", fake_get_comments)
    monkeypatch.setattr(client, "load_credential", lambda home: SimpleNamespace(dedeuserid="1"))
    out = asyncio.run(client.verify_comment("home", BV1, 555))
    assert out["visible"] is True and out["likes"] == 7
    assert out["how"].startswith("顶层·最新")


def test_reply_maps_bind_phone_error_to_readable_text(client, monkeypatch):
    from bilibili_api.utils.network import ResponseCodeException

    class Handle:
        async def get_info(self):
            return {"aid": 1}

    async def boom(**kwargs):
        raise ResponseCodeException(61001, "需要绑定手机号")

    monkeypatch.setattr(client.video, "Video", lambda *a, **k: Handle())
    monkeypatch.setattr(client.comment, "send_comment", boom)
    monkeypatch.setattr(client, "get_cred", lambda home: SimpleNamespace())
    out = asyncio.run(client.reply("home", BV1, "你好"))
    assert out["success"] is False
    assert "绑定手机号" in out["error"]
    assert out["uncertain"] is False
