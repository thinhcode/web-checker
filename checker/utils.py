import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from json import JSONDecodeError
from typing import Optional

import requests
from django.conf import settings
from requests import Session
from requests.exceptions import HTTPError, RequestException

ENCODING: str = "utf-8"
MAX_WORKERS = 5


def verify_captcha(response: str, user_ip: str) -> bool:
    """
    Verifies the reCAPTCHA response.

    :param response: Response from reCAPTCHA.
    :param user_ip: User's IP address.
    :return: True if the response is valid, False otherwise.
    """
    if settings.DEBUG:
        print("Skipping reCAPTCHA verification in debug mode.")
        return True

    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        "secret": settings.GOOGLE_RECAPTCHA_SECRET_KEY,
        "response": response,
        "remoteip": user_ip,
    }

    try:
        r = requests.post(url=url, data=data)
        result: dict = r.json()
        return result["success"]
    except (HTTPError, JSONDecodeError) as e:
        print(f"Failed to verify reCAPTCHA: {e}")
        return False


def get_robots_link(client: Session, base_url: str) -> Optional[str]:
    """
    Get robots.txt link.

    :param client: Client sessions.
    :param base_url: Base URL.
    :return: robots.txt link if successful, None otherwise.
    """
    robots_url = base_url + "/robots.txt"
    try:
        r = client.head(robots_url)
        r.raise_for_status()
        return robots_url
    except HTTPError as e:
        print(f"Failed to get robots.txt: {e}")
        return None


def get_sitemap_links(client: Session, base_url: str, robots_url: str) -> Optional[list[str]]:
    """
    Get sitemap links.

    :param client: Client sessions.
    :param base_url: Base URL.
    :param robots_url: robots.txt link.
    :return: Sitemap links if successful, None otherwise.
    """
    sitemap_url = base_url + "/sitemap.xml"
    try:
        r = client.head(sitemap_url)
        r.raise_for_status()
        return [sitemap_url]
    except HTTPError as e:
        print(f"Failed to get sitemap.xml: {e}")

    # Get sitemap from robots.txt content
    if not robots_url:
        return None

    sitemaps: list[str] = list()
    try:
        r = client.get(robots_url)
        r.raise_for_status()
        sitemaps.extend(re.findall(r"Sitemap:.*xml", r.text))
    except HTTPError as e:
        print(f"Failed to get robots.txt content: {e}")
        return None

    if not sitemaps:
        return None

    return [sitemap.split("Sitemap:")[1].strip() for sitemap in sitemaps]


def check_broken_link(client: Session, link: str) -> Optional[str]:
    """
    Check if a link is broken.

    :param client: Client sessions.
    :param link: Link to check.
    :return: Link if it is broken, None otherwise.
    """
    try:
        r = client.head(link)
        r.raise_for_status()
        return None
    except HTTPError:
        return link
    except RequestException:
        pass


def get_broken_links(client: Session, links: Optional[list[str]]) -> Optional[list[str]]:
    """
    Get a list of broken links.

    :param client: Client sessions.
    :param links: List of links to check.
    :return: List of links if broken, None otherwise.
    """
    if not links:
        return None

    broken_links: list[str] = list()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_broken_link, client, link) for link in links]
        for future in as_completed(futures):
            if future.result():
                broken_links.append(future.result())

    return broken_links if broken_links else None


def get_page_rank(client: Session, domain: str) -> int:
    """
    Get the page rank of a domain.

    :param client: Client sessions.
    :param domain: Domain to check.
    :return: Page rank if found, 0 otherwise.
    """
    if settings.DEBUG:
        print("Skipping page rank retrieval in debug mode.")
        return 0

    url = "https://openpagerank.com/api/v1.0/getPageRank?domains[0]=" + domain
    headers = {"API-OPR": settings.OPEN_PAGERANK_KEY}
    try:
        r = client.get(url, headers=headers)
        result: dict = r.json()["response"][0]
        if result["status_code"] == 200:
            return int(result["rank"])
    except HTTPError as e:
        print(f"Failed to get page rank: {e}")

    return 0
