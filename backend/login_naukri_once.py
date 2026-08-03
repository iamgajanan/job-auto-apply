from app.providers.naukri.login import NaukriLogin

browser, page = NaukriLogin().login()

print(
    "Please log in to Naukri in the browser window that just opened."
)

# Naukri sends you to the homepage (or /mnjuser/homepage for jobseekers)
# after a successful login. We wait for either.
page.wait_for_url(
    lambda url: "naukri.com" in url and "nlogin" not in url,
    timeout=0,
)

print(
    "Login saved successfully. You can now close this window."
)

browser.close()
