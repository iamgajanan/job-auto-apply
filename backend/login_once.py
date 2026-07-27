from app.providers.linkedin.login import LinkedInLogin

browser, page = LinkedInLogin().login()

print(
    "Please login once."
)

page.wait_for_url(
    "https://www.linkedin.com/feed/*",
    timeout=0,
)

print(
    "Login saved successfully."
)

browser.close()