import asyncio
import os
import random
from datetime import datetime

import httpx
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import TimeoutError


# ─── 环境变量读取 ───────────────────────────────────────────────
LOGIN_EMAIL = os.environ.get("LOGIN_EMAIL", "")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")


class StepLogger:
    """收集每一步的执行日志，最终生成 Markdown 报告。"""

    def __init__(self):
        self.steps: list[dict] = []
        self.start_time = datetime.now()

    def log(self, emoji: str, message: str):
        """同时打印到控制台并记录到内部列表。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{emoji} {message}")
        self.steps.append({"time": timestamp, "emoji": emoji, "message": message})

    def build_markdown(self) -> str:
        duration = datetime.now() - self.start_time
        lines = [
            f"## 🤖 自动化任务执行报告",
            f"",
            f"**执行时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**总耗时**: {duration.total_seconds():.1f} 秒",
            f"",
            f"---",
            f"",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. `{step['time']}` {step['emoji']} {step['message']}")
        lines.append("")
        lines.append("---")
        lines.append(f"_由自动化脚本生成_")
        return "\n".join(lines)


async def send_telegram(markdown_text: str):
    """将 Markdown 报告推送到 Telegram。"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 推送。")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": markdown_text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200 and resp.json().get("ok"):
                print("✅ 执行报告已成功推送到 Telegram！")
            else:
                print(f"⚠️ Telegram 推送失败: {resp.text}")
    except Exception as e:
        print(f"⚠️ Telegram 推送异常: {e}")


