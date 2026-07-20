from app.runtime_v2 import BlobStore


def test_blob_write_is_content_addressed_and_read_is_verified(tmp_path):
    store = BlobStore(tmp_path)
    ref = store.put_text("hello")
    assert store.read_text(ref["blob_ref"]) == "hello"

    path = tmp_path / ref["blob_ref"]
    path.write_text("tampered", encoding="utf-8")
    try:
        store.read_text(ref["blob_ref"])
    except RuntimeError as exc:
        assert "checksum mismatch" in str(exc)
    else:
        raise AssertionError("tampered Runtime V2 blobs must not be consumed")
