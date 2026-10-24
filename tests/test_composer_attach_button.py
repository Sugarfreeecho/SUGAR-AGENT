"""输入框附件按钮（回形针）与语音按钮的尺寸/高亮一致性契约。"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

APP_CSS = ROOT / "frontend/src/styles/app.css"
SPEECH_CSS = ROOT / "plugins/voice-input/web/voice.css"
VENDOR = ROOT / "frontend/src/vendor/myagent_path_picker.js"
STATIC_VENDOR = ROOT / "app/templates/static/myagent_path_picker.js"

ATTACH_BASE = re.compile(r"\.input-wrapper \.path-browse-btn--ghost \{(?P<body>[^}]*)\}")
ATTACH_ICON = re.compile(r"\.input-wrapper \.path-browse-btn--ghost svg \{(?P<body>[^}]*)\}")
ATTACH_HIGHLIGHT = re.compile(
    r"\.input-wrapper \.path-browse-btn--ghost:hover,\s*"
    r"\.input-wrapper \.path-browse-btn--ghost:focus-visible,\s*"
    r"\.input-wrapper \.path-browse-btn--ghost\.is-open,\s*"
    r"\.input-wrapper \.path-browse-btn--ghost\[aria-expanded=\"true\"\] \{(?P<body>[^}]*)\}"
)
SPEECH_HOVER = re.compile(
    r"\.voice-mic:hover,\s*\.voice-mic:focus-visible,\s*"
    r"\.voice-mic\[aria-expanded=\"true\"\] \{(?P<body>[^}]*)\}"
)


def _decls(body: str) -> dict:
    out = {}
    for chunk in body.split(";"):
        if ":" not in chunk:
            continue
        name, _, value = chunk.partition(":")
        out[name.strip()] = re.sub(r"\s+", " ", value.strip())
    return out


def test_attach_button_matches_the_speech_button_box() -> None:
    styles = APP_CSS.read_text(encoding="utf-8")
    base = _decls(ATTACH_BASE.search(styles).group("body"))
    icon = _decls(ATTACH_ICON.search(styles).group("body"))

    # 与插件 .voice-mic 同为 2rem 方形 + 8px 圆角
    assert base["width"] == "2rem"
    assert base["height"] == "2rem"
    assert base["border-radius"] == "8px"
    assert base["padding"] == "0"
    # 图标 16px（原来 18px 显得偏大）
    assert icon["width"] == "1rem"
    assert icon["height"] == "1rem"


def test_attach_highlight_reuses_the_speech_button_palette() -> None:
    styles = APP_CSS.read_text(encoding="utf-8")
    speech = _decls(SPEECH_HOVER.search(SPEECH_CSS.read_text(encoding="utf-8")).group("body"))
    attach = _decls(ATTACH_HIGHLIGHT.search(styles).group("body"))

    # 高亮底色与前景色和语音按钮完全同源，改一侧另一侧会一起失败
    assert attach["background"] == speech["background"] == "rgba(var(--accent-rgb), .1)"
    assert attach["color"] == speech["color"] == "var(--accent-1)"


def test_attach_button_keeps_the_highlight_while_the_panel_is_open() -> None:
    vendor = VENDOR.read_text(encoding="utf-8")

    assert "button.setAttribute('aria-haspopup', 'dialog');" in vendor
    assert "button.classList.toggle('is-open', open);" in vendor
    assert "button.setAttribute('aria-expanded', open ? 'true' : 'false');" in vendor
    assert "new MutationObserver(syncPanelTriggerState).observe(" in vendor
    assert "attributeFilter: ['class']" in vendor


def test_static_path_picker_copy_stays_in_sync() -> None:
    assert VENDOR.read_bytes() == STATIC_VENDOR.read_bytes()
