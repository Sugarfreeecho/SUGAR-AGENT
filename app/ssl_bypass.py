"""
ssl_bypass.py — SSL 证书验证绕过补丁
======================================
用法：在项目入口文件最顶上加上这一行：
    import ssl_bypass

作用：
  - 给所有 requests 请求自动加上 verify=False
  - 屏蔽 SSL 警告信息
  - huawei.com 等域名强制不走代理（见下方 NO_PROXY）
  - 兼容公司网关/自签名证书环境

控制开关：
  环境变量 SSL_BYPASS_ENABLED=1  (默认)  开启 SSL bypass
                SSL_BYPASS_ENABLED=0        关闭 SSL bypass（外网使用）

注意：仅用于下载公开数据的工具类项目。
      处理敏感数据时请改为添加正确的 CA 证书。
"""

import os
import requests
import urllib3

# ── 环境变量开关 ──────────────────────────────────────────────
# SSL_BYPASS_ENABLED=1 （默认）开启 bypass
# SSL_BYPASS_ENABLED=0 关闭 bypass（外网环境）
_bypass_enabled = os.getenv("SSL_BYPASS_ENABLED", "1").strip().lower()
if _bypass_enabled in ("0", "false", "no", "off"):
    print("[ssl_bypass] SSL bypass DISABLED (set SSL_BYPASS_ENABLED=1 to enable)")
    # 注入一个空函数，让 import ssl_bypass 仍然能成功，但不做任何 bypass
    def _noop():
        pass
else:
    _bypass_enabled = True

if _bypass_enabled is True:
    # 强制不使用任何代理访问 huawei.com 域名（及本地）
    os.environ["NO_PROXY"] = "huawei.com,myhuaweicloud.com,huaweicloud.com,127.0.0.1,localhost"
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)

    # 屏蔽 SSL 警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ── 方案A：注入默认参数 ──────────────────────────────────────
    _original_request = requests.Session.request

    def _patched_request(self, method, url, *args, **kwargs):
        if 'verify' not in kwargs:
            kwargs['verify'] = False
        return _original_request(self, method, url, *args, **kwargs)

    requests.Session.request = _patched_request

    # ── 方案B：也修补 requests.get / requests.post 等快捷方法 ──
    for method_name in ('get', 'post', 'put', 'delete', 'head', 'options', 'patch'):
        original = getattr(requests, method_name, None)
        if original:
            def _make_patch(orig_fn):
                def _patched(url, *args, **kwargs):
                    if 'verify' not in kwargs:
                        kwargs['verify'] = False
                    return orig_fn(url, *args, **kwargs)
                return _patched
            setattr(requests, method_name, _make_patch(original))

    print("[ssl_bypass] SSL bypass enabled")

    # ── httpx.Client SSL bypass（OpenAI SDK 使用）────────────────
    try:
        import httpx
        _original_httpx_init = httpx.Client.__init__

        def _patched_httpx_init(self, *args, **kwargs):
            if 'verify' not in kwargs:
                kwargs['verify'] = False
            return _original_httpx_init(self, *args, **kwargs)

        httpx.Client.__init__ = _patched_httpx_init
        print("[ssl_bypass] httpx.Client SSL bypass enabled")
    except ImportError:
        pass
