import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from json import JSONDecodeError
from typing import Optional

import requests
from django.conf import settings
from requests import Session
from requests.exceptions import HTTPError, RequestException

MAX_WORKERS = 5


def verify_captcha(response: str, user_ip: str) -> bool:
    """
    Verifies the reCAPTCHA response using the Google reCAPTCHA API.

    :param response: The reCAPTCHA response token provided by the user.
    :param user_ip: The IP address of the user submitting the reCAPTCHA.
    :return: True if the reCAPTCHA verification is successful, False otherwise.
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
    Retrieves the URL of the robots.txt file for a given base URL using the provided HTTP client.

    :param client: The session client to make HTTP requests.
    :param base_url: The base URL to construct the robots.txt file.
    :return: The URL of the robots.txt file if it exists and can be accessed, None otherwise.
    """
    robots_url = base_url + "/robots.txt"
    try:
        r = client.head(robots_url)
        r.raise_for_status()
        return robots_url
    except HTTPError as e:
        print(f"Failed to get robots.txt: {e}")
        return None


def get_sitemap_links(
    client: Session, base_url: str, robots_url: str
) -> Optional[list[str]]:
    """
    Get sitemap links from the provided base URL and robots URL.

    :param client: The session client to make HTTP requests.
    :param base_url: The base URL to construct the sitemap URL.
    :param robots_url: The URL to fetch robots.txt content.
    :return: A list of sitemap URLs if successful, None otherwise.
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
    Check if a given link is broken by sending a HEAD request to the link using the provided session.

    :param client: The session client to make HTTP requests.
    :param link: The link to be checked.
    :return: If the link is broken, returns the link itself. Otherwise, returns None.
    """
    try:
        r = client.head(link)
        r.raise_for_status()
        return None
    except HTTPError:
        return link
    except RequestException:
        pass


def get_broken_links(
    client: Session, links: Optional[list[str]]
) -> Optional[list[str]]:
    """
    Retrieves a list of broken links from a given list of links using a thread pool executor.

    :param client: The session client to make HTTP requests.
    :param links: A list of links to check for broken links.
    :return: A list of broken links, or None if no broken links are found.
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
    Retrieves the page rank for a given domain using the OpenPageRank API.

    :param client: The session client to make HTTP requests.
    :param domain: A domain name.
    :return: The page rank, or 0 if the request fails.
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
