import asyncio
import base64
import copy
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from starlette.requests import Request

APP = str(Path(__file__).resolve().parents[1] / "app")
if APP not in sys.path:
    sys.path.insert(0, APP)
from human_interaction.service import HumanInteractionService, HumanInteractionValidationError


@pytest.fixture
def image_service(tmp_path, monkeypatch):
    import attachments
    # Import consumers before patching the exported factory; otherwise their
    # module-level binding can retain this test's store after fixture teardown.
    import webui
    from attachments.local import LocalAttachmentStore

    store = LocalAttachmentStore(tmp_path / "workspace")
    monkeypatch.setattr(attachments, "get_attachment_store", lambda *args, **kwargs: store)
    monkeypatch.setenv("ASK_USER_ENABLED", "1")
    service = HumanInteractionService(tmp_path / "sessions", path_resolver=lambda sid: tmp_path / "sessions" / sid)
    return service, store


def _png():
    output = BytesIO()
    Image.new("RGB", (120, 120), "white").save(output, "PNG")
    return output.getvalue()


def _arguments(image=None):
    image = image if image is not None else {
        "data_url": "data:image/png;base64," + base64.b64encode(_png()).decode(),
        "alt": "登录二维码", "caption": "请扫码，再选择实际结果。",
    }
    return {"questions": [{
        "header": "扫码登录", "question": "请用手机扫码登录。", "images": [image],
        "options": [{"label": "已扫码", "description": "继续检查登录状态"},
                    {"label": "二维码失效", "description": "生成新的二维码"}],
    }]}


def test_inline_image_persists_only_attachment_ref_and_survives_rebuild(image_service):
    service, store = image_service
    arguments = _arguments()
    original = copy.deepcopy(arguments)
    created = service.create_question("s", arguments)
    image = created["questions"][0]["images"][0]
    assert arguments == original
    assert image["alt"] == "登录二维码"
    assert "data_url" not in image
    assert store.read_image_sync(image["attachment"]).ref["width"] == 120
    event_path = service.mirror.event_log.event_path("s")
    assert "data:image" not in event_path.read_text(encoding="utf-8")
    from attachments.lifecycle import collect_image_references
    assert image["attachment"]["attachmentId"] in collect_image_references([event_path.parent])
    rebuilt = HumanInteractionService(service.mirror.event_log.root, path_resolver=lambda sid: event_path.parent.parent / sid)
    assert rebuilt.get("s", created["interaction_id"])["questions"][0]["images"] == [image]
    resolved = rebuilt.resolve_question("s", created["interaction_id"], {
        "answers": [{"question_id": "q1", "selected_option_ids": ["q1o1"]}],
        "request_version": created["request_version"], "request_digest": created["request_digest"],
    })
    assert resolved["answers"][0]["selected_labels"] == ["已扫码"]


def test_reuses_existing_read_file_attachment(image_service, tmp_path):
    service, store = image_service
    import agent_tools
    path = tmp_path / "login.png"
    path.write_bytes(_png())
    result = agent_tools._read_file_image_output(path)
    ref = result[1]["attachment"]
    created = service.create_question("s", _arguments({"attachment_id": ref["attachmentId"], "alt": "登录码"}))
    admitted = created["questions"][0]["images"][0]["attachment"]
    assert admitted["attachmentId"] == ref["attachmentId"]
    assert store.read_image_sync(admitted).data == store.read_image_sync(ref).data
    assert len(list(store.root.glob("*/*/image.json"))) == 1


