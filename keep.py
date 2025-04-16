import json
import asyncio
import requests
import os
from playwright.async_api import Playwright, async_playwright

def send_to_telegram(message):
    bot_token = os.environ.get('TG_BOT_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
        except Exception as e:
            print(f"发送到 Telegram 失败: {e}")

async def run(playwright: Playwright) -> None:
    browser = await playwright.chromium.launch(headless=True, slow_mo=1000)
    context = await browser.new_context()
    
    try:
        with open("cookie.json", "r") as file:
            cookies = json.load(file)
        
        for cookie in cookies:
            if 'sameSite' not in cookie or cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                cookie['sameSite'] = 'Lax'
        
        await context.add_cookies(cookies)
        send_to_telegram("成功加载现有cookie")
    except:
        send_to_telegram("无法加载现有cookie或cookie不存在")
    
    page = await context.new_page()
    await page.goto("https://www.xshellz.com")
    await page.wait_for_load_state("networkidle")
    
    new_cookies = await context.cookies()
    with open("cookie.json", "w") as file:
        json.dump(new_cookies, file, indent=4)
    send_to_telegram("已更新并保存最新的cookie")
    
    await page.get_by_text("doomparty  Free Shell", exact=True).click()
    await asyncio.sleep(3)
    
    time_span = await page.wait_for_selector("span.ng-binding")
    if time_span:
        hours = await time_span.text_content()
        message = f"续期前剩余时间: {hours} 小时"
        print(message)
        send_to_telegram(message)
    
    await page.locator('span.fas.fa-exchange-alt').click()
    await asyncio.sleep(10)
    
    time_span = await page.wait_for_selector("span.ng-binding")
    if time_span:
        new_hours = await time_span.text_content()
        message = f"续期后剩余时间: {new_hours} 小时"
        print(message)
        send_to_telegram(message)

    final_cookies = await context.cookies()
    with open("cookie.json", "w") as file:
        json.dump(final_cookies, file, indent=4)
    send_to_telegram("已保存最终的cookie状态")

    await context.close()
    await browser.close()

async def main():
    async with async_playwright() as playwright:
        await run(playwright)
    send_to_telegram("模拟登录完成")

if __name__ == "__main__":
    asyncio.run(main())
