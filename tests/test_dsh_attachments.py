import asyncio
import base64
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from attachments import AttachmentError, LocalAttachmentStore, SaveImageAttachment
from attachments.types import ImageAttachmentLimits, ImageRequestPolicy
from attachments.content import durable_content, project_request_images, chat_tool_images
from attachments.encoding import decode_base64
from attachments.request_budget import RequestImageOffloadPolicy, offloaded_image_prefix_count


def picture(mode="RGB", size=(80, 60), format="PNG", color=None):
    out = BytesIO()
    Image.new(mode, size, color or ((20, 40, 60, 100) if mode == "RGBA" else (20, 40, 60))).save(out, format=format)
    return out.getvalue()


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_DIR", str(tmp_path))
    # Other tests import the harness and keep its WORK_DIR in memory.
    if "agent_harness" in sys.modules:
        monkeypatch.setattr(sys.modules["agent_harness"], "WORK_DIR", tmp_path)
    return LocalAttachmentStore(tmp_path)


def save(store, **kwargs):
    return store.save_images_sync([SaveImageAttachment(picture(**kwargs), "image/png", "example.png")])[0]


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_normalization_redecoded_metadata_and_alpha(store, mode):
    ref = save(store, mode=mode, size=(2400, 2000))
    stored = asyncio.run(store.read_image(ref))
    assert ref["width"] * ref["height"] <= 2048 ** 2
    assert ref["originalDimensions"] == {"width": 2400, "height": 2000}
    with Image.open(BytesIO(stored.data)) as decoded:
        assert decoded.mode == mode
        assert not decoded.getexif()
        assert not decoded.info.get("icc_profile")
        assert getattr(decoded, "n_frames", 1) == 1
    assert ref["mediaType"] == ("image/webp" if mode == "RGBA" else "image/jpeg")


def test_digest_idempotent_concurrent_variant_and_corrupt_cache_recovery(store):
    ref = save(store)
    assert save(store) == ref
    policy = ImageRequestPolicy(max_pixels=400, max_bytes=1000)
    with ThreadPoolExecutor(max_workers=6) as pool:
        versions = list(pool.map(lambda _: store.read_request_image_sync(ref, policy), range(12)))
    assert len({v.variant_id for v in versions}) == 1
    assert len({v.data for v in versions}) == 1
    assert len(list(store.root.rglob("image.jpg"))) == 1
    key = versions[0].variant_id[7:]
    cache = store.cache_root / key[:2] / key
    before = cache.stat().st_mtime_ns
    store.read_request_image_sync(ref, policy)
    assert cache.stat().st_mtime_ns == before
    cache.write_bytes(b"corrupt")
    assert store.read_request_image_sync(ref, policy).data == versions[0].data
    assert store.save_path(store.image_host_path(ref))["attachmentId"] == ref["attachmentId"]


@pytest.mark.parametrize("data,media,code", [
    (b"bad", "image/png", "UNSUPPORTED_IMAGE_TYPE"),
    (picture(), "image/gif", "UNSUPPORTED_IMAGE_TYPE"),
    (picture(size=(8193, 1)), "image/png", "IMAGES_TOO_LARGE"),
])
def test_admission_errors_leave_no_objects(store, data, media, code):
    with pytest.raises(AttachmentError) as error:
        store.save_images_sync([SaveImageAttachment(data, media)])
    assert error.value.code == code
    assert not store.root.exists()


def test_batch_rollback_on_write_failure(store, monkeypatch):
    import attachments.local as local
    original = local.atomic_write
    calls = 0
    def fail(path, data, readonly=False):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("disk unavailable")
        return original(path, data, readonly)
    monkeypatch.setattr(local, "atomic_write", fail)
    with pytest.raises(AttachmentError) as error:
        store.save_images_sync([SaveImageAttachment(picture(color=color), "image/png") for color in [(1, 2, 3), (250, 0, 0)]])
    assert error.value.code == "ATTACHMENT_WRITE_FAILED"
    assert not [p for p in store.root.rglob("*") if p.is_file()]


@pytest.mark.parametrize("bad", ["YQ", "YQ==\n", "YR==", "!!!!", ""])
def test_canonical_base64(bad):
    with pytest.raises(AttachmentError):
        decode_base64(bad)


