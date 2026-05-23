"""Boss 直聘 MCP 二维码登录服务。"""

from __future__ import annotations

import base64
import time
from typing import Dict

import requests
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad

from app.utils.task_tracker import update_mcp_login_task
from src.boss_zp.cookie_utils import save_cookie_to_config


def generate_boss_fp() -> str:
    i_str = "8048b8676fb7d3d8952276e6e98e0bde.f2dc7a63c4b0fbfa4b51a07e2710cf83.fef7e750fc3a1e6327e8a880915aee9c.ae00f848beb1aa591d71d5a80dd3bd95"
    e_b64 = "clRwXUJBK1VKK0k0IWFbbQ=="

    key_bytes = base64.b64decode(e_b64)
    plaintext_bytes = i_str.encode("utf-8")
    iv_bytes = get_random_bytes(16)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded_plaintext = pad(plaintext_bytes, AES.block_size)
    ciphertext_bytes = cipher.encrypt(padded_plaintext)
    result_bytes = iv_bytes + ciphertext_bytes
    return base64.b64encode(result_bytes).decode("utf-8")


def parse_set_cookie(set_cookie_headers: str) -> tuple[str, str]:
    cookie_str = ""
    bst_value = ""
    if not set_cookie_headers:
        return cookie_str, bst_value

    cookies: Dict[str, str] = {}
    cookie_parts = set_cookie_headers.split(",")
    for part in cookie_parts:
        if "=" not in part:
            continue
        name_value = part.strip().split(";", 1)[0].strip()
        if "=" not in name_value:
            continue
        name, value = name_value.split("=", 1)
        cookies[name.strip()] = value.strip()

    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    if "bst" in cookies:
        bst_value = cookies["bst"]
    return cookie_str, bst_value


def run_mcp_login_task(task_id: str) -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.zhipin.com/web/user/?ka=header-login",
            "Origin": "https://www.zhipin.com",
        }
    )

    try:
        update_mcp_login_task(task_id, step="qr_preparing", message="正在生成登录二维码...")

        randkey_url = "https://www.zhipin.com/wapi/zppassport/captcha/randkey"
        rand_resp = session.post(randkey_url, timeout=15)
        rand_resp.raise_for_status()
        qr_id = rand_resp.json()["zpData"]["qrId"]

        qr_url = f"https://www.zhipin.com/wapi/zpweixin/qrcode/getqrcode?content={qr_id}"
        qr_resp = session.get(qr_url, timeout=15)
        qr_resp.raise_for_status()

        update_mcp_login_task(
            task_id,
            step="qr_generated",
            message="二维码已生成，请使用 Boss 直聘 APP 扫码。",
            qr_id=qr_id,
            qr_ready=True,
            qr_bytes=qr_resp.content,
        )

        scan_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scan?uuid={qr_id}"
        scan_deadline = time.time() + 240
        scanned = False
        while time.time() < scan_deadline:
            try:
                scan_resp = session.get(scan_url, timeout=35)
                if scan_resp.status_code == 200 and scan_resp.json().get("scaned"):
                    scanned = True
                    update_mcp_login_task(
                        task_id,
                        step="scanned",
                        message="已检测到扫码，正在等待手机端确认登录...",
                    )
                    break
            except requests.exceptions.ReadTimeout:
                pass
            except Exception:
                pass
            time.sleep(1)

        if not scanned:
            update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="等待扫码超时，请重新发起 MCP 登录。",
            )
            return

        confirm_url = f"https://www.zhipin.com/wapi/zppassport/qrcode/scanLogin?qrId={qr_id}&status=1"
        confirm_deadline = time.time() + 240
        confirmed = False
        while time.time() < confirm_deadline:
            try:
                confirm_resp = session.get(confirm_url, timeout=35)
                if confirm_resp.status_code == 200:
                    confirmed = True
                    update_mcp_login_task(
                        task_id,
                        step="confirmed",
                        message="手机端已确认，正在获取登录 Cookie...",
                    )
                    break
            except requests.exceptions.ReadTimeout:
                pass
            except Exception:
                pass
            time.sleep(1)

        if not confirmed:
            update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="等待手机确认超时，请重新发起 MCP 登录。",
            )
            return

        update_mcp_login_task(task_id, step="cookie", message="正在交换登录凭证...")
        fp = generate_boss_fp()
        dispatcher_url = (
            f"https://www.zhipin.com/wapi/zppassport/qrcode/dispatcher?qrId={qr_id}&pk=header-login&fp={fp}"
        )
        cookie_resp = session.get(dispatcher_url, allow_redirects=False, timeout=20)
        cookie_str, bst_value = parse_set_cookie(cookie_resp.headers.get("Set-Cookie", ""))

        if not cookie_str:
            update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="Cookie 获取失败，请重新发起登录。",
            )
            return

        update_mcp_login_task(task_id, step="saving", message="已获取 Cookie，正在写入配置...")
        save_ok = save_cookie_to_config(cookie_str, bst_value)
        if not save_ok:
            update_mcp_login_task(
                task_id,
                status="failed",
                ok=False,
                step="failed",
                message="Cookie 写入失败，请检查配置文件权限。",
            )
            return

        update_mcp_login_task(
            task_id,
            status="done",
            ok=True,
            step="logged_in",
            message="登录成功，Cookie 已保存。",
        )
    except Exception as e:
        update_mcp_login_task(
            task_id,
            status="failed",
            ok=False,
            step="failed",
            message=f"MCP 登录异常: {e}",
        )
