"""设置中心（/settings 单页 9 分区）的契约测试。

覆盖：路由与分区预选、静态资源白名单、env「恢复默认」删键、技能新建/安装。
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient


def _client():
    import webui

    return TestClient(webui.fastapi_app)


def test_settings_routes_render_single_page_with_preselect():
    client = _client()

    for path, section in (
        ("/settings", "general"),
        ("/setup/env", "env"),
        ("/setup/mcp", "mcp"),
        ("/setup/extensions", "plugins"),
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.text
        # 同一个外壳 + 分区预选
        assert 'id="st-nav-list"' in body
        assert "/static/settings/core.js" in body
        assert "/static/settings/sections_basic.js" in body
        assert "/static/settings/sections_ext.js" in body
        assert "/static/settings/sections_ops.js" in body
        assert '"section": "%s"' % section in body
        # 旧页面不再直接下发
        assert "settings-tab-model" not in body


def test_settings_static_assets_are_whitelisted():
    client = _client()

    expected = {
        "settings.css": "text/css",
        "core.js": "application/javascript",
        "package_import.js": "application/javascript",
        "plugin_sections.js": "application/javascript",
        "sections_basic.js": "application/javascript",
        "sections_ext.js": "application/javascript",
        "sections_ops.js": "application/javascript",
    }
    for name, content_type in expected.items():
        response = client.get("/static/settings/" + name)
        assert response.status_code == 200, name
        assert response.headers["content-type"].startswith(content_type), name
        assert response.text.strip(), name

    assert client.get("/static/settings/../../app/.env").status_code == 404
    assert client.get("/static/settings/unknown.js").status_code == 404


def test_settings_page_keeps_path_picker_available():
    body = _client().get("/settings").text
    assert "myagent_path_picker.js" in body


def test_env_api_can_remove_keys(tmp_path, monkeypatch):
    import webui

    env_path = tmp_path / ".env"
    env_path.write_text(
        "WORK_DIR=./workspace\n"
        "CUSTOM_KNOB=1\n"
        "KEEP_ME=1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env_path)
    monkeypatch.setattr(webui, "refresh_executor_client_from_env", lambda: None)

    client = TestClient(webui.fastapi_app)
    response = client.post("/api/env", json={"remove": ["CUSTOM_KNOB"]})
    assert response.status_code == 200
    assert response.json()["ok"] is True

    text = env_path.read_text(encoding="utf-8")
    assert "CUSTOM_KNOB" not in text
    assert "KEEP_ME=1" in text
    assert "WORK_DIR=./workspace" in text

    bad = client.post("/api/env", json={"remove": "CUSTOM_KNOB"})
    assert bad.status_code == 400
    assert bad.json()["error"] == "remove must be a list"

    empty = client.post("/api/env", json={})
    assert empty.status_code == 400


def test_env_api_still_writes_values_with_removal(tmp_path, monkeypatch):
    import webui

    env_path = tmp_path / ".env"
    env_path.write_text("DROP_ME=1\n", encoding="utf-8")
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env_path)
    monkeypatch.setattr(webui, "refresh_executor_client_from_env", lambda: None)
    # The endpoint changes os.environ as well as the file; restore it at teardown.
    monkeypatch.setenv("ASK_USER_ENABLED", "1")

    client = TestClient(webui.fastapi_app)
    response = client.post("/api/env", json={"values": {"ASK_USER_ENABLED": "0"}, "remove": ["DROP_ME"]})
    assert response.status_code == 200

    text = env_path.read_text(encoding="utf-8")
    assert "DROP_ME" not in text
    assert "ASK_USER_ENABLED=0" in text
    assert webui.ask_user_enabled() is False


def test_skill_create_writes_skill_md(tmp_path, monkeypatch):
    import webui

    skills_root = tmp_path / "skills"
    monkeypatch.setattr(webui, "_skills_root_dir", lambda: skills_root)

    client = TestClient(webui.fastapi_app)
    response = client.post("/api/skills/create", json={"name": "pdf-report", "description": "读取 PDF 并生成摘要"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True

    skill_md = skills_root / "pdf-report" / "SKILL.md"
    assert skill_md.is_file()
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: pdf-report" in text
    assert 'description: "读取 PDF 并生成摘要"' in text

    again = client.post("/api/skills/create", json={"name": "pdf-report"})
    assert again.status_code == 400

    invalid = client.post("/api/skills/create", json={"name": "../escape"})
    assert invalid.status_code == 400


def test_skill_install_from_local_directory(tmp_path, monkeypatch):
    import webui

    skills_root = tmp_path / "skills"
    monkeypatch.setattr(webui, "_skills_root_dir", lambda: skills_root)

    source = tmp_path / "my-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: my-skill\ndescription: demo\n---\n", encoding="utf-8")

    client = TestClient(webui.fastapi_app)
    response = client.post("/api/skills/install", json={"source": str(source), "kind": "dir"})
    assert response.status_code == 200
    assert response.json()["name"] == "my-skill"
    assert (skills_root / "my-skill" / "SKILL.md").is_file()

    missing = client.post("/api/skills/install", json={"source": str(tmp_path / "nope"), "kind": "dir"})
    assert missing.status_code == 400

    no_source = client.post("/api/skills/install", json={})
    assert no_source.status_code == 400


def test_settings_sections_registered_in_assets():
    """9 个分区 id 必须同时出现在前端资产里，避免注册表被误删。"""
    root = Path(__file__).resolve().parents[1]
    static = root / "app" / "templates" / "static" / "settings"
    bundle = "\n".join(
        (static / name).read_text(encoding="utf-8")
        for name in ("core.js", "sections_basic.js", "sections_ext.js", "sections_ops.js")
    )
    for section_id in ("general", "models", "skills", "plugins", "hooks", "mcp", "security", "env", "paths"):
        assert "id: '%s'" % section_id in bundle or 'id: "%s"' % section_id in bundle, section_id
    # 后端资产白名单与磁盘文件一一对应
    for name in json.loads('["settings.css","core.js","sections_basic.js","sections_ext.js","sections_ops.js"]'):
        assert (static / name).is_file(), name


def test_env_snapshot_updates_keep_unrelated_lines():
    """_apply_env_updates 只动命中的键：注释、空行、别的键原样保留（保存不脏写的前提）。"""
    import webui

    original = (
        "# 联网搜索\n"
        "WEB_SEARCH_PROVIDER=duckduckgo\n"
        "\n"
        "# 另一个键\n"
        "KEEP_ME=1\n"
    )
    updated = webui._apply_env_updates(original, {"WEB_SEARCH_PROVIDER": "duckduckgo"})
    assert updated == original, "同值保存不应改动文件"

    changed = webui._apply_env_updates(original, {"WEB_SEARCH_PROVIDER": "tavily"})
    assert "# 联网搜索" in changed
    assert "KEEP_ME=1" in changed
    assert "WEB_SEARCH_PROVIDER=tavily" in changed

    # 空值会写成 KEY=（所以前端不该把没填的键提交上来）
    assert webui._apply_env_updates(original, {"SKILLS_DIR": ""}).endswith("SKILLS_DIR=\n")


def test_env_and_paths_save_only_submit_changes():
    """设置中心保存只提交改过的键：避免「点一次保存」把整屏默认项/空路径写进 .env。"""
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "templates" / "static" / "settings" / "sections_ops.js").read_text(encoding="utf-8")

    # 两份 save 都按快照比对，并把「清空」翻译成 remove
    assert source.count("const before = String(") == 2
    assert source.count("const remove = [];") == 2
    assert source.count("if (Object.keys(values).length) body.values = values;") == 2
    assert source.count("if (remove.length) body.remove = remove;") == 2
    assert source.count("if (!Object.keys(values).length && !remove.length) return;") == 2
    # 密钥只写：空值不提交
    assert "if (raw !== '') values[key] = raw;" in source
    # 不再存在「把整屏控件一次性提交」的旧写法
    assert "values[el.dataset.pathKey] = el.value.trim();" not in source
    assert "values[key] = raw;\n      });\n      if (!Object.keys(values).length) return;" not in source


def test_models_section_wires_drag_and_keyboard_reordering():
    """模型页必须保留排序能力（旧「高级设置」页有 drag-drop，设置中心不能用丢）。

    回归背景：设置中心上线后模型列表只剩「越靠上优先级越高」的文案，拖拽调整没了。
    """
    root = Path(__file__).resolve().parents[1]
    static = root / "app" / "templates" / "static" / "settings"
    source = (static / "sections_basic.js").read_text(encoding="utf-8")
    css = (static / "settings.css").read_text(encoding="utf-8")

    # 行 + 手柄 + 列表容器
    assert 'class="st-lrow st-profile-row" data-profile-id="' in source
    assert "data-profile-list" in source
    assert 'class="st-drag-handle"' in source
    # 只有手柄可拖，容器负责 dragover / drop
    assert "handle.draggable = true;" in source
    assert "handle.addEventListener('dragstart'" in source
    assert "list.addEventListener('dragover'" in source
    assert "list.addEventListener('drop'" in source
    assert "row.addEventListener('dragstart'" not in source
    # 拖动时实时让位（带位移动画），拖到列表外视为取消
    assert "function animateProfileRows(" in source
    assert "if (!state.dropped) { restore(state.beforeIds); return; }" in source
    # 落地提交到既有接口
    assert "api('/api/model_profiles/reorder', { method: 'POST', body: { ordered_ids: ids } })" in source
    # 键盘可达
    assert "ev.key === 'ArrowUp'" in source and "ev.key === 'ArrowDown'" in source
    # 手柄样式
    assert ".st-drag-handle" in css and ".st-profile-row.is-dragging" in css


def test_section_search_survives_same_section_reload():
    """分区内 reload() 不能清掉搜索词。

    回归背景：showSection() 无条件 `state.search = ''`，而「技能 / 环境变量」的 onSearch 正是
    `reload()` —— 结果是输入的字被立刻清空、列表不筛选（实测 36 行输入 TAVILY 仍是 36 行）。
    """
    root = Path(__file__).resolve().parents[1]
    core = (root / "app" / "templates" / "static" / "settings" / "core.js").read_text(encoding="utf-8")
    ops = (root / "app" / "templates" / "static" / "settings" / "sections_ops.js").read_text(encoding="utf-8")

    assert "const previousSection = state.section;" in core
    assert "if (previousSection !== id) state.search = '';" in core
    # 搜索输入 → state.search → section.onSearch
    assert "el.matches('[data-act=\"search\"]')" in core
    assert "state.search = el.value;" in core
    # 搜索只隐藏已挂载行，保留输入焦点和未保存字段。
    assert "onSearch() { A.filterSearchRows(); }" in ops


def test_font_size_is_a_dsh_style_stepper_with_px_preference():
    """字号学 DSH：整数 px 步进器（可输入 + 上下箭头 + px 单位），不再是三档分段控件。

    这条也防止有人把字号又改回「小/标准/大」三档——那正是用户要求换掉的形态。
    """
    root = Path(__file__).resolve().parents[1]
    static = root / "app" / "templates" / "static" / "settings"
    core = (static / "core.js").read_text(encoding="utf-8")
    basic = (static / "sections_basic.js").read_text(encoding="utf-8")
    css = (static / "settings.css").read_text(encoding="utf-8")
    host = (root / "frontend" / "src" / "app" / "modules" / "settings.js").read_text(encoding="utf-8")

    # 控件：药丸 + 可输入数值 + 两个箭头 + px 单位
    assert "fontStepper:" in core
    assert 'data-act="font-size-input"' in core
    assert 'data-act="font-up"' in core and 'data-act="font-down"' in core
    assert 'class="st-unit"' in core
    assert ".st-stepper {" in css and ".st-stepper-arrow" in css
    # 三档分段控件已经不在常规分区里
    assert "{ v: '0', t: t('小', 'S') }" not in basic
    assert "W.seg('font'" not in basic

    # 取值范围与默认值：12–20 px，缺省 16（沿用原「标准」档的观感）
    assert "const FONT_MIN = 12;" in core and "const FONT_MAX = 20;" in core
    assert "const FONT_LEVEL_PX = [14, 16, 17];" in core
    assert "const UI_FONT_MIN = 12;" in host and "const UI_FONT_MAX = 20;" in host

    # 新的 px 偏好键 + 旧的 0/1/2 档位键同步维护（老读者不受影响）
    assert "const LS_FONT_PX = 'myagent-font-size-px';" in core
    assert "const LS_UI_FONT_SIZE = 'myagent-font-size-px';" in host
    assert "fontPx: 'myagent-font-size-px'," in core                       # PREF_KEYS（回推宿主用）
    assert "A.setPrefs({ fontPx: String(next), font: String(levelForPx(next)) });" in basic
    assert "localStorage.setItem(LS_UI_FONT, String(levelForFontPx(next)));" in host
    # 聊天页按 px 应用，并暴露 data-font-size 便于外部核对
    assert "function applyFontSize(px, persist)" in host
    assert "document.documentElement.setAttribute('data-font-size', String(next));" in host
    assert "applyFontSize(getStoredFontPx(), false);" in host               # restoreUiPreferences 走 px


def test_skill_description_lives_in_a_hover_tip_only():
    """技能说明不进列表行，只在悬停/聚焦浮框里出现（用户要求：别把 description 铺出来）。"""
    root = Path(__file__).resolve().parents[1]
    static = root / "app" / "templates" / "static" / "settings"
    core = (static / "core.js").read_text(encoding="utf-8")
    basic = (static / "sections_basic.js").read_text(encoding="utf-8")
    css = (static / "settings.css").read_text(encoding="utf-8")

    # 技能行：名字挂 data-tip，副标题留空
    assert "W.tip(esc(s.name), s.description || '', 'st-mono')" in basic
    assert "W.lrow(esc(s.name), esc(s.description || '')," not in basic
    # 行里仍然可以按说明搜到（搜索逻辑不受影响）
    assert "s.name + ' ' + (s.description || '')" in basic
    # 浮框组件 + 样式 + 事件（悬停/聚焦显示，移开/滚动隐藏）
    assert "tip: (label, text, cls)" in core
    assert "data-tip=" in core
    assert "function showTip(target)" in core and "function hideTip()" in core
    assert "closest('[data-tip]')" in core
    assert "document.addEventListener('scroll', () => { hideTip(); }, true);" in core
    assert ".st-tip {" in css and ".st-tip-target" in css
    # 切分区时先收掉，免得浮框跨页残留
    assert "hideTip();\n    state.section = id;" in core


def test_mcp_tools_and_plugins_keep_descriptions_in_hover_tips():
    """MCP 27 条工具说明、插件简介同样只进浮框：列表里只留名字 / 短标识。"""
    root = Path(__file__).resolve().parents[1]
    ext = (root / "app" / "templates" / "static" / "settings" / "sections_ext.js").read_text(encoding="utf-8")

    # 统一的「有说明才挂浮框」小工具
    assert "const tipIf = (label, text, cls) => (text ? W.tip(label, text, cls) : label);" in ext
    # 插件行：名字挂浮框，副标题只剩组件汇总 / 命名空间
    assert "tipIf(esc(pluginName(p))" in ext
    assert "(p.description ? esc(p.description) + ' · ' : '')" not in ext
    # MCP 工具行：function_name 挂浮框，副标题留空
    assert "tipIf('<span class=\"st-mono\">' + esc(tool.function_name) + '</span>'," in ext
    assert "esc(tool.description || tool.tool_name || '')," not in ext
    # 插件贡献的设置入口同样
    assert "tipIf(esc(c.title || c.label || c.id || ''), c.description || '')" in ext
    # 卡片提示点出「悬停看说明」
    assert "悬停插件名看简介" in ext
    assert "悬停工具名看说明" in ext