def test_quanta_match_dsh_strict_byte_boundary():
    policy = RequestImageOffloadPolicy(max_bytes=128, byte_quantum=64)
    assert offloaded_image_prefix_count([1] * 129, policy) == 65
    assert offloaded_image_prefix_count([1] * 192, policy) == 65
    assert offloaded_image_prefix_count([1] * 193, policy) == 129
    assert offloaded_image_prefix_count([1] * 21, RequestImageOffloadPolicy(max_images=20)) == 20


def test_nested_budget_oldest_offloaded_without_mutating_core(store):
    ref = save(store)
    blocks = [{"type": "text", "text": "result"}, {"type": "image", "attachment": ref}]
    messages = [{"role": "tool", "tool_call_id": "a", "content": blocks}, {"role": "user", "content": blocks}]
    original = json.dumps(messages)
    client = SimpleNamespace(_myagent_image_request_policy={"maxImagesPerRequest": 1, "countQuantum": 1})
    wire = project_request_images(messages, store=store, client=client, language="en")
    assert "image omitted to fit" in json.dumps(wire[0])
    assert ref["attachmentId"] in json.dumps(wire[0])
    assert json.dumps(store.image_host_path(ref)) in wire[0]["content"][1]["text"]
    assert wire[1]["content"][-1]["type"] == "image_url"
    assert json.dumps(messages) == original
    assert "base64" not in original


def test_three_native_protocol_positions(store):
    from agent_messages import UserMessage, ToolMessage
    from agent_openai import messages_to_openai_params
    from llm.transport import chat_messages_to_anthropic, chat_messages_to_responses_input
    ref = save(store)
    tool = ToolMessage([{ "type": "text", "text": "screenshot"}, {"type": "image", "attachment": ref}], "call-1")
    native = messages_to_openai_params([tool], native_tool_images=True, language="en")
    chat = chat_tool_images(native)
    assert chat[0] == {"role": "tool", "tool_call_id": "call-1", "content": "screenshot"}
    assert chat[1]["role"] == "user"
    assert chat[1]["content"][-1]["type"] == "image_url"
    responses = chat_messages_to_responses_input(native)
    assert responses[0]["type"] == "function_call_output"
    assert responses[0]["output"][-1]["type"] == "input_image"
    _, anthropic = chat_messages_to_anthropic(native)
    assert anthropic[0]["content"][0]["type"] == "tool_result"
    assert anthropic[0]["content"][0]["content"][-1]["type"] == "image"
    assert "base64" not in json.dumps(tool.content)


def test_text_model_never_reads_request_variant(store, monkeypatch):
    ref = save(store)
    monkeypatch.setattr(store, "read_request_image_sync", lambda *args: pytest.fail("No image preparation on text route"))
    wire = project_request_images([{"role": "user", "content": [{"type": "image", "attachment": ref}]}], store=store, image_enabled=False, language="en")
    assert "accepts text only" in wire[0]["content"][0]["text"]
    assert "task" not in json.dumps(wire)


def test_mcp_admission_batch_and_log_redaction(store):
    import agent_mcp
    data = base64.b64encode(picture()).decode()
    result = SimpleNamespace(content=[SimpleNamespace(type="text", text="before"), SimpleNamespace(type="image", mimeType="image/png", data=data), SimpleNamespace(type="text", text="after")], isError=False)
    blocked = agent_mcp.format_call_tool_result(result, image_enabled=False, model="text", attachment_store=store)
    assert "does not declare image input" in blocked
    assert not store.root.exists()
    admitted = agent_mcp.format_call_tool_result(result, image_enabled=True, attachment_store=store)
    assert [b["type"] for b in admitted] == ["text", "image", "text"]
    assert data not in agent_mcp._serialize_call_tool_result_for_log(result)
    result.content.append(SimpleNamespace(type="image", mimeType="image/png", data="YR=="))
    assert "entire image batch rejected" in agent_mcp.format_call_tool_result(result, image_enabled=True, attachment_store=store)


