import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from lxml import etree

from checker.utils import ENCODING


class Parser:
    HEADING_LEVEL: int = 6
    METHOD_HTML: str = "html"

    def __init__(self, content: bytes, base_url: str) -> None:
        """
        Initialize the parser.

        :param content: Content to be parsed.
        :param base_url: Base URL.
        """
        html_parser = etree.HTMLParser(encoding=ENCODING)
        self.content = etree.fromstring(text=content, parser=html_parser, base_url=base_url)
        self.base_url = base_url

        if self.content is None:
            raise ValueError("Cannot parse content")

    def _xpath(self, xpath: str, multiple: bool = False) -> Optional[str | list[str]]:
        """
        Perform an XPath query.

        :param xpath: XPath query.
        :param multiple: Enable multiple results.
        :return: Result if successful, None otherwise.
        """
        elements = self.content.xpath(xpath)
        if not elements:
            return None

        if not multiple:
            return elements[0]
        return elements

    def _xpath_tags(self, xpath: str) -> Optional[list[str]]:
        """
        Perform an XPath query that returns HTML tags.

        :param xpath: XPath query.
        :return: List of HTML tags if successful, None otherwise.
        """
        elements = self.content.xpath(xpath)
        if not elements:
            return None

        tags: list[str] = list()
        for element in elements:
            tag = etree.tostring(element, encoding=ENCODING, method=self.METHOD_HTML).decode(ENCODING)
            if tag_match := re.search(r"<.*?>", tag):
                tags.append(tag_match.group())

        return tags if tags else None

    @staticmethod
    def _clean_headings(level: int, headings: list[str]) -> tuple[int, Optional[list[str]]]:
        """
        Clean the list of headings.

        :param level: Heading level.
        :param headings: List of headings.
        :return: Cleaned list of headings.
        """
        if not headings:
            return level, None

        # Remove empty or whitespace-only headings
        cleaned = list(filter(None, [heading.strip() for heading in headings]))
        return level, cleaned if cleaned else None

    @staticmethod
    def _is_page_link(link: str) -> bool:
        """
        Check if the link is a valid page link.

        :param link: Link to check.
        :return: True if valid, False otherwise.
        """
        # Internal links
        if link in ("#", "/"):
            return False

        # javascript, mailto, tel links
        if link.startswith(("javascript:", "mailto:", "tel:")):
            return False

        return True

    def _get_page_link(self, link: str) -> str:
        """
        Get the normalized page link.

        :param link: Link to normalize.
        :return: Normalized link.
        """

        # Add base URL
        if not link.startswith(("http://", "https://", "//")):
            return self.base_url + "/" + link.lstrip("/")

        # Add scheme
        if link.startswith("//"):
            return self.base_url.split(":")[0] + "//" + link.lstrip("/")

        return link

    @property
    def title(self) -> Optional[str]:
        """Get title."""
        return self._xpath("//title/text()")

    @property
    def description(self) -> Optional[str]:
        """Get description."""
        return self._xpath('//meta[@name="description"]/@content')

    @property
    def favicon(self) -> Optional[str]:
        """Get favicon."""
        link = self._xpath('//link[contains(@rel, "icon")]/@href')
        return self._get_page_link(link) if link else None

    @property
    def robots_meta(self) -> Optional[str]:
        """Get robots meta."""
        return self._xpath('//meta[@name="robots"]/@content')

    @property
    def headings(self) -> Optional[dict[int, Optional[list[str]]]]:
        """Get headings."""
        xpath_template = "//h{}//text()"

        results: list[tuple[int, Optional[list[str]]]] = []
        with ThreadPoolExecutor(max_workers=self.HEADING_LEVEL) as executor:
            futures = list()
            for level in range(self.HEADING_LEVEL):
                headings = self._xpath(xpath_template.format(level + 1), multiple=True)
                futures.append(executor.submit(self._clean_headings, level, headings))

            results.extend([future.result() for future in as_completed(futures)])
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except TimeoutError as e:
                    print(f"TimeoutError: {e}")

        if not results:
            return None

        return {result[0] + 1: result[1] for result in results}

    @property
    def anchors(self) -> Optional[list[str]]:
        """Get anchors."""
        page_links: list[str] = list()

        links = self._xpath("//a/@href", multiple=True)
        if not links:
            return None

        for link in links:
            link = link.strip()
            if not self._is_page_link(link):
                continue
            page_links.append(self._get_page_link(link))

        page_links = list(set(page_links))
        return page_links if page_links else None

    @property
    def inline_css(self) -> Optional[list[str]]:
        """Get inline CSS."""
        return self._xpath_tags("//@style/..")

    @property
    def images(self) -> Optional[list[str]]:
        """Get images."""
        return self._xpath_tags("//img")

    @property
    def images_miss_alt(self) -> Optional[list[str]]:
        """Get images without alt attribute."""
        return self._xpath_tags("//img[not(@alt)]")
