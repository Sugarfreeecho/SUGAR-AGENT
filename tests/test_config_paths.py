import io
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from config_paths import config_dir, config_path, resolve_legacy_config_path


def test_rename_preserves_config_and_nested_workspace_data(tmp_path):
    legacy = tmp_path / ".sugaragent"
    (legacy / "attachments/v1").mkdir(parents=True)
    (legacy / "model_profiles.json").write_bytes(b'{"profiles": [{"id": "saved"}]}')
    (legacy / "attachments/v1/image.png").write_bytes(b"image-data")

    target = config_dir(tmp_path)

    assert target == tmp_path / ".config"
    assert (target / "model_profiles.json").read_bytes() == b'{"profiles": [{"id": "saved"}]}'
    assert (target / "attachments/v1/image.png").read_bytes() == b"image-data"
    assert not legacy.exists()
    assert config_dir(tmp_path) == target


def test_merge_preserves_new_config_and_keeps_conflicting_old_copy(tmp_path):
    legacy = tmp_path / ".sugaragent"
    target = tmp_path / ".config"
    for directory in (legacy, target):
        (directory / "history-media").mkdir(parents=True)
    (legacy / "model_profiles.json").write_bytes(b"old-profiles")
    (target / "model_profiles.json").write_bytes(b"new-profiles")
    (legacy / "history-media/old.png").write_bytes(b"old-image")
    (target / "history-media/new.png").write_bytes(b"new-image")
    (target / "unrelated-settings").write_bytes(b"keep")

    assert config_dir(tmp_path) == target

    assert (target / "model_profiles.json").read_bytes() == b"new-profiles"
    assert (legacy / "model_profiles.json").read_bytes() == b"old-profiles"
    assert (target / "history-media/old.png").read_bytes() == b"old-image"
    assert (target / "history-media/new.png").read_bytes() == b"new-image"
    assert (target / "unrelated-settings").read_bytes() == b"keep"


def test_locked_legacy_directory_remains_readable_and_writable(tmp_path, monkeypatch):
    legacy = tmp_path / ".sugaragent"
    legacy.mkdir()
    state = legacy / "skill_states.json"
    state.write_bytes(b"disabled-skills")
    original = Path.rename

    def deny_legacy_move(self, target):
        if self == legacy:
            raise PermissionError("locked directory")
        return original(self, target)

    monkeypatch.setattr(Path, "rename", deny_legacy_move)
    resolved = config_path(tmp_path, "skill_states.json")

    assert resolved == state
    assert resolved.read_bytes() == b"disabled-skills"
    resolved.write_bytes(b"updated-skills")
    assert state.read_bytes() == b"updated-skills"


def test_attachment_references_survive_directory_rename(tmp_path):
    from PIL import Image
    from attachments.local import LocalAttachmentStore
    from attachments.types import SaveImageAttachment

    data = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(data, format="PNG")
    original = LocalAttachmentStore(tmp_path)
    ref = original.save_images_sync([SaveImageAttachment(data=data.getvalue(), media_type="image/png")])[0]
    stored_bytes = Path(original.image_host_path(ref)).read_bytes()
    # Model the old on-disk layout while retaining the exact saved identity.
    (tmp_path / ".config").rename(tmp_path / ".sugaragent")
    import config_paths
    config_paths._migrated_roots.discard(tmp_path.resolve())

    current = LocalAttachmentStore(tmp_path)

    assert current.root == tmp_path / ".config/attachments/v1"
    assert Path(current.image_host_path(ref)).read_bytes() == stored_bytes
    assert current.read_image_sync(ref).data == stored_bytes


def test_old_image_path_is_aliased_after_migration(tmp_path):
    legacy = tmp_path / ".sugaragent/history-media/hash.png"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"saved-image")
    new = config_path(tmp_path, "history-media", "hash.png")

    assert resolve_legacy_config_path(legacy, tmp_path) == new
    assert new.read_bytes() == b"saved-image"


def test_existing_conflicting_old_image_still_resolves_to_its_own_bytes(tmp_path):
    legacy = tmp_path / ".sugaragent/history-media/hash.png"
    new = tmp_path / ".config/history-media/hash.png"
    for path, data in ((legacy, b"old"), (new, b"new")):
        path.parent.mkdir(parents=True)
        path.write_bytes(data)

    assert resolve_legacy_config_path(legacy, tmp_path) == legacy
    assert legacy.read_bytes() == b"old"
    assert new.read_bytes() == b"new"


def test_legacy_alias_does_not_rewrite_unrelated_or_parent_paths(tmp_path):
    unrelated = tmp_path / "nested/.sugaragent/image.png"
    escaped = tmp_path / ".sugaragent/../outside.png"

    assert resolve_legacy_config_path(unrelated, tmp_path) == unrelated.resolve()
    assert resolve_legacy_config_path(escaped, tmp_path) == (tmp_path / "outside.png").resolve()


def test_config_directory_keeps_existing_protected_path_policy(tmp_path):
    from security.policy import protected_path

    assert protected_path(tmp_path / ".config/model_profiles.json", tmp_path)
    assert protected_path(tmp_path / ".sugaragent/model_profiles.json", tmp_path)
