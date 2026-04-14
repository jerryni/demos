#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AUTH_URL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
MESSAGE_URL = "https://open.larksuite.com/open-apis/im/v1/messages"


class LarkNotifierError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LarkNotifierError(f"HTTP {exc.code}: {body}") from exc


def load_lark_config(config_path: str | Path) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise LarkNotifierError(f"Lark 配置文件不存在: {path}")

    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("app_id", "app_secret"):
        if not config.get(key):
            raise LarkNotifierError(f"Lark 配置缺少字段: {key}")
    return config


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    response = _post_json(
        AUTH_URL,
        {"app_id": app_id, "app_secret": app_secret},
        {"Content-Type": "application/json; charset=utf-8"},
    )
    if response.get("code") != 0 or not response.get("tenant_access_token"):
        raise LarkNotifierError(f"获取 tenant_access_token 失败: {response}")
    return response["tenant_access_token"]


def send_text_message(
    tenant_access_token: str,
    receive_id: str,
    text: str,
    receive_id_type: str = "email",
) -> dict:
    query = urllib.parse.urlencode({"receive_id_type": receive_id_type})
    response = _post_json(
        f"{MESSAGE_URL}?{query}",
        {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        {
            "Authorization": f"Bearer {tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    if response.get("code") != 0:
        raise LarkNotifierError(f"发送 Lark 消息失败: {response}")
    return response


def send_text_from_config(
    config_path: str | Path,
    text: str,
    receive_id: str | None = None,
    receive_id_type: str | None = None,
) -> dict:
    config = load_lark_config(config_path)
    target_receive_id = receive_id or config.get("receive_id")
    target_receive_id_type = receive_id_type or config.get("receive_id_type", "email")

    if not target_receive_id:
        raise LarkNotifierError("未提供 receive_id，也未在配置文件中设置 receive_id")

    token = get_tenant_access_token(config["app_id"], config["app_secret"])
    return send_text_message(token, target_receive_id, text, target_receive_id_type)
