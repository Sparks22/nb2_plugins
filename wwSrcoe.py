import httpx
import logging

try:
    from nonebot.log import logger as nb_logger
except Exception:
    nb_logger = None

_logger = nb_logger or logging.getLogger("wwSrcoe")

def _redact_token(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 12:
        return "******"
    return f"{value[:6]}...{value[-6:]}"

def _safe_headers(headers: dict) -> dict:
    safe = dict(headers)
    if "token" in safe:
        safe["token"] = _redact_token(safe.get("token"))
    return safe

def _truncate(text: str, limit: int = 2000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"...(truncated,{len(text)} chars)"

# 默认请求头配置
# 这些配置保留了原始文件中的硬编码值，作为默认请求头
# 调用 send_kuro_request 时传入的 token 会覆盖这里的默认 token
DEFAULT_HEADERS = {
    "Host": "api.kurobbs.com",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "sec-ch-ua": '"Android WebView";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
    "source": "android",
    "b-at": "52d84678a02944be9ad024a273efef5a",
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; MEIZU 21 Pro Build/UKQ1.230917.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/117.0.0.0 Mobile Safari/537.36 Kuro/2.10.0 KuroGameBox/2.10.0",
    "sec-ch-ua-mobile": "?1",
    "Content-Type": "application/x-www-form-urlencoded",
    "did": "EE8A7E4C915F1CD7EDE605AEAB96D9FBF3C0915D",
    "Accept": "application/json, text/plain, */*",
    "devCode": "39.144.144.52, Mozilla/5.0 (Linux; Android 14; MEIZU 21 Pro Build/UKQ1.230917.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/117.0.0.0 Mobile Safari/537.36 Kuro/2.10.0 KuroGameBox/2.10.0",
    # 默认 token，如果调用时传入 token 参数，将会覆盖此值
    "token": "eyJhbGciOiJIUzI1NiJ9.eyJjcmVhdGVkIjoxNzY4NjQ1NjcxNDkxLCJ1c2VySWQiOjIwOTEwNTM1fQ.YD3jbfC02hNPzbrprnPiu1vgKB02eesWbRAChHk6Q64",
    "sec-ch-ua-platform": '"Android"',
    "Origin": "https://web-static.kurobbs.com",
    "X-Requested-With": "com.kurogame.kjq",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
}

async def send_kuro_request(url: str, method: str, token: str, data: dict) -> httpx.Response:
    """
    封装接口调用
    :param url: 请求的 URL
    :param method: 请求方法 (POST/GET)
    :param token: 请求头里的 token
    :param data: 请求体 (POST data 或 GET params)
    :return: httpx.Response
    """
    headers = DEFAULT_HEADERS.copy()
    if token:
        headers["token"] = token
        
    async with httpx.AsyncClient() as client:
        _logger.info(f"[kuro] request method={method.upper()} url={url} headers={_safe_headers(headers)} data={data}")
        if method.upper() == "POST":
            resp = await client.post(url, headers=headers, data=data, timeout=10)
        else:
            resp = await client.get(url, headers=headers, params=data, timeout=10)
        _logger.info(f"[kuro] response status={resp.status_code} url={url} text={_truncate(resp.text)}")
        return resp
