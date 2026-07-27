from app.providers.linkedin.browser import BrowserManager

browser = BrowserManager()

page = browser.launch()

page.goto(
    "https://www.linkedin.com/feed",
    wait_until="networkidle",
)

print(page.title())

browser.close()