@pytest.mark.parametrize("image", [
    {"data_url": "https://example.test/qr.png", "alt": "二维码"},
    {"data_url": "file:///private/qr.png", "alt": "二维码"},
    {"data_url": "data:image/svg+xml;base64,PHN2Zy8+", "alt": "二维码"},
    {"data_url": "data:image/png;base64,AAAA", "alt": "二维码"},
    {"attachment_id": "../secret", "alt": "二维码"},
    {"attachment_id": "sha256:" + "a" * 64, "data_url": "data:image/png;base64,AAAA", "alt": "二维码"},
    {"alt": "二维码"},
    {"data_url": "data:image/png;base64,AAAA", "alt": ""},
    {"data_url": "data:image/png;base64,AAAA", "alt": "二维码", "caption": 123},
])
def test_invalid_image_never_creates_pending_request(image_service, image):
    service, store = image_service
    with pytest.raises(HumanInteractionValidationError):
        service.create_question("s", _arguments(image))
    assert not service.list("s")
    assert not list(store.root.glob("*/*/image.json"))


def test_corrupt_batch_does_not_save_first_valid_image(image_service):
    service, store = image_service
    arguments = _arguments()
    arguments["questions"][0]["images"].append({"data_url": "data:image/png;base64,AAAA", "alt": "坏图片"})
    with pytest.raises(HumanInteractionValidationError, match="image unavailable"):
        service.create_question("s", arguments)
    assert not list(store.root.glob("*/*/image.json"))


def test_image_count_and_encoded_size_limits(image_service):
    service, _ = image_service
    arguments = _arguments()
    question = arguments["questions"][0]
    question["images"] *= 5
    with pytest.raises(HumanInteractionValidationError, match="at most 4"):
        service.create_question("s", arguments)
    question["images"] = question["images"][:3]
    arguments["questions"] = [dict(question, question=f"扫码任务 {i}") for i in range(3)]
    with pytest.raises(HumanInteractionValidationError, match="at most 8"):
        service.create_question("s", arguments)
    from app.human_interaction.images import MAX_IMAGE_BYTES
    image = {"data_url": "data:image/png;base64," + "A" * (MAX_IMAGE_BYTES * 2), "alt": "大图"}
    with pytest.raises(HumanInteractionValidationError, match="2 MiB"):
        service.create_question("s", _arguments(image))


def test_text_only_question_does_not_touch_image_store(image_service, monkeypatch):
    service, _ = image_service
    import attachments
    def fail():
        pytest.fail("text-only requests must not open the attachment store")
    monkeypatch.setattr(attachments, "get_attachment_store", fail)
    arguments = _arguments()
    arguments["questions"][0].pop("images")
    assert "images" not in service.create_question("s", arguments)["questions"][0]


def test_question_image_http_is_bound_to_record_and_authenticated(image_service, monkeypatch):
    service, store = image_service
    import human_interaction
    import webui
    monkeypatch.setattr(human_interaction, "get_human_interaction_service", lambda: service)
    monkeypatch.setattr(webui, "get_attachment_store", lambda *_: store)
    created = service.create_question("s", _arguments())
    iid = created["interaction_id"]
    response = asyncio.run(webui.read_session_interaction_image("s", iid, "q1", 0))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert Image.open(BytesIO(response.body)).size == (120, 120)
    for sid, request_id, qid, index in [("s", iid, "q1", -1), ("s", iid, "q1", 1),
                                         ("s", iid, "q2", 0), ("s", "other", "q1", 0),
                                         ("other", iid, "q1", 0)]:
        assert asyncio.run(webui.read_session_interaction_image(sid, request_id, qid, index)).status_code == 404
    from fastapi import HTTPException
    request = Request({"type": "http", "headers": [(b"host", b"agent.test")],
                       "client": ("198.51.100.2", 9999)})
    with pytest.raises(HTTPException) as denied:
        asyncio.run(webui.read_session_interaction_image("s", iid, "q1", 0, request))
    assert denied.value.status_code == 401
    request = Request({"type": "http", "headers": [(b"host", b"agent.test"),
                       (b"origin", b"https://untrusted.test")], "client": ("127.0.0.1", 9999)})
    with pytest.raises(HTTPException) as denied:
        asyncio.run(webui.read_session_interaction_image("s", iid, "q1", 0, request))
    assert denied.value.status_code == 403