async def run():
    logger = StepLogger()

    # ─── 环境变量校验 ───────────────────────────────────────────
    if not LOGIN_EMAIL or not LOGIN_PASSWORD:
        logger.log("❌", "未设置 LOGIN_EMAIL 或 LOGIN_PASSWORD 环境变量，脚本终止。")
        await send_telegram(logger.build_markdown())
        return

    logger.log("🚀", "正在启动 Camoufox 浏览器...")

    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
    # ✅ 拦截页面未捕获异常，防止 Playwright 驱动崩溃
        page.on("pageerror", lambda err: print(f"[页面异常已忽略] {err}"))

        url = "https://justrunmy.app/id/account/login"
        logger.log("🌐", f"正在打开页面: {url}")
        await page.goto(url)
    # ... 后续代码保持同一缩进级别

        # ─── 1. 输入账号密码 ───────────────────────────────────
        email_input = page.locator("#login")
        await email_input.wait_for(state="visible")
        await email_input.press_sequentially(LOGIN_EMAIL, delay=random.randint(50, 150))
        logger.log("✅", "已输入邮箱")

        password_input = page.locator("#password")
        await password_input.wait_for(state="visible")
        await password_input.press_sequentially(LOGIN_PASSWORD, delay=random.randint(50, 150))
        logger.log("✅", "已输入密码")

        # ─── 2. 处理登录页的 Cloudflare 验证 ──────────────────
        logger.log("⏳", "等待 Cloudflare 验证框加载...")
        try:
            turnstile_container = page.locator(
                "div:has( > input[name='cf-turnstile-response'])"
            ).first
            await turnstile_container.wait_for(state="visible", timeout=15000)
            logger.log("✅", "已定位到 Cloudflare 外层容器")

            await asyncio.sleep(2)
            box = await turnstile_container.bounding_box()
            if box:
                click_x = 30
                click_y = box["height"] / 2
                logger.log("🖱️", "准备通过坐标点击复选框区域...")
                await turnstile_container.hover(position={"x": click_x, "y": click_y})
                await asyncio.sleep(random.uniform(0.5, 1.2))
                await turnstile_container.click(
                    position={"x": click_x, "y": click_y},
                    delay=random.randint(50, 150),
                )
                logger.log("✅", "已点击！正在等待验证 Token 生成...")

                response_input = page.locator("input[name='cf-turnstile-response']")
                is_verified = False
                for _ in range(20):
                    token_value = await response_input.input_value()
                    if token_value:
                        is_verified = True
                        logger.log("✅", "验证成功！已获取到 CF Token。")
                        break
                    await asyncio.sleep(1)

                if not is_verified:
                    logger.log("⚠️", "等待 Token 超时，验证可能失败。")
        except Exception as e:
            logger.log("⚠️", f"处理验证码时出现异常: {e}")

        # ─── 3. 点击 Sign In 按钮 ─────────────────────────────
        submit_btn = page.locator("button[type='submit']")
        await submit_btn.wait_for(state="visible")
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await submit_btn.click()
        logger.log("✅", "已点击登录按钮")

        # ─── 4. 检查结果 & 执行后续流程 ───────────────────────
        await asyncio.sleep(3)
        logger.log("🌐", f"当前页面 URL: {page.url}")

        if "login" not in page.url.lower():
            logger.log("🎉", "登录成功！开始执行后续面板操作...")

            try:
                panel_link = page.locator("div.space-x-10 a[href='/panel']")
                await panel_link.wait_for(state="visible", timeout=10000)
                await panel_link.click()
                logger.log("✅", "已点击 Sign in 链接，正在加载面板...")

                await page.wait_for_load_state("domcontentloaded")

                running_el = page.locator('span:has-text("Running")').first
                await running_el.wait_for(state="visible", timeout=10000)
                await running_el.click()
                logger.log("✅", "已点击 Running 状态元素，正在进入详情页...")

                await page.wait_for_load_state("domcontentloaded")

                # 步骤 C：获取重置前倒计时 & 点击外部 Reset Timer 按钮
                countdown_span = page.locator("span.font-mono.text-xl").first
                await countdown_span.wait_for(state="visible", timeout=10000)
                time_before = await countdown_span.inner_text()
                logger.log("📊", f"点击 Reset Timer 前的倒计时: {time_before}")

                reset_btn = page.locator('button:has-text("Reset Timer")').first
                await reset_btn.wait_for(state="visible", timeout=10000)
                await reset_btn.click()
                logger.log("🔄", "已点击外层 Reset Timer 按钮，等待弹窗加载...")

                # ═══ 处理弹窗及二次 CF 验证 ═══════════════════
                modal_cf_container = page.locator("#turnstile-timer-reset")
                await modal_cf_container.wait_for(state="visible", timeout=15000)
                logger.log("✅", "弹窗外层容器已加载")

                await modal_cf_container.scroll_into_view_if_needed()
                await asyncio.sleep(2.5)

                box = await modal_cf_container.bounding_box()
                if box:
                    center_x = box["width"] / 2
                    click_x = center_x - 115
                    click_y = box["height"] / 2

                    logger.log(
                        "🖱️",
                        f"弹窗容器真实尺寸: 宽{box['width']} 高{box['height']}",
                    )
                    logger.log("🎯", f"计算出穿透点击坐标: X={click_x}, Y={click_y}")

                    await modal_cf_container.hover(
                        position={"x": click_x, "y": click_y}
                    )
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                    await modal_cf_container.click(
                        position={"x": click_x, "y": click_y},
                        delay=random.randint(50, 150),
                    )
                    logger.log("✅", "已向黑盒物理坐标发起点击！正在等待验证通过...")

                    is_modal_verified = False
                    for _ in range(25):
                        tokens = await page.locator(
                            "input[name='cf-turnstile-response']"
                        ).all()
                        if tokens:
                            token_value = await tokens[-1].input_value()
                            if token_value:
                                is_modal_verified = True
                                logger.log("✅", "弹窗 CF 验证成功！获取到 Token。")
                                break
                        await asyncio.sleep(1)

                    if not is_modal_verified:
                        logger.log(
                            "⚠️",
                            "弹窗 CF 验证等待超时，可能是网络卡顿，尝试强行继续...",
                        )

                # 点击弹窗中的 Just Reset 按钮
                just_reset_btn = page.locator('button:has-text("Just Reset")').first
                await just_reset_btn.wait_for(state="visible", timeout=10000)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await just_reset_btn.click()
                logger.log("🔄", "已点击 Just Reset 按钮，等待弹窗消失及倒计时刷新...")

                # 智能等待倒计时变化
                time_after = time_before
                for _ in range(10):
                    await asyncio.sleep(1)
                    current_time = await countdown_span.inner_text()
                    if current_time != time_before:
                        time_after = current_time
                        break
                else:
                    time_after = await countdown_span.inner_text()

                logger.log("📊", f"最终的倒计时: {time_after}")

                if time_before != time_after:
                    logger.log("🎉", "倒计时已成功重置，所有操作步骤顺利完成！")
                else:
                    logger.log("⚠️", "倒计时数值未发生变化，可能请求未成功。")

            except TimeoutError as te:
                logger.log("❌", f"等待元素超时，可能页面结构变化: {te}")
            except Exception as e:
                logger.log("❌", f"执行面板操作时发生异常: {e}")
        else:
            error_msg = page.locator("text='Captcha code is invalid'")
            if await error_msg.is_visible():
                logger.log("❌", "登录失败：网站提示 Captcha 无效。")
            else:
                logger.log("⚠️", "登录可能失败，仍在登录页面。")

        logger.log("👋", "浏览器将在 10 秒后自动安全关闭...")
        await asyncio.sleep(10)

    # ─── 推送 Telegram 报告 ────────────────────────────────────
    report = logger.build_markdown()
    print("\n" + "=" * 50)
    print(report)
    print("=" * 50 + "\n")
    await send_telegram(report)


if __name__ == "__main__":
    asyncio.run(run())
