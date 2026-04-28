def test_check_env_mask_secret():
    from scripts.check_env import mask_secret
    assert mask_secret("") == ""
    assert mask_secret("1234") == "****"
    assert mask_secret("1234567890") == "1234****7890"
    assert mask_secret("ark_abcdefghijklmnopqrstuvwxyz") == "ark_****wxyz"
    assert mask_secret("ghp_abcdefghijklmnopqrstuvwxyz123456") == "ghp_****3456"

def test_check_env_missing_vars(monkeypatch, capsys):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    
    from scripts.check_env import check_env
    check_env()
    
    captured = capsys.readouterr()
    assert "FEISHU_APP_ID: MISSING" in captured.out
    assert "GITHUB_TOKEN: MISSING" in captured.out
    assert "Feishu ready: no" in captured.out
    assert "GitHub ready: no" in captured.out
    assert "Ark ready: no" in captured.out

def test_check_env_with_vars(monkeypatch, capsys):
    monkeypatch.setenv("FEISHU_APP_ID", "cli_1234567890abcdef")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret_abcdefghijklmnopqrstuvwxyz123456")
    monkeypatch.setenv("FEISHU_CHAT_ID", "oc_1234567890abcdef")
    
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_abcdefghijklmnopqrstuvwxyz123456")
    monkeypatch.setenv("GITHUB_OWNER", "test_owner")
    monkeypatch.setenv("GITHUB_REPO", "test_repo")
    monkeypatch.setenv("GITHUB_BASE_BRANCH", "main")
    
    from scripts.check_env import check_env
    check_env()
    
    captured = capsys.readouterr()
    assert "FEISHU_APP_ID: OK (cli_1234567890abcdef)" in captured.out
    assert "FEISHU_APP_SECRET: OK (secr****3456)" in captured.out
    assert "FEISHU_CHAT_ID: OK (oc_1234567890abcdef)" in captured.out
    
    assert "GITHUB_TOKEN: OK (ghp_****3456)" in captured.out
    assert "GITHUB_OWNER: OK (test_owner)" in captured.out
    assert "GITHUB_REPO: OK (test_repo)" in captured.out
    assert "GITHUB_BASE_BRANCH: OK (main)" in captured.out
    
    assert "Feishu ready: yes" in captured.out
    assert "GitHub ready: yes" in captured.out

def test_send_test_feishu_card_missing_config(monkeypatch, capsys):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    
    from scripts.send_test_feishu_card import send_test_feishu_card
    send_test_feishu_card()
    
    captured = capsys.readouterr()
    assert "Feishu config missing, fallback to mock card" in captured.out

def test_github_smoke_test_missing_config(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    
    from scripts.github_smoke_test import github_smoke_test
    issue = github_smoke_test()
    
    captured = capsys.readouterr()
    assert "Created Issue: #" in captured.out
    assert "mock://local/issue/" in captured.out
    assert "Scan result: Issue found in open bug issues" in captured.out
    assert "Comment result: success" in captured.out
    assert "Label result: success" in captured.out
    assert "Smoke test completed" in captured.out
    assert issue is not None
    assert 'number' in issue

def test_reset_demo_state_imports():
    import scripts.reset_demo_state  # noqa: F401
