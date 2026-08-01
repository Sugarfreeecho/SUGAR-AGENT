from app import check_requirements


def test_platform_markers_skip_non_matching_dependencies(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        'always>=1\n'
        'windows-only; sys_platform == "win32"\n'
        'not-windows; sys_platform != "win32"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_requirements, "REQUIREMENTS_FILE", requirements)

    names = check_requirements.load_required_distributions()

    assert "always" in names
    assert ("windows-only" in names) is (check_requirements.sys.platform == "win32")
    assert ("not-windows" in names) is (check_requirements.sys.platform != "win32")


def test_extras_and_inline_comments_are_parsed(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "markitdown[pptx]  # document support\nopenai>=1.30,<3\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_requirements, "REQUIREMENTS_FILE", requirements)

    assert check_requirements.load_required_distributions() == ["markitdown", "openai"]
