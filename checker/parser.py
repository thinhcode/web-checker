import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from lxml import etree

ENCODING: str = "utf-8"


class Parser:
    HEADING_LEVEL: int = 6
    METHOD_HTML: str = "html"

    def __init__(self, content: bytes, base_url: str) -> None:
        """
        Initializes an instance of the class with the given content and base URL.

        :param content: The content to be parsed.
        :param base_url: The base URL for the content.
        """
        html_parser = etree.HTMLParser(encoding=ENCODING)
        self.content = etree.fromstring(
            text=content, parser=html_parser, base_url=base_url
        )
        self.base_url = base_url

        if self.content is None:
            raise ValueError("Cannot parse content")

    def _xpath(self, xpath: str, multiple: bool = False) -> Optional[str | list[str]]:
        """
        Perform an XPath query on the content and return the result.

        :param xpath: The XPath expression to be evaluated.
        :param multiple: Whether to return a single element or multiple elements. Defaults to False.
        :return: Either a single element or a list of elements matching the XPath expression.
        """
        elements = self.content.xpath(xpath)
        if not elements:
            return None

        if not multiple:
            return elements[0]
        return elements

    def _xpath_tags(self, xpath: str) -> Optional[list[str]]:
        """
        Retrieves a list of HTML tags matching the given XPath expression.

        :param xpath: The XPath expression to match against.
        :return: A list of HTML tags matching the XPath expression, or None if no matches are found.
        """
        elements = self.content.xpath(xpath)
        if not elements:
            return None

        tags: list[str] = list()
        for element in elements:
            tag = etree.tostring(
                element, encoding=ENCODING, method=self.METHOD_HTML
            ).decode(ENCODING)
            tags.append(re.search(r"<.*?>", tag).group())

        return tags if tags else None

    @staticmethod
    def _clean_headings(
        level: int, headings: list[str]
    ) -> tuple[int, Optional[list[str]]]:
        """
        Cleans the given list of headings by removing any empty or whitespace-only headings.

        :param level: The level of the headings.
        :param headings: The list of headings to be cleaned.
        :return: A tuple containing the level of the headings and the cleaned list of headings.
                 If the cleaned list is empty, None is returned instead.
        """
        if not headings:
            return level, None

        cleaned = list(filter(None, [heading.strip() for heading in headings]))
        return level, cleaned if cleaned else None

    @staticmethod
    def _is_page_link(link: str) -> bool:
        """
        Check if the given link is a valid page link.

        :param link: The link to be checked.
        :return: True if the link is a valid page link, False otherwise.
        """
        if link in ("#", "/"):
            return False
        if link.startswith(("javascript:", "mailto:", "tel:")):
            return False
        return True

    def _get_page_link(self, link: str) -> str:
        """
        Returns a normalized page link based on the provided link string.

        :param link: The link string to be normalized.
        :return: The normalized page link.
        """
        if not link.startswith(("http://", "https://", "//")):
            return self.base_url + "/" + link.lstrip("/")
        if link.startswith("//"):
            return self.base_url.split(":")[0] + "//" + link.lstrip("/")
        return link

    @property
    def title(self) -> Optional[str]:
        return self._xpath("//title/text()")

    @property
    def description(self) -> Optional[str]:
        return self._xpath('//meta[@name="description"]/@content')

    @property
    def favicon(self) -> Optional[str]:
        link = self._xpath('//link[contains(@rel, "icon")]/@href')
        return self._get_page_link(link) if link else None

    @property
    def robots_meta(self) -> Optional[str]:
        return self._xpath('//meta[@name="robots"]/@content')

    @property
    def headings(self) -> Optional[dict[int, Optional[list[str]]]]:
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
        page_links: list[str] = list()

        links = self._xpath("//a/@href", multiple=True)
        for link in links:
            link = link.strip()
            if not self._is_page_link(link):
                continue
            page_links.append(self._get_page_link(link))

        page_links = list(set(page_links))
        return page_links if page_links else None

    @property
    def inline_css(self) -> Optional[list[str]]:
        return self._xpath_tags("//@style/..")

    @property
    def images(self) -> Optional[list[str]]:
        return self._xpath_tags("//img")

    @property
    def images_miss_alt(self) -> Optional[list[str]]:
        return self._xpath_tags("//img[not(@alt)]")