def test_legacy_migration_stable_when_source_changes(store, tmp_path, monkeypatch):
    from agent_messages import UserMessage
    from agent_openai import messages_to_openai_params
    path = tmp_path / "source.bmp"
    path.write_bytes(picture(format="BMP"))
    message = UserMessage(f'look at "{path}"')
    from attachments.admission import AdmissionContext, admit_content
    message.content = admit_content(message.content, AdmissionContext(store), scan_paths=True)
    identity = message.content[1]["attachment"]["attachmentId"]
    path.write_bytes(picture(color=(255, 0, 0), format="BMP"))
    messages_to_openai_params([message])
    assert len(message.content) == 2
    assert message.content[1]["attachment"]["attachmentId"] == identity
    monkeypatch.setenv("MULTIMODAL_TEXT_PATH_SCAN", "off")
    assert isinstance(UserMessage(f'look at "{path}"').content, str)


def test_runtime_event_snapshot_restore_preserves_tool_and_user_refs(store, tmp_path, monkeypatch):
    from runtime_v2.history_ops import RuntimeHistoryOps
    from runtime_v2.model_projection import RuntimeModelProjection
    from runtime_v2.event_schema import RuntimeEvent
    from agent_harness import _dict_to_message
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    ref = save(store)
    blocks = [{"type": "image", "attachment": ref}]
    root = tmp_path / "sessions"
    ops = RuntimeHistoryOps(root)
    ops.commit_user_turn("images", blocks, ui_content="inspect", model_payload={"attachments": [ref]})
    ops.append_model_message("images", "tool", blocks, tool_call_id="call-1")
    rows = RuntimeModelProjection(root).read_message_dicts("images")
    assert rows[0]["content"] == blocks
    assert rows[1]["content"] == blocks
    assert _dict_to_message(rows[1]).content == blocks
    # Rebuild without trusting the saved snapshot.
    rebuilt = ops.projector.project(ops.event_log.read_all("images"))
    assert rebuilt["model_messages"][1]["payload"]["content"] == blocks
    raw = ops.event_log.event_path("images").read_text()
    assert "base64" not in raw
    assert ref["attachmentId"] in raw
    legacy = RuntimeEvent(1, "ui_event", "images", payload={"content": "data:image/png;base64,YQ=="})
    assert "data:image" not in json.dumps(legacy.to_dict())


