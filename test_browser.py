import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
            ]
        )

        context = await browser.new_context(
            ignore_https_errors=True
        )

        page = await context.new_page()

        print("Opening page...")

        await page.goto(
            "https://www.w3schools.com",
            wait_until="domcontentloaded",
            timeout=30000
        )

        print("Page title:", await page.title())

        await browser.close()

asyncio.run(test())