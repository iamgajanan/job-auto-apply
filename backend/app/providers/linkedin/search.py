from urllib.parse import quote

from app.providers.linkedin.browser import BrowserManager


class LinkedInSearch:

    JOB_LIMIT = 100          # hard cap: never scrape/return more than this
    PAGE_SIZE = 25           # LinkedIn's cards-per-page
    MAX_PAGES = 20           # safety cap on pagination loop
    MAX_SCROLLS_PER_PAGE = 15   # a page only ever holds ~25 cards, 15 scrolls is plenty
    SCROLL_POLL_TIMEOUT_MS = 1800  # max time to wait per scroll for new cards to render
    MAX_CONSECUTIVE_STALLS = 2  # require 2 no-change scrolls in a row before giving up
    POST_NAV_WAIT_MS = 1500    # was 3000 -- domcontentloaded + this is enough

    def search(self, request):

        browser = BrowserManager()
        page = browser.launch()

        keyword = quote(request.job_title or "")
        location = quote(request.location or "")

        base_url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={keyword}"
            f"&location={location}"
        )

        # Easy Apply
        if request.easy_apply:
            base_url += "&f_AL=true"

        # Work Mode
        if request.work_mode:
            mode = request.work_mode.lower()

            if mode == "remote":
                base_url += "&f_WT=2"
            elif mode == "hybrid":
                base_url += "&f_WT=3"
            elif mode in ["onsite", "on-site"]:
                base_url += "&f_WT=1"

        # Experience
        if request.experience:
            try:
                years = int(request.experience.split()[0])

                if years <= 2:
                    base_url += "&f_E=1"
                elif years <= 5:
                    base_url += "&f_E=3"
                elif years <= 10:
                    base_url += "&f_E=4"
                else:
                    base_url += "&f_E=5"

            except Exception:
                pass

        # Posted Within
        if request.posted_within:
            posted = request.posted_within.lower()

            if posted == "day":
                base_url += "&f_TPR=r86400"
            elif posted == "week":
                base_url += "&f_TPR=r604800"
            elif posted == "month":
                base_url += "&f_TPR=r2592000"

        jobs = []
        seen_job_ids = set()

        # ---------------------------------------
        # Paginate: LinkedIn shows ~25 cards per
        # page, controlled via &start= offset.
        # Stop as soon as: a page adds no new jobs,
        # OR we hit JOB_LIMIT, OR MAX_PAGES reached.
        # ---------------------------------------

        for page_num in range(self.MAX_PAGES):

            start = page_num * self.PAGE_SIZE
            url = base_url + f"&start={start}"

            print("=" * 80)
            print(f"Page {page_num + 1} | start={start}")
            print(url)
            print("=" * 80)

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            # Wait for at least one card to show up instead of a fixed
            # blind sleep -- falls back to the fixed wait if none appear
            # (e.g. zero-result search) so we don't hang.
            try:
                page.wait_for_selector(
                    ".job-card-container",
                    timeout=self.POST_NAV_WAIT_MS,
                )
            except Exception:
                page.wait_for_timeout(self.POST_NAV_WAIT_MS)

            print("Actual URL :", page.url)

            cards = page.locator(".job-card-container")
            print("Initially rendered:", cards.count())

            # ---------------------------------------
            # Find the real scrollable container.
            #
            # IMPORTANT PERF FIX: the previous version looped over every
            # single DOM element in Python, issuing one evaluate() round
            # trip PER ELEMENT (can be 1000+ round trips per page -- this
            # was the single biggest cause of slow responses). This does
            # the exact same search in ONE round trip by running the loop
            # inside the browser via a single page.evaluate() call.
            # ---------------------------------------

            best_info = page.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                let best = null;
                let bestHeight = 0;

                for (const e of all) {
                    const diff = e.scrollHeight - e.clientHeight;
                    if (diff > bestHeight) {
                        bestHeight = diff;
                        best = e;
                    }
                }

                if (!best) return null;

                // Stash the winning element on window so we can scroll
                // it directly in later evaluate() calls without having
                // to re-run this search or pass elements across the
                // Python/JS boundary.
                window.__scrollTarget = best;

                return {
                    tag: best.tagName,
                    cls: best.className,
                    id: best.id,
                    scrollHeight: best.scrollHeight,
                    clientHeight: best.clientHeight,
                    diff: bestHeight
                };
            }
            """)

            print("=" * 80)
            print("Largest scrollable element")
            print(best_info)
            print("=" * 80)

            if best_info:

                previous = 0
                stall_count = 0

                for i in range(self.MAX_SCROLLS_PER_PAGE):

                    page.evaluate("""
                    () => {
                        if (window.__scrollTarget) {
                            window.__scrollTarget.scrollBy(0, 1200);
                        }
                    }
                    """)

                    # Adaptive wait: poll every 200ms instead of one fixed
                    # sleep. Breaks out early the moment new cards show up
                    # (fast case) but keeps checking up to POLL_TIMEOUT_MS
                    # total before giving up (slow-load case). A single
                    # short fixed wait was causing false "no more cards"
                    # stops when LinkedIn just hadn't rendered yet.
                    poll_interval_ms = 200
                    elapsed_ms = 0
                    current = previous

                    while elapsed_ms < self.SCROLL_POLL_TIMEOUT_MS:
                        page.wait_for_timeout(poll_interval_ms)
                        elapsed_ms += poll_interval_ms

                        current = page.locator(".job-card-container").count()

                        if current > previous:
                            break  # new cards rendered, move to next scroll

                    print(f"Scroll {i + 1}: {current} (waited {elapsed_ms}ms)")

                    if current == previous:
                        stall_count += 1
                        if stall_count >= self.MAX_CONSECUTIVE_STALLS:
                            break
                    else:
                        stall_count = 0

                    previous = current

                    # Stop scrolling early if we've already got enough
                    # jobs overall (accounting for what's on earlier pages)
                    if len(jobs) + current >= self.JOB_LIMIT:
                        break

            cards = page.locator(".job-card-container")

            print(f"Page {page_num + 1} final jobs:", cards.count())

            if cards.count() == 0:
                # No cards on this page at all -> we've run past the end
                print("No cards found on this page. Stopping pagination.")
                break

            page_new_count = 0

            for i in range(cards.count()):

                # Stop the instant we hit the cap -- don't keep parsing
                # cards we're going to throw away.
                if len(jobs) >= self.JOB_LIMIT:
                    break

                card = cards.nth(i)

                text = (card.text_content() or "").lower()

                try:
                    title = (
                        card.locator("strong")
                        .first
                        .text_content()
                        .strip()
                    )
                except:
                    title = ""

                try:
                    company = (
                        card.locator(".artdeco-entity-lockup__subtitle")
                        .first
                        .text_content()
                        .strip()
                    )
                except:
                    company = ""

                try:
                    job_location = (
                        card.locator(".artdeco-entity-lockup__caption")
                        .first
                        .text_content()
                        .strip()
                    )
                except:
                    job_location = ""

                try:
                    logo = card.locator("img").first.get_attribute("src") or ""
                except:
                    logo = ""

                try:
                    link = card.locator("a").first.get_attribute("href") or ""

                    if link.startswith("/"):
                        link = "https://www.linkedin.com" + link

                except:
                    link = ""

                job_id = ""

                if "/jobs/view/" in link:
                    try:
                        job_id = (
                            link.split("/jobs/view/")[1]
                            .split("/")[0]
                            .split("?")[0]
                        )
                    except:
                        pass

                # Skip cards with no resolvable job_id. These are not
                # real job listings -- they're LinkedIn's injected
                # "recommended" / "hiring in network" widget cards that
                # also match .job-card-container but link to
                # /jobs/collections/... instead of /jobs/view/{id}/...
                # Keeping them causes duplicate '' job_id inserts and
                # breaks the DB's unique constraint on job_id.
                if not job_id:
                    continue

                # Skip duplicates across pages (LinkedIn sometimes
                # repeats the last card(s) of the previous page)
                if job_id in seen_job_ids:
                    continue

                seen_job_ids.add(job_id)

                work_mode = "Unknown"

                if "remote" in text:
                    work_mode = "Remote"
                elif "hybrid" in text:
                    work_mode = "Hybrid"
                elif "on-site" in text or "onsite" in text:
                    work_mode = "On-site"

                jobs.append(
                    {
                        "platform": "linkedin",
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "location": job_location,
                        "salary": "Not Disclosed",
                        "experience": request.experience,
                        "easy_apply": "easy apply" in text,
                        "work_mode": work_mode,
                        "job_url": link,
                        "apply_url": "",
                        "description": "",
                        "company_logo": logo,
                        "posted_at": None,
                        "posted_within": request.posted_within,
                        "status": "NEW",
                    }
                )

                page_new_count += 1

            print(f"Page {page_num + 1} added {page_new_count} new jobs. Total so far: {len(jobs)}")

            # Cap reached -- stop paginating entirely.
            if len(jobs) >= self.JOB_LIMIT:
                print(f"Reached JOB_LIMIT ({self.JOB_LIMIT}). Stopping pagination.")
                break

            # If this page contributed no new (unique) jobs,
            # we've reached the end of the results.
            if page_new_count == 0:
                print("No new jobs added from this page. Stopping pagination.")
                break

        # Final safety trim -- guarantees we never return more than
        # JOB_LIMIT even if some edge case let extra ones slip through.
        jobs = jobs[: self.JOB_LIMIT]

        print("=" * 80)
        print("TOTAL JOBS SCRAPED:", len(jobs))
        print("=" * 80)

        browser.close()

        return jobs