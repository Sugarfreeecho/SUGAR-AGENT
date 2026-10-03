import pytest

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


def test_normalize_dist_name_matches_pep503():
    assert check_requirements._normalize_dist_name("Python_Magic") == "python-magic"
    assert check_requirements._normalize_dist_name("PyYAML") == "pyyaml"
    assert check_requirements._normalize_dist_name("zope.interface") == "zope-interface"


def test_missing_distributions_matches_installed_names_case_insensitively():
    assert check_requirements.missing_distributions(["pytest", "PyTest"]) == []
    assert check_requirements.missing_distributions(
        ["pytest", "definitely-not-installed-package-xyz"]
    ) == ["definitely-not-installed-package-xyz"]


def test_main_reports_missing_packages_and_returns_one(tmp_path, monkeypatch, capsys):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "pytest\ndefinitely-not-installed-package-xyz\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_requirements, "REQUIREMENTS_FILE", requirements)

    assert check_requirements.main() == 1
    assert "definitely-not-installed-package-xyz" in capsys.readouterr().err


def test_main_returns_zero_when_environment_satisfies_requirements(
    tmp_path, monkeypatch, capsys
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pytest\n", encoding="utf-8")
    monkeypatch.setattr(check_requirements, "REQUIREMENTS_FILE", requirements)

    assert check_requirements.main() == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("requirement,version,satisfied", [
    ("demo>=2,<3", "1.9", False),
    ("demo>=2,<3", "2.1", True),
    ("demo>=2,<3", "3.0", False),
    ("demo==2.1", "2.0", False),
    ("demo~=2.1.0", "2.2", False),
    ("demo!=2.1,>=2", "2.1", False),
    ("demo>=2", "invalid-version", False),
])
def test_version_constraints_are_checked(requirement, version, satisfied):
    missing = check_requirements.missing_distributions([requirement], installed={"demo": version})
    assert (not missing) is satisfied


def test_main_detects_changed_requirement_with_existing_distribution(tmp_path, monkeypatch, capsys):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("demo[feature]>=2\n", encoding="utf-8")
    monkeypatch.setattr(check_requirements, "REQUIREMENTS_FILE", requirements)
    monkeypatch.setattr(check_requirements, "installed_distributions", lambda: {"demo": "1.0"})
    assert check_requirements.main() == 1
    assert "demo[feature]>=2" in capsys.readouterr().err
    requirements.write_text("demo[feature]>=1\n", encoding="utf-8")
    assert check_requirements.main() == 0
