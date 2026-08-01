"""Pre-approved documentation hosts for read-only ``web_fetch`` calls.

Mirrors Claude Code's WebFetch preapproved list: fetching a docs page is a
read-only GET, so hitting a curated documentation site should not produce an
approval prompt every time. This list is deliberately scoped to ``web_fetch``
only:

- ``web_download`` (writes files) and shell/network commands never inherit it.
- Upload-capable or general-purpose hosts (huggingface.co, kaggle.com,
  nuget.org, ...) are excluded on purpose to keep the exfiltration surface
  small (same reasoning as Claude Code's ``preapproved.ts``).

Users can extend the list with the ``MYAGENT_WEB_FETCH_PREAPPROVED_DOMAINS``
environment variable (comma-separated) or through the settings UI, which
persists the edited list in the security store.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit


PREAPPROVED_HOSTS: frozenset[str] = frozenset(
    {
        # Language & platform docs
        "docs.python.org",
        "en.cppreference.com",
        "docs.oracle.com",
        "learn.microsoft.com",
        "developer.mozilla.org",
        "go.dev",
        "pkg.go.dev",
        "www.php.net",
        "docs.swift.org",
        "kotlinlang.org",
        "ruby-doc.org",
        "doc.rust-lang.org",
        "www.typescriptlang.org",
        # Web & frontend frameworks
        "react.dev",
        "angular.io",
        "vuejs.org",
        "nextjs.org",
        "nuxt.com",
        "expressjs.com",
        "nodejs.org",
        "bun.sh",
        "getbootstrap.com",
        "tailwindcss.com",
        "d3js.org",
        "threejs.org",
        "redux.js.org",
        "webpack.js.org",
        "vitejs.dev",
        "jestjs.io",
        "reactrouter.com",
        # Python frameworks & libraries
        "docs.djangoproject.com",
        "flask.palletsprojects.com",
        "fastapi.tiangolo.com",
        "pandas.pydata.org",
        "numpy.org",
        "www.tensorflow.org",
        "pytorch.org",
        "scikit-learn.org",
        "matplotlib.org",
        "requests.readthedocs.io",
        "jupyter.org",
        "python-poetry.org",
        "docs.pytest.org",
        # PHP / Java / .NET
        "laravel.com",
        "symfony.com",
        "wordpress.org",
        "docs.spring.io",
        "hibernate.org",
        "tomcat.apache.org",
        "gradle.org",
        "maven.apache.org",
        "asp.net",
        "dotnet.microsoft.com",
        "blazor.net",
        # Mobile
        "reactnative.dev",
        "docs.flutter.dev",
        "developer.apple.com",
        "developer.android.com",
        # Databases & data
        "www.mongodb.com",
        "redis.io",
        "www.postgresql.org",
        "dev.mysql.com",
        "www.sqlite.org",
        "graphql.org",
        "prisma.io",
        "clickhouse.com",
        # Cloud & DevOps
        "docs.aws.amazon.com",
        "cloud.google.com",
        "kubernetes.io",
        "www.docker.com",
        "www.terraform.io",
        "www.ansible.com",
        "vercel.com",
        "docs.netlify.com",
        "nginx.org",
        "www.elastic.co",
        "prometheus.io",
        # Tools & testing
        "cypress.io",
        "playwright.dev",
        "eslint.org",
        "prettier.io",
        "git-scm.com",
        "www.gnu.org",
        "www.kernel.org",
        # Chinese-friendly docs
        "zh-hans.react.dev",
        "www.runoob.com",
        "www.liaoxuefeng.com",
        "developer.aliyun.com",
        "cloud.tencent.com",
        # Misc frequently referenced
        "www.rfc-editor.org",
        "www.w3.org",
        "www.w3schools.com",
        "devdocs.io",
    }
)


def _normalize_host(host: str) -> str:
    return str(host or "").strip().lower().rstrip(".").removeprefix("www.")


def _env_extra_hosts() -> frozenset[str]:
    raw = os.environ.get("MYAGENT_WEB_FETCH_PREAPPROVED_DOMAINS", "")
    return frozenset(
        _normalize_host(item)
        for item in str(raw).split(",")
        if str(item).strip()
    )


def _host_matches_list(host: str, hosts: frozenset[str]) -> bool:
    normalized = _normalize_host(host)
    if not normalized:
        return False
    if normalized in hosts:
        return True
    parts = normalized.split(".")
    for i in range(1, len(parts) - 1):
        if ".".join(parts[i:]) in hosts:
            return True
    return False


def is_preapproved_host(host: str) -> bool:
    """True when the host (or a matching parent domain) is pre-approved."""
    return _host_matches_list(host, PREAPPROVED_HOSTS | _env_extra_hosts())


def is_preapproved_host_with_user_list(host: str, user_hosts: frozenset[str]) -> bool:
    """Built-in list plus user-persisted domains (from the settings UI)."""
    return _host_matches_list(
        host, PREAPPROVED_HOSTS | _env_extra_hosts() | frozenset(user_hosts)
    )


def is_preapproved_url(url: str) -> bool:
    try:
        parsed = urlsplit(str(url or ""))
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    return is_preapproved_host(parsed.hostname)
