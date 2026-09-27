import asyncio
import os
import pathlib
import time
from playwright.async_api import async_playwright

ARTIFACT_DIR = "/config/.gemini/antigravity/brain/1a0c8f70-72e7-47b7-b181-bb6e0cff1122"

async def record_demo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=ARTIFACT_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        print("Navigating to http://localhost:8080...")
        await page.goto("http://localhost:8080")
        await page.wait_for_timeout(3000)

        # 1. First Prompt: Core capability - 4-Day Strength Plan
        print("Sending Prompt 1: 4-Day Strength Plan...")
        prompt1_btn = page.locator(".prompt-chip", has_text="4-Day Strength Plan")
        if await prompt1_btn.count() > 0:
            await prompt1_btn.click()
        else:
            await page.fill("#input", "Can you create a 4-day workout plan for strength training?")
            await page.click("button:has-text('Send')")
        
        # Wait for agent response
        print("Waiting for response to Prompt 1...")
        await page.wait_for_selector(".msg.agent", timeout=45000)
        await page.wait_for_timeout(6000)

        # 2. Second Prompt: Richer prompt with tool calls (Places & Image generation)
        print("Sending Prompt 2: Nearby Gyms & Motivation Visual...")
        await page.fill("#input", "Find nearby gyms around San Francisco, CA and create a motivational visual for leg day!")
        await page.click("button:has-text('Send')")

        print("Waiting for response to Prompt 2...")
        # Wait for second agent message
        await asyncio.sleep(2)
        await page.wait_for_selector(".msg.agent:nth-of-type(4)", timeout=60000)
        await page.wait_for_timeout(8000)

        print("Closing context and saving video...")
        video_path = await page.video.path()
        await context.close()
        await browser.close()
        
        target_video = os.path.join(ARTIFACT_DIR, "fitcoach_ai_demo.webm")
        os.rename(video_path, target_video)
        print(f"Demo video successfully saved to: {target_video}")

if __name__ == "__main__":
    asyncio.run(record_demo())