def test_upload_endpoint_to_wire_and_binary_response(store, tmp_path, monkeypatch):
    import webui
    from starlette.datastructures import UploadFile
    from agent_messages import UserMessage
    from agent_openai import messages_to_openai_params
    monkeypatch.setattr(webui, "WORK_DIR", tmp_path)
    response = asyncio.run(webui.upload_chat_files([UploadFile(filename="screen.png", file=BytesIO(picture()))]))
    receipt = json.loads(response.body)["files"][0]
    binary = asyncio.run(webui.read_attachment(receipt["attachment"]["attachmentId"]))
    assert binary.status_code == 200
    assert binary.body == store.read_image_sync(receipt["attachment"]).data
    message = UserMessage([{"type": "image", "attachment": receipt["attachment"]}])
    wire = messages_to_openai_params([message])
    assert wire[0]["content"][-1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "base64" not in json.dumps(receipt)
    assert "base64" not in json.dumps(message.content)


def test_reference_validation_and_batch_limits(store):
    with pytest.raises(AttachmentError) as exc:
        store.image_host_path({"attachmentId": "../../file", "mediaType": "image/png"})
    assert exc.value.code == "INVALID_ATTACHMENT_REF"
    item = SaveImageAttachment(picture(), "image/png")
    store.limits = replace(store.limits, max_images_per_message=1)
    with pytest.raises(AttachmentError) as exc:
        store.save_images_sync([item, item])
    assert exc.value.code == "TOO_MANY_IMAGES"
    store.limits = replace(store.limits, max_images_per_message=20, max_message_image_bytes=1)
    with pytest.raises(AttachmentError) as exc:
        store.save_images_sync([item])
    assert exc.value.code == "IMAGES_TOO_LARGE"
    assert not store.root.exists()


def test_raw_user_image_batch_rejects_before_any_commit(store):
    valid = base64.b64encode(picture()).decode()
    content = [{"type": "image", "mediaType": "image/png", "data": data} for data in [valid, "YR=="]]
    admitted = durable_content(content, store)
    assert all(part["type"] == "text" for part in admitted)
    assert not store.root.exists()


def test_route_policy_is_saved_validated_and_invalidates_client_cache(tmp_path):
    import model_profiles
    profile = model_profiles.upsert_profile(tmp_path, {"name": "vision", "model": "image-model", "base_url": "https://example.com/v1", "api_key": "test", "image_request_policy": {"maxImagesPerRequest": 2, "maxPixels": 400}})
    assert profile["image_request_policy"]["maxPixels"] == 400
    before = model_profiles.profile_cache_key(profile)
    profile["image_request_policy"]["maxPixels"] = 800
    assert model_profiles.profile_cache_key(profile) != before
    with pytest.raises(ValueError):
        model_profiles.normalize_image_request_policy({"byteQuantum": 0})


def test_actual_fallback_candidate_owns_image_budget(store):
    import agent_harness
    from agent_messages import UserMessage
    from agent_openai import _messages_to_params_for_client
    from llm import TransportEvent
    calls = []
    class Transport:
        def __init__(self, fail):
            self.fail = fail
        def stream_completion(self, **kwargs):
            calls.append(kwargs["messages"])
            if self.fail:
                raise ValueError("bad request on first route")
            yield TransportEvent("content_delta", text="ok")
    candidates = [{"model": str(i), "profile_id": str(i), "transport": Transport(i == 0), "input_modalities": ["text", "image"], "image_request_policy": {"maxImagesPerRequest": i}} for i in range(2)]
    client = agent_harness.ExecutorLLMClient(candidates)
    message = UserMessage([{"type": "image", "attachment": save(store)}])
    canonical = _messages_to_params_for_client(client, [message])
    assert canonical[0]["content"][0]["type"] == "image"
    assert "base64" not in json.dumps(canonical)
    list(client.stream_completion(model="0", messages=canonical, max_tokens=8))
    assert not any(p.get("type") == "image_url" for p in calls[0][0]["content"])
    assert any(p.get("type") == "image_url" for p in calls[1][0]["content"])


def test_legacy_event_replay_admits_image_before_redaction(store):
    from runtime_v2.event_schema import RuntimeEvent
    encoded = base64.b64encode(picture()).decode()
    from runtime_v2.attachment_migration import event_from_record
    event = event_from_record({"seq": 1, "type": "model_tool", "session_id": "legacy", "payload": {
        "tool_call_id": "call-1", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}}]}})
    ref = event.payload["content"][0]["attachment"]
    assert store.read_image_sync(ref).data
    assert "base64" not in json.dumps(event.to_dict())
    assert RuntimeEvent.from_dict(event.to_dict()).payload == event.payload


def test_history_cleaning_and_microshrink_keep_tool_images(store, monkeypatch):
    from agent_messages import ToolMessage
    from agent_tokenizer import messages_for_openai_turns
    from agent_memory import _micro_shrink_tool_message_content_inplace
    import agent_memory
    blocks = [{"type": "text", "text": "Tool Call: screenshot -> " + "a" * 200},
              {"type": "image", "attachment": save(store)}, {"type": "text", "text": "after"}]
    message = messages_for_openai_turns([ToolMessage(content=blocks, tool_call_id="c1")])[0]
    assert message.content[0]["text"] == "a" * 200
    monkeypatch.setattr(agent_memory, "_micro_tool_keep_each_side", lambda: 20)
    assert _micro_shrink_tool_message_content_inplace(message)
    assert message.content[1:] == blocks[1:]
    assert len(message.content[0]["text"]) < 100


def test_upload_uses_declared_type_and_rejects_mismatch_atomically(store, tmp_path, monkeypatch):
    import webui
    from starlette.datastructures import UploadFile, Headers
    monkeypatch.setattr(webui, "WORK_DIR", tmp_path)
    def upload(name, mime):
        return UploadFile(filename=name, file=BytesIO(picture()), headers=Headers({"content-type": mime}))
    result = asyncio.run(webui.upload_chat_files([upload("no-extension", "image/png"), upload("wrong.jpg", "image/jpeg")]))
    assert result.status_code == 400
    assert json.loads(result.body)["code"] == "UNSUPPORTED_IMAGE_TYPE"
    assert not store.root.exists()
    result = asyncio.run(webui.upload_chat_files([upload("no-extension", "image/png")]))
    assert json.loads(result.body)["files"][0]["attachment"]["mediaType"] == "image/jpeg"


