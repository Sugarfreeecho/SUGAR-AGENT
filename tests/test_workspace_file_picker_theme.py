from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workspace_file_picker_uses_shared_surface_tokens() -> None:
    picker = (ROOT / "frontend/src/vendor/myagent_path_picker.js").read_text(encoding="utf-8")

    assert ".workspace-file-popover{" in picker
    assert "background:var(--surface-glass2" in picker
    assert "border:1px solid var(--border-glass" in picker
    assert "box-shadow:var(--shadow-soft" in picker
    assert ".workspace-file-popover:before" not in picker
    assert "0 0 34px rgba(139,92,246,.16)" not in picker
    assert "radial-gradient(circle at 18%" not in picker


def test_workspace_file_picker_limits_accent_to_selection() -> None:
    picker = (ROOT / "frontend/src/vendor/myagent_path_picker.js").read_text(encoding="utf-8")

    assert ".workspace-file-item:hover,.workspace-file-item.is-active{background:rgba(255,255,255,.055)" in picker
    assert ".workspace-file-item.is-selected{background:rgba(var(--accent-rgb" in picker
    assert ".workspace-file-outside{flex-shrink:0;border:1px solid var(--border-glass" in picker
    assert ".theme-light .workspace-file-popover{background:rgba(255,255,255,.98)" in picker
