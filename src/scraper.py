"""
Boss直聘职位爬取模块
支持关键词搜索和推荐职位获取
"""

import json
import sys
import time
import os
import asyncio
import base64
import random
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from pathlib import Path

# 解决 Windows GBK 终端无法输出 emoji 的问题
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Random import get_random_bytes

from .models import JobDetail, SearchQuery, CITY_CODES, EXPERIENCE_CODES, EDUCATION_CODES, SALARY_CODES
from .config import Config

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # 添加项目根目录到路径

# 延迟导入 run_login_process，避免循环依赖（fastmcp 依赖重）
def _import_run_login_process():
    from .boss_zp.boss_zhipin_fastmcp_v2 import run_login_process
    return run_login_process

# 轻量导入：cookie_utils 不依赖 fastmcp
def _import_save_cookie_to_config():
    from .boss_zp.cookie_utils import save_cookie_to_config
    return save_cookie_to_config

class BossZhipinScraper:
    """Boss直聘职位爬取器"""

    # 搜索接口
    SEARCH_URL = "https://www.zhipin.com/wapi/zpgeek/search/joblist.json"
    # 推荐接口
    RECOMMEND_URL = "https://www.zhipin.com/wapi/zpgeek/pc/recommend/job/list.json"
    # 职位详情接口
    JOB_DETAIL_URL = "https://www.zhipin.com/wapi/zpgeek/job/card.json"

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self._setup_session()
        self._job_cache: List[JobDetail] = []
        # 浏览器会话状态（用于绕过安全验证的 API 请求）
        self._pw_instance = None
        self._pw_browser = None
        self._pw_context = None
        self._pw_page = None
        self._use_browser = False  # 是否处于浏览器模式
        self._security_passed = False  # 安全验证是否已通过（可用 fetch）
        self._last_run_meta: Dict[str, Any] = {
            "entered_browser_mode": False,
            "risk_blocked": False,
            "blank_page": False,
            "last_error": "",
        }

    def _reset_run_meta(self) -> None:
        self._last_run_meta = {
            "entered_browser_mode": False,
            "risk_blocked": False,
            "blank_page": False,
            "last_error": "",
        }

    def get_last_run_meta(self) -> Dict[str, Any]:
        return dict(self._last_run_meta)

    def _setup_session(self):
        """配置 HTTP 会话"""
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.zhipin.com/web/geek/job",
            "Origin": "https://www.zhipin.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        # 设置 Cookie
        if self.config.cookie:
            self.session.headers["Cookie"] = self.config.cookie
        # 同时将 cookie 解析到 session.cookies
        if self.config.cookie:
            for cookie_pair in self.config.cookie.split("; "):
                if "=" in cookie_pair:
                    name, value = cookie_pair.split("=", 1)
                    self.session.cookies.set(name.strip(), value.strip())

        if self.config.bst:
            self.session.headers["zp_token"] = self.config.bst

    def set_cookie(self, cookie: str, bst: str = ""):
        """设置登录Cookie"""
        self.config.cookie = cookie
        self.config.bst = bst
        self._setup_session()
        print("✅ Cookie 已更新")

    def load_cookie_from_mcp(self) -> bool:
        """从 MCP 服务器获取登录 Cookie (直接调用内置登录流程)"""
        try:
            print(f"🔐 尝试通过内置浏览器启动登录流程...")
            import asyncio

            run_login_process = _import_run_login_process()
            result = asyncio.run(run_login_process())

            if result.get("is_logged_in"):
                cookie = result.get("cookie")
                bst = result.get("bst")
                if cookie:
                    self.set_cookie(cookie, bst)
                    # Cookie 已在 run_login_process 中自动同步到 config.json
                    # 同时更新当前 config 对象
                    self.config.cookie = cookie
                    self.config.bst = bst or ""
                    print("🎉 成功获取并设置了 Cookie!")
                    return True
                else:
                    print("⚠️ 登录成功，但未能获取到 Cookie。")
                    return False
            else:
                print(f"❌ 登录失败: {result.get('message', '未知错误')}")
                return False

        except Exception as e:
            print(f"❌ 执行内置登录流程时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return bool(self.config.cookie)

    def _get_chrome_path(self) -> Optional[str]:
        """获取本地 Chrome 浏览器路径"""
        # 检查项目自带的 chrome
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_chrome = os.path.join(base_dir, "chrome-win64", "chrome.exe")
        if os.path.exists(local_chrome):
            return local_chrome
        return None  # 用 Playwright 默认的

    def pass_security_check(self, target_url: str = "https://www.zhipin.com/web/geek/job") -> bool:
        """使用无头浏览器通过 Boss直聘安全验证，获取 __zp_stoken__

        该方法会：
        1. 用无头浏览器打开目标页面（带上已有 Cookie）
        2. 等待 JS 执行完毕，生成 __zp_stoken__ 等安全 Cookie
        3. 提取完整 Cookie 更新到 session
        4. 同步保存到 config.json

        Args:
            target_url: 要访问的目标页面

        Returns:
            是否成功获取安全令牌
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("   ❌ 缺少 playwright，请执行: pip install playwright && playwright install chromium")
            return False

        print("\n   🔒 启动无头浏览器通过安全验证...")
        try:
            with sync_playwright() as p:
                # 尝试用本地 Chrome，否则用 Playwright 自带的
                chrome_path = self._get_chrome_path()
                launch_kwargs = {"headless": True}
                if chrome_path:
                    launch_kwargs["executable_path"] = chrome_path
                    print(f"   使用本地 Chrome: {chrome_path}")

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                # 设置已有 Cookie
                cookies = []
                if self.config.cookie:
                    for cookie_pair in self.config.cookie.split("; "):
                        if "=" in cookie_pair:
                            name, value = cookie_pair.split("=", 1)
                            cookies.append({
                                "name": name.strip(),
                                "value": value.strip(),
                                "domain": ".zhipin.com",
                                "path": "/"
                            })
                    context.add_cookies(cookies)
                    print(f"   已设置 {len(cookies)} 个已有 Cookie")

                page = context.new_page()

                # 访问目标页面，让 JS 自然执行安全验证
                print(f"   正在访问: {target_url}")
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                # 等待网络空闲
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass  # 超时不影响，继续执行

                # 预留时间让 JS 执行完成
                page.wait_for_timeout(5000)

                # 检查是否被重定向到 security-check 页面
                current_url = page.url
                if "security-check" in current_url:
                    print("   🛡️ 检测到安全验证页面，等待自动完成...")
                    # 等待安全检查完成后的跳转
                    try:
                        page.wait_for_url("**/web/geek/**", timeout=30000)
                        print("   ✅ 安全验证自动通过，已跳转")
                    except Exception:
                        # 没有跳转，但 Cookie 可能已经设置好了
                        print("   ⚠️ 等待跳转超时，尝试提取 Cookie")
                    # 再等待一下确保 Cookie 写入
                    page.wait_for_timeout(3000)

                # 提取所有 Cookie
                all_cookies = context.cookies()
                new_cookie_parts = []
                has_stoken = False
                for c in all_cookies:
                    new_cookie_parts.append(f"{c['name']}={c['value']}")
                    if c["name"] == "__zp_stoken__":
                        has_stoken = True
                        print(f"   ✅ 成功获取 __zp_stoken__")

                new_cookie_str = "; ".join(new_cookie_parts)

                # 也尝试从 JS 获取（某些 httpOnly cookie 只能通过 context.cookies 获取）
                if not has_stoken:
                    js_cookies = page.evaluate("() => document.cookie")
                    if "__zp_stoken__" in js_cookies:
                        has_stoken = True
                        new_cookie_str = js_cookies
                        print(f"   ✅ 通过 JS 获取到 __zp_stoken__")

                browser.close()

                if not new_cookie_str:
                    print("   ❌ 未能获取到任何 Cookie")
                    return False

                # 更新 session
                old_bst = self.config.bst
                self.set_cookie(new_cookie_str, old_bst)
                self.config.cookie = new_cookie_str

                # 同步到 config.json
                try:
                    save_fn = _import_save_cookie_to_config()
                    save_fn(new_cookie_str, old_bst)
                except Exception as e:
                    print(f"   ⚠️ 同步 config.json 失败: {e}")

                if has_stoken:
                    print("   ✅ 安全验证通过，Cookie 已更新\n")
                else:
                    print("   ⚠️ 未获取到 __zp_stoken__，但已更新其他 Cookie\n")

                return has_stoken

        except Exception as e:
            print(f"   ❌ 安全验证失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ========== 浏览器模式：通过页面导航拦截 API 响应 ==========

    def _open_browser_session(self) -> bool:
        """启动 Playwright 有头浏览器会话（headless=False）。

        使用有头模式 + 反检测是唯一可靠通过 Boss直聘安全验证的方式。
        headless 模式会陷入安全检查死循环。
        """
        if self._pw_page is not None:
            return True  # 已有会话

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("   ❌ 缺少 playwright，请执行: pip install playwright && playwright install chromium")
            return False

        try:
            print("   🌐 启动浏览器...")
            self._pw_instance = sync_playwright().start()

            chrome_path = self._get_chrome_path()
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--window-size=1920,1080",
            ]

            self._pw_browser = self._pw_instance.chromium.launch(
                headless=False,  # 必须有头模式，headless 会被安全系统检测
                executable_path=chrome_path if chrome_path else None,
                args=launch_args,
            )

            self._pw_context = self._pw_browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )

            # 反检测 JS
            self._pw_context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            """)

            # 注入已有 Cookie
            if self.config.cookie:
                cookies = []
                for pair in self.config.cookie.split("; "):
                    if "=" in pair:
                        name, value = pair.split("=", 1)
                        cookies.append({
                            "name": name.strip(),
                            "value": value.strip(),
                            "domain": ".zhipin.com",
                            "path": "/"
                        })
                self._pw_context.add_cookies(cookies)

            self._pw_page = self._pw_context.new_page()
            self._use_browser = True
            self._last_run_meta["entered_browser_mode"] = True
            print("   ✅ 浏览器就绪")
            return True
            return True

        except Exception as e:
            print(f"   ❌ 启动浏览器会话失败: {e}")
            self._close_browser_session()
            return False

    def _close_browser_session(self):
        """关闭浏览器会话，并将最新 Cookie 同步回 session 和 config.json。"""
        try:
            if self._pw_context:
                all_cookies = self._pw_context.cookies()
                if all_cookies:
                    new_cookie = "; ".join(
                        [f"{c['name']}={c['value']}" for c in all_cookies]
                    )
                    old_bst = self.config.bst
                    self.set_cookie(new_cookie, old_bst)
                    self.config.cookie = new_cookie
                    try:
                        save_fn = _import_save_cookie_to_config()
                        save_fn(new_cookie, old_bst)
                    except Exception:
                        pass
        except Exception:
            pass

        for attr in ("_pw_browser", "_pw_instance"):
            try:
                obj = getattr(self, attr, None)
                if obj:
                    if attr == "_pw_browser":
                        obj.close()
                    else:
                        obj.stop()
            except Exception:
                pass

        self._pw_page = None
        self._pw_context = None
        self._pw_browser = None
        self._pw_instance = None
        self._use_browser = False
        self._security_passed = False

    def _browser_navigate_and_capture(
        self,
        page_url: str,
        api_url_pattern: str,
        timeout: int = 30000,
        api_url: str = "",
        params: dict = None,
    ) -> Optional[dict]:
        """导航浏览器到搜索页面，通过 XHR 拦截捕获 API 响应。

        有头浏览器 + 反检测通过安全验证后，SPA 会自动发起 API 请求。
        安全检查通常需要 ~10 秒的重定向后自动通过。

        优先使用 XHR 拦截（最可靠），成功后再尝试 fetch 获取后续页面。

        Args:
            page_url: 要导航到的网页 URL（搜索页、推荐页等）
            api_url_pattern: API URL 中用于匹配的子串
            timeout: 等待超时时间 (ms)
            api_url: 完整 API URL（用于 fetch 调用）
            params: API 请求参数（用于 fetch 调用）

        Returns:
            API 响应的 JSON dict，或 None
        """
        if not self._pw_page:
            return None

        # --- 如果已过安全验证，优先尝试 fetch（更快） ---
        if self._security_passed and api_url and params:
            result = self._browser_fetch(api_url, params, api_url_pattern)
            if result is not None:
                return result

        # --- XHR 拦截方式：导航到页面，等待 SPA 发起 API 调用 ---
        captured: List[dict] = []

        def on_response(response):
            if api_url_pattern in response.url:
                try:
                    data = response.json()
                    captured.append(data)
                except Exception:
                    pass

        self._pw_page.on("response", on_response)

        try:
            print(f"   🔗 导航到页面 (安全检查约需10秒)...")
            self._pw_page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
            current_url = str(self._pw_page.url or "")
            if current_url.startswith("about:blank"):
                self._last_run_meta["blank_page"] = True
                self._last_run_meta["risk_blocked"] = True
                self._last_run_meta["last_error"] = "浏览器跳转到空白页，疑似触发风控"
                print("   ⚠️ 浏览器跳转到 about:blank，疑似触发风控")
        except Exception as e:
            print(f"   ⚠️ 导航: {e}")
            self._last_run_meta["risk_blocked"] = True
            self._last_run_meta["last_error"] = f"浏览器导航异常: {e}"

        # 轮询等待 API 响应（安全检查通常 ~10 秒完成）
        # 按产品要求固定等待 10 秒，避免长时间卡在安全检查轮询。
        max_wait_seconds = 10
        for i in range(max_wait_seconds):
            # 检查是否捕获到成功的 API 响应
            for r in captured:
                if r.get("code") == 0:
                    self._pw_page.remove_listener("response", on_response)
                    self._security_passed = True
                    print(f"   ✅ API 响应成功 ({i+1}s)")
                    return r
            time.sleep(1)
            if i > 0 and i % 5 == 0:
                print(f"   ⏳ 等待安全验证... ({i}s)")

        self._pw_page.remove_listener("response", on_response)

        # 检查是否有任何响应（即使不是 code=0）
        if captured:
            last = captured[-1]
            code = last.get("code")
            msg = last.get("message", "")
            print(f"   ⚠️ API 返回 code={code}, msg={msg}")
            if code != 0:
                self._last_run_meta["risk_blocked"] = True
                self._last_run_meta["last_error"] = msg or f"API 返回 code={code}"
            return last

        print(f"   ❌ 超时未捕获到 API 响应 (pattern={api_url_pattern})")
        self._last_run_meta["risk_blocked"] = True
        self._last_run_meta["last_error"] = "浏览器模式超时未捕获 API 响应"
        return None

    def _browser_fetch(self, api_url: str, params: dict, api_url_pattern: str = "") -> Optional[dict]:
        """在已通过安全验证的页面内通过 fetch 调用 API（更快捷的后续请求方式）。"""
        if not self._pw_page:
            return None
        from urllib.parse import urlencode
        full_url = f"{api_url}?{urlencode(params)}"
        try:
            result = self._pw_page.evaluate(
                """async (url) => {
                    try {
                        const resp = await fetch(url, {
                            credentials: 'include',
                            headers: { 'Accept': 'application/json, text/plain, */*' }
                        });
                        return await resp.json();
                    } catch(e) { return {_error: e.message}; }
                }""",
                full_url
            )
            if result and isinstance(result, dict):
                if result.get("_error"):
                    print(f"   [fetch] 错误: {result['_error']}")
                    return None
                code = result.get("code")
                if code == 0:
                    return result
                msg = result.get("message", "")
                if "访问行为异常" in msg or "安全验证" in msg:
                    # fetch 被拦截，标记安全验证失效
                    self._security_passed = False
                    self._last_run_meta["risk_blocked"] = True
                    self._last_run_meta["last_error"] = msg or "fetch 被安全验证拦截"
                    return None
                return result  # 其他错误码，仍返回数据
        except Exception as e:
            # 页面可能在导航中，context 被销毁
            self._security_passed = False
            self._last_run_meta["risk_blocked"] = True
            self._last_run_meta["last_error"] = f"浏览器 fetch 异常: {e}"
            return None
        return None

    def _build_search_page_url(self, params: dict) -> str:
        """根据搜索参数构建 Boss直聘搜索页面 URL。"""
        from urllib.parse import urlencode
        web_params = {}
        if "query" in params:
            web_params["query"] = params["query"]
        if "city" in params:
            web_params["city"] = params["city"]
        if "page" in params:
            web_params["page"] = params["page"]
        if "experience" in params:
            web_params["experience"] = params["experience"]
        if "degree" in params:
            web_params["degree"] = params["degree"]
        if "salary" in params:
            web_params["salary"] = params["salary"]
        return f"https://www.zhipin.com/web/geek/job?{urlencode(web_params)}"

    def _build_recommend_page_url(self, page: int = 1) -> str:
        """构建推荐职位页面 URL。"""
        return f"https://www.zhipin.com/web/geek/job?page={page}"

    def _try_requests_or_browser(
        self,
        api_url: str,
        params: dict,
        page_url: str = "",
        api_pattern: str = ""
    ) -> Optional[dict]:
        """统一请求入口：优先 requests，安全拦截时自动切换浏览器页面导航模式。

        Args:
            api_url: API 接口 URL（用于 requests 请求）
            params: 请求参数
            page_url: 浏览器模式下要导航的页面 URL
            api_pattern: 浏览器模式下要拦截的 API URL 匹配子串

        Returns:
            成功时返回 JSON dict；失败返回 None。
        """
        # ---- 如果已处于浏览器模式，直接用 fetch ----
        if self._use_browser:
            if api_pattern:
                data = self._browser_navigate_and_capture(
                    page_url, api_pattern,
                    api_url=api_url, params=params
                )
                if data and data.get("code") == 0:
                    return data
                if data:
                    print(f"   ❌ 浏览器模式 API 错误: {data.get('message', '未知错误')}")
            return None

        # ---- 常规 requests 请求 ----
        try:
            resp = self.session.get(api_url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"   ❌ 网络请求失败: {e}")
            return None

        if data.get("code") == 0:
            return data

        error_msg = data.get("message", "未知错误")
        print(f"   ❌ API 错误: {error_msg}")

        # 非安全验证错误，直接返回失败
        # Boss 端常见拦截文案包括: 访问行为异常 / 您的环境存在异常 / 安全验证 / token 失效
        security_markers = (
            "访问行为异常",
            "环境存在异常",
            "环境异常",
            "安全验证",
        )
        if not (any(marker in error_msg for marker in security_markers)
            or "token" in error_msg.lower()):
            return None

        # ---- 安全验证拦截 → 直接切换浏览器模式 ----
        print("   ⚠️ 检测到安全验证，切换为浏览器模式...")
        if not self._open_browser_session():
            return None

        if api_pattern:
            data = self._browser_navigate_and_capture(
                page_url, api_pattern,
                api_url=api_url, params=params
            )
            if data and data.get("code") == 0:
                return data
            if data:
                print(f"   ❌ 浏览器模式 API 错误: {data.get('message', '未知错误')}")
        return None

    def search_jobs(
        self,
        query: SearchQuery,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> List[JobDetail]:
        """
        按关键词搜索职位

        Args:
            query: 搜索参数

        Returns:
            职位详情列表
        """
        if not self.is_logged_in():
            print("❌ 未登录，请先设置 Cookie")
            return []

        self._reset_run_meta()

        all_jobs: List[JobDetail] = []
        current_page = query.page

        print(f"\n🔍 开始搜索: 关键词='{query.keyword}', 城市={query.city_name}")
        print(f"   经验={query.experience or '不限'}, 薪资={query.salary or '不限'}")
        print(f"   计划爬取 {query.max_pages} 页\n")

        try:
            for page_num in range(query.max_pages):
                current_page = query.page + page_num

                params = {
                    "query": query.keyword,
                    "city": query.city,
                    "page": current_page,
                    "pageSize": query.page_size,
                    "_": int(time.time() * 1000),
                }

                # 添加可选筛选条件
                if query.experience and query.experience in EXPERIENCE_CODES:
                    exp_code = EXPERIENCE_CODES[query.experience]
                    if exp_code:
                        params["experience"] = exp_code

                if query.education and query.education in EDUCATION_CODES:
                    edu_code = EDUCATION_CODES[query.education]
                    if edu_code:
                        params["degree"] = edu_code

                if query.salary and query.salary in SALARY_CODES:
                    sal_code = SALARY_CODES[query.salary]
                    if sal_code:
                        params["salary"] = sal_code

                try:
                    print(f"   📄 正在获取第 {current_page} 页...")

                    # 构建浏览器模式下的页面 URL
                    page_url = self._build_search_page_url(params)
                    data = self._try_requests_or_browser(
                        self.SEARCH_URL, params,
                        page_url=page_url,
                        api_pattern="search/joblist.json"
                    )

                    if data is None:
                        break

                    zp_data = data.get("zpData", {})
                    job_list = zp_data.get("jobList", [])

                    if not job_list:
                        print(f"   📭 第 {current_page} 页没有更多职位")
                        break

                    page_jobs = []
                    for job_data in job_list:
                        job = JobDetail.from_api_response(job_data)
                        page_jobs.append(job)

                    all_jobs.extend(page_jobs)
                    print(f"   ✅ 第 {current_page} 页: 获取 {len(page_jobs)} 个职位")

                    if progress_callback:
                        progress_callback(page_num + 1, query.max_pages, len(all_jobs))

                    # 检查是否还有更多
                    has_more = zp_data.get("hasMore", False)
                    if not has_more:
                        print(f"   📭 没有更多职位了")
                        break

                    # 请求间隔，避免被封
                    if page_num < query.max_pages - 1:
                        delay = max(0.3, self.config.request_delay * 0.6) + random.uniform(0.2, 0.6)
                        print(f"   ⏳ 等待 {delay:.1f} 秒...")
                        time.sleep(delay)

                except Exception as e:
                    print(f"   ❌ 解析失败: {e}")
                    break
        finally:
            # 清理浏览器会话
            if self._use_browser:
                self._close_browser_session()

        print(f"\n✅ 搜索完成! 共获取 {len(all_jobs)} 个职位\n")

        self._job_cache.extend(all_jobs)
        return all_jobs

    def get_recommend_jobs(
        self,
        page: int = 1,
        max_pages: int = 3,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> List[JobDetail]:
        """
        获取推荐职位

        Args:
            page: 起始页码
            max_pages: 最大页数

        Returns:
            职位详情列表
        """
        if not self.is_logged_in():
            print("❌ 未登录，请先设置 Cookie")
            return []

        self._reset_run_meta()

        all_jobs: List[JobDetail] = []

        print(f"\n🌟 获取推荐职位，计划获取 {max_pages} 页\n")

        try:
            for page_num in range(max_pages):
                current_page = page + page_num

                params = {
                    "page": current_page,
                    "pageSize": 15,
                    "_": int(time.time() * 1000),
                }

                try:
                    print(f"   📄 正在获取第 {current_page} 页推荐职位...")

                    page_url = self._build_recommend_page_url(current_page)
                    data = self._try_requests_or_browser(
                        self.RECOMMEND_URL, params,
                        page_url=page_url,
                        api_pattern="recommend/job/list.json"
                    )

                    if data is None:
                        break

                    zp_data = data.get("zpData", {})
                    job_list = zp_data.get("jobList", [])

                    if not job_list:
                        print(f"   📭 没有更多推荐职位")
                        break

                    page_jobs = [JobDetail.from_api_response(j) for j in job_list]
                    all_jobs.extend(page_jobs)
                    print(f"   ✅ 第 {current_page} 页: 获取 {len(page_jobs)} 个职位")

                    if progress_callback:
                        progress_callback(page_num + 1, max_pages, len(all_jobs))

                    if not zp_data.get("hasMore", False):
                        break

                    if page_num < max_pages - 1:
                        delay = max(0.3, self.config.request_delay * 0.6) + random.uniform(0.2, 0.6)
                        time.sleep(delay)

                except Exception as e:
                    print(f"   ❌ 获取推荐职位失败: {e}")
                    break
        finally:
            if self._use_browser:
                self._close_browser_session()

        print(f"\n✅ 推荐职位获取完成! 共 {len(all_jobs)} 个\n")

        self._job_cache.extend(all_jobs)
        return all_jobs

    def save_jobs(self, jobs: List[JobDetail], filename: Optional[str] = None) -> str:
        """
        保存职位数据到 JSON 文件

        Args:
            jobs: 职位列表
            filename: 文件名 (不含路径)

        Returns:
            保存的文件路径
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, self.config.data_dir)
        os.makedirs(data_dir, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_{timestamp}.json"

        filepath = os.path.join(data_dir, filename)

        jobs_data = [job.to_dict() for job in jobs]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(jobs_data, f, ensure_ascii=False, indent=2)

        print(f"💾 已保存 {len(jobs)} 个职位到: {filepath}")
        return filepath

    def load_jobs(self, filepath: str) -> List[JobDetail]:
        """从 JSON 文件加载职位数据"""
        with open(filepath, "r", encoding="utf-8") as f:
            jobs_data = json.load(f)

        jobs = []
        for data in jobs_data:
            job = JobDetail(**data)
            jobs.append(job)

        print(f"📂 从 {filepath} 加载了 {len(jobs)} 个职位")
        return jobs

    def get_cached_jobs(self) -> List[JobDetail]:
        """获取缓存的全部职位"""
        return self._job_cache

    def clear_cache(self):
        """清空缓存"""
        self._job_cache.clear()
        print("🧹 缓存已清空")