def test_steer_history_includes_durable_attachment(store):
    from runtime_v2.event_schema import RuntimeEvent
    from runtime_v2.ui_projection import RuntimeUiProjection
    ref = save(store)
    event = RuntimeEvent(1, "user_turn_committed", "s", payload={"ui_type": "user_steer", "ui_content": "inspect", "attachments": [ref]})
    assert RuntimeUiProjection.event_to_ui(event)["attachments"] == [ref]


@pytest.mark.parametrize("source_format", ["exif", "16bit", "gif"])
def test_normalization_orientation_depth_and_animation(store, source_format):
    out = BytesIO()
    if source_format == "exif":
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (80, 40), (10, 40, 80)).save(out, "JPEG", exif=exif)
        expected, media = (40, 80), "image/jpeg"
    elif source_format == "16bit":
        Image.new("I;16", (80, 40), 32768).save(out, "PNG")
        expected, media = (80, 40), "image/png"
    else:
        Image.new("RGB", (80, 40), "red").save(out, "GIF", save_all=True, append_images=[Image.new("RGB", (80, 40), "blue")], duration=50)
        expected, media = (80, 40), "image/gif"
    ref = store.save_images_sync([SaveImageAttachment(out.getvalue(), media)])[0]
    with Image.open(BytesIO(store.read_image_sync(ref).data)) as image:
        assert image.size == expected
        assert image.mode == "RGB"
        assert getattr(image, "n_frames", 1) == 1
        assert not image.getexif()
        if source_format == "16bit":
            assert 120 <= image.getpixel((0, 0))[0] <= 135


def test_file_ref_projects_to_readonly_handle(store):
    ref = store.save_file_sync("notes.txt", b"durable file")
    wire = project_request_images([{"role": "user", "content": [{"type": "file", "attachment": ref}]}], store=store, language="en")
    text = wire[0]["content"][0]["text"]
    assert ref["attachmentId"] in text
    assert "read-only" in text
    assert "copy before editing" in text


def test_legacy_budget_alias_warns_and_new_setting_takes_precedence(monkeypatch):
    from attachments import budget_policy
    monkeypatch.setenv("MULTIMODAL_INLINE_MAX_BYTES", "1000")
    monkeypatch.delenv("MULTIMODAL_MAX_INLINE_REQUEST_IMAGE_BYTES", raising=False)
    with pytest.warns(FutureWarning, match="deprecated"):
        legacy = budget_policy()
    monkeypatch.setenv("MULTIMODAL_MAX_INLINE_REQUEST_IMAGE_BYTES", "2000")
    with pytest.warns(FutureWarning, match="deprecated"):
        current = budget_policy()
    assert legacy.max_bytes == 1000
    assert current.max_bytes == 2000


def test_encoding_uses_first_fit_or_smallest_quality_result():
    from attachments.encoding import encode_image
    class Encoder:
        mode = "RGB"
        calls = []
        def save(self, output, *, quality, **kwargs):
            self.calls.append(quality)
            # Encoded sizes need not decrease monotonically with quality.
            output.write(b"x" * {90: 90, 80: 60, 70: 70, 60: 20, 50: 40, 40: 30}[quality])
    image = Encoder()
    data, _ = encode_image(image, 65)
    assert image.calls == [90, 80]
    assert len(data) == 60
    image.calls = []
    data, _ = encode_image(image, 1)
    assert len(image.calls) == 6
    assert len(data) == 20


def test_request_resize_can_remove_ineffective_alpha(store):
    image = Image.new("RGBA", (100, 100), (40, 80, 120, 255))
    image.putpixel((0, 0), (40, 80, 120, 0))
    out = BytesIO()
    image.save(out, "PNG")
    ref = store.save_images_sync([SaveImageAttachment(out.getvalue(), "image/png")])[0]
    assert ref["mediaType"] == "image/webp"
    policy = ImageRequestPolicy(max_pixels=1)
    version = store.read_request_image_sync(ref, policy)
    assert version.media_type == "image/jpeg"
    assert not version.has_alpha
    assert store.read_request_image_sync(ref, policy).data == version.data
