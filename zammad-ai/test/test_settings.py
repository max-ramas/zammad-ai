from app.settings.settings import get_settings


def test_get_settings_ignores_local_yaml_in_unittest_mode(tmp_path, monkeypatch) -> None:
    broken_yaml = tmp_path / "config.yaml"
    broken_yaml.write_text("triage: [", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZAMMAD_AI_MODE", "unittest")
    monkeypatch.setenv("ZAMMAD_AI_DISABLE_YAML", "1")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.mode == "unittest"
    assert settings.triage.prompts.type == "string"
