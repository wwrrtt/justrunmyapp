import json
import asyncio
from playwright.async_api import Playwright, async_playwright

async def run(playwright: Playwright) -> None:
    browser = await playwright.chromium.launch(headless=True, slow_mo=1000)
    context = await browser.new_context()
    
    # 尝试加载现有的 cookie
    try:
        with open("cookie.json", "r") as file:
            cookies = json.load(file)
        
        # 修复 sameSite 属性
        for cookie in cookies:
            if 'sameSite' not in cookie or cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                cookie['sameSite'] = 'Lax'
        
        await context.add_cookies(cookies)
    except:
        print("无法加载现有cookie或cookie不存在")
    
    page = await context.new_page()
    await page.goto("https://www.xshellz.com")
    await page.wait_for_load_state("networkidle")
    
    # 获取并保存最新的 cookies
    new_cookies = await context.cookies()
    with open("cookie.json", "w") as file:
        json.dump(new_cookies, file, indent=4)
    print("已更新并保存最新的cookie")
    
    await page.get_by_text("doomparty  Free Shell", exact=True).click()
    await asyncio.sleep(3)
    
    # 获取倒计时时间，精确定位到小时数
    time_span = await page.wait_for_selector("span.ng-binding")
    if time_span:
        hours = await time_span.text_content()
        print(f"续期前剩余时间: {hours} 小时")
    
    await page.locator('span.fas.fa-exchange-alt').click()
    await asyncio.sleep(10)  # 等待页面更新
    
    # 点击按钮后再次获取时间
    time_span = await page.wait_for_selector("span.ng-binding")
    if time_span:
        new_hours = await time_span.text_content()
        print(f"续期后剩余时间: {new_hours} 小时")

    # 操作完成后再次保存最新的 cookies
    final_cookies = await context.cookies()
    with open("cookie.json", "w") as file:
        json.dump(final_cookies, file, indent=4)
    print("已保存最终的cookie状态")

    await context.close()
    await browser.close()

async def main():
    async with async_playwright() as playwright:
        await run(playwright)
    print("模拟登录完成")

if __name__ == "__main__":
    asyncio.run(main())
