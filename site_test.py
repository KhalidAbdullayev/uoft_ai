from __future__ import annotations
from playwright.sync_api import sync_playwright
from collections import deque
from urllib.parse import urlparse
from urllib.parse import urljoin
from urllib.parse import urlsplit, urlunsplit
import os
import json

MAX_PAGES = 1000
LOG = 100
SKIP_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".png",
    ".jpg",
)

domain = "utm.utoronto.ca"


queue = deque([
    "https://www.utm.utoronto.ca", "https://www.utm.utoronto.ca/registrar/dates"
])

queued = set(queue)


def normalize_url(current_url: str, href1: str | None) -> str | None:
    if href1 is None:
        return None
    if href1.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    absolute1 = urljoin(current_url, href1)
    absolute1 = absolute1.rstrip("/")
    parts = urlsplit(absolute1)
    parts.netloc.lower()
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


visited = set()
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context(accept_downloads=False)
    context.route("**/*", lambda route: (route.abort() if route.request.resource_type
                                                          in ["image", "font", "media"] else route.continue_()))
    page = context.new_page()

    if os.path.exists("utm.json"):
        with open("utm.json", encoding="utf8") as f:
            pages = json.load(f)
    else:
        pages = []
    pages_dict = {}
    for page in pages:
        pages_dict[page["url"]] = page


    while queue:
        if len(visited) % LOG == 0:
            with open("utm.json", "w", encoding="utf8") as f:
                #noinspection PyTypeChecker
                json.dump(list(pages_dict.values()), f, ensure_ascii=False, indent=4)
        if len(visited) >= MAX_PAGES:
            break

        url = queue.popleft()
        queued.remove(url)

        parsed = urlparse(url)
        if not parsed.netloc.endswith(domain):
            continue
        if url in visited:
            continue

        visited.add(url)

        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            print(response.url)
            if response.url == "calendar.pdf":
                continue
            page.wait_for_load_state("networkidle", timeout=5000)
            if response:
                content_type = response.header_value("content-type")
                if content_type and "text/html" not in content_type:
                    continue
        except Exception as e:
            print(e)
            continue

        text = page.locator("body").inner_text()

        # pages.append({
        #     "url": url,
        #     "title": page.title(),
        #     "text": text
        # })
        pages_dict[url] = {
            "url": url,
            "title": page.title(),
            "text": text
        }

        links = page.locator("a")
        count = links.count()
        for i in range(links.count()):
            href = links.nth(i).get_attribute("href")
            absolute = normalize_url(url, href)
            if absolute is None:
                continue
            if absolute.lower().endswith(SKIP_EXTENSIONS):
                continue
            if absolute not in visited and absolute not in queued:
                queue.append(absolute)
                queued.add(absolute)