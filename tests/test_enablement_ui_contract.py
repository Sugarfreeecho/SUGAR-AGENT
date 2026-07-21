from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_model_profile_switcher_and_configuration_page_expose_enablement_controls():
    switcher = (ROOT / "frontend/src/app/modules/model-profiles.js").read_text(encoding="utf-8")
    settings = (ROOT / "app/templates/advance_config.html").read_text(encoding="utf-8")
    backend = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "data-toggle-profile-id" in switcher
    assert "setModelProfileEnabled" in switcher
    assert "data-act='toggle'" in settings
    assert "setConfiguredProfileEnabled" in settings
    assert '@fastapi_app.post("/api/model_profiles/{profile_id}/enabled")' in backend


def test_skill_picker_exposes_enablement_controls():
    picker = (ROOT / "frontend/src/app/modules/skill-picker.js").read_text(encoding="utf-8")
    backend = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "skill-picker-toggle" in picker
    assert "setSkillPickerEnabled" in picker
    assert "reconcileSelectedSkillsWithEnabledCatalog" in picker
    assert '@fastapi_app.post("/api/skills/{skill_name}/enabled")' in backend
