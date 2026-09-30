from qishui.storage import Journal


def test_existing_settings_gain_android_defaults_without_losing_target(tmp_path, monkeypatch):
    from qishui.storage import load_settings
    monkeypatch.setenv("QISHUI_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.json").write_text('{"target": 7, "hdc": "hdc.exe"}', "utf-8")
    settings = load_settings()
    assert settings["target"] == 7 and settings["hdc"] == "hdc.exe"
    assert settings["platform"] == "auto" and settings["adb"] == ""


def test_success_is_durable_and_idempotent(tmp_path):
    path = tmp_path / 'history.db'
    j = Journal(path)
    s = j.session(2)
    r = j.begin(s)
    assert j.counts(s)['started'] == 0
    j.watching(r)
    assert j.counts(s)['started'] == 1
    assert j.success(r,'verified')
    assert not j.success(r,'duplicate')
    j.close()
    j = Journal(path)
    assert j.counts(s)['success'] == 1


def test_crash_never_converts_unconfirmed_to_success(tmp_path):
    j = Journal(tmp_path / 'history.db')
    s = j.session(2)
    r = j.begin(s)
    j.watching(r)
    j.recover()
    assert j.counts(s) == {'success':0,'started':1,'uncertain':1}
    assert not j.success(r,'stale')


def test_unobserved_attempt_is_not_counted_as_started(tmp_path):
    j=Journal(tmp_path/'history.db')
    s=j.session(2)
    j.begin(s)
    j.recover()
    assert j.counts(s)=={'success':0,'started':0,'uncertain':1}
