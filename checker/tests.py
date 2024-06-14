from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from checker.parser import Parser
from checker.utils import *


class ParserTestCase(TestCase):
    def setUp(self) -> None:
        self.base_url = "https://test.com"

    def test_content_empty(self) -> None:
        self.assertRaises(ValueError, Parser, content=b"", base_url=self.base_url)

    def test_title(self) -> None:
        parser = Parser(b"<title>Title</title>", self.base_url)
        self.assertEqual(parser.title, "Title")

    def test_title_not_found(self) -> None:
        parser = Parser(b"Title", self.base_url)
        self.assertIsNone(parser.title)

    def test_description(self) -> None:
        parser = Parser(b"<meta name='description' content='Description'>", self.base_url)
        self.assertEqual(parser.description, "Description")

    def test_description_not_found(self) -> None:
        parser = Parser(b"Description", self.base_url)
        self.assertIsNone(parser.description)

    def test_favicon(self) -> None:
        parser = Parser(b"<link rel='icon' href='favicon.ico'>", self.base_url)
        self.assertEqual(parser.favicon, f"{self.base_url}/favicon.ico")

    def test_favicon_not_found(self) -> None:
        parser = Parser(b"Favicon", self.base_url)
        self.assertIsNone(parser.favicon)

    def test_robots_meta(self) -> None:
        parser = Parser(b"<meta name='robots' content='noindex, nofollow'>", self.base_url)
        self.assertEqual(parser.robots_meta, "noindex, nofollow")

    def test_robots_meta_not_found(self) -> None:
        parser = Parser(b"Robots", self.base_url)
        self.assertIsNone(parser.robots_meta)

    def test_headings(self) -> None:
        parser = Parser(
            b"<h1>Heading 1</h1>"
            b"<h2>Heading 2</h2>"
            b"<h3>Heading 3</h3>"
            b"<h4>Heading 4</h4>"
            b"<h5>Heading 5</h5>"
            b"<h6>Heading 6</h6>",
            self.base_url,
        )
        self.assertDictEqual(
            parser.headings,
            {
                1: ["Heading 1"],
                2: ["Heading 2"],
                3: ["Heading 3"],
                4: ["Heading 4"],
                5: ["Heading 5"],
                6: ["Heading 6"],
            },
        )

    def test_headings_not_found(self) -> None:
        parser = Parser(b"Headings", self.base_url)
        self.assertDictEqual(parser.headings, {1: None, 2: None, 3: None, 4: None, 5: None, 6: None})

    def test_anchors_internal_links(self) -> None:
        parser = Parser(b"<a href='#'></a><a href='/'></a>", self.base_url)
        self.assertIsNone(parser.anchors)

    def test_anchors_javascript_mailto_tel_links(self) -> None:
        parser = Parser(b"<a href='javascript:'></a><a href='mailto:'></a><a href='tel:'></a>", self.base_url)
        self.assertIsNone(parser.anchors)

    def test_anchors_page_links(self) -> None:
        parser = Parser(
            b"<a href='https://test.com/page1'>"
            b"</a><a href='//test.com/page2'>"
            b"</a><a href='/page3'></a>"
            b"<a href='page4'></a>",
            self.base_url,
        )
        for idx, anchor in enumerate(sorted(parser.anchors)):
            self.assertEqual(anchor, f"{self.base_url}/page{idx + 1}")

    def test_anchors_duplicate_links(self) -> None:
        parser = Parser(b"<a href='page'></a><a href='page'></a>", self.base_url)
        self.assertListEqual(parser.anchors, [f"{self.base_url}/page"])

    def test_anchors_not_found(self) -> None:
        parser = Parser(b"Anchors", self.base_url)
        self.assertIsNone(parser.anchors)

    def test_inline_css(self) -> None:
        parser = Parser(b"<div style='color:red'></div>", self.base_url)
        self.assertListEqual(parser.inline_css, ['<div style="color:red">'])

    def test_inline_css_not_found(self) -> None:
        parser = Parser(b"Inline CSS", self.base_url)
        self.assertIsNone(parser.inline_css)

    def test_images(self) -> None:
        parser = Parser(b"<img src='image.png'>", self.base_url)
        self.assertListEqual(parser.images, ['<img src="image.png">'])

    def test_images_not_found(self) -> None:
        parser = Parser(b"Images", self.base_url)
        self.assertIsNone(parser.images)

    def test_images_miss_alt(self) -> None:
        parser = Parser(b"<img src='image.png'>", self.base_url)
        self.assertListEqual(parser.images_miss_alt, ['<img src="image.png">'])

    def test_images_miss_alt_not_found(self) -> None:
        parser = Parser(b"Images", self.base_url)
        self.assertIsNone(parser.images_miss_alt)


class UtilsTestCase(TestCase):
    def setUp(self) -> None:
        self.base_url = "https://test.com"

    @patch("checker.utils.requests")
    def test_verify_captcha(self, mock_requests) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}

        mock_requests.post.return_value = mock_response
        self.assertTrue(verify_captcha("response", "127.0.0.1"))

    @patch("checker.utils.requests")
    def test_verify_captcha_with_http_error(self, mock_requests) -> None:
        mock_requests.post.side_effect = HTTPError()
        self.assertFalse(verify_captcha("response", "127.0.0.1"))

    @patch("checker.utils.requests")
    def test_verify_captcha_with_json_error(self, mock_requests) -> None:
        mock_response = MagicMock()
        mock_response.json.side_effect = JSONDecodeError("", "", 0)

        mock_requests.post.return_value = mock_response
        self.assertFalse(verify_captcha("response", "127.0.0.1"))

    @override_settings(DEBUG=True)
    def test_verify_captcha_with_debug(self) -> None:
        self.assertTrue(verify_captcha("response", "127.0.0.1"))

    @patch("checker.utils.requests")
    def test_get_robots_link(self, mock_requests) -> None:
        self.assertEqual(get_robots_link(mock_requests, self.base_url), f"{self.base_url}/robots.txt")

    def test_get_robots_link_with_http_error(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError()

        mock_session = MagicMock()
        mock_session.head.return_value = mock_response
        self.assertEqual(get_robots_link(mock_session, self.base_url), None)

    @patch("checker.utils.requests")
    def test_get_sitemap_link(self, mock_requests) -> None:
        self.assertListEqual(get_sitemap_links(mock_requests, self.base_url, None), [f"{self.base_url}/sitemap.xml"])

    def test_get_sitemap_link_with_http_error(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError()

        mock_session = MagicMock()
        mock_session.head.return_value = mock_response
        self.assertIsNone(get_sitemap_links(mock_session, self.base_url, None))

    def test_get_sitemap_link_from_robots_url(self) -> None:
        mock_head_response = MagicMock()
        mock_head_response.raise_for_status.side_effect = HTTPError()

        mock_session = MagicMock()
        mock_session.head.return_value = mock_head_response

        mock_get_response = MagicMock()
        mock_get_response.text = f"Sitemap: {self.base_url}/sitemap1.xml\nSitemap: {self.base_url}/sitemap2.xml"
        mock_session.get.return_value = mock_get_response
        self.assertListEqual(
            get_sitemap_links(mock_session, self.base_url, f"{self.base_url}/robots.txt"),
            [f"{self.base_url}/sitemap1.xml", f"{self.base_url}/sitemap2.xml"],
        )

    def test_get_sitemap_link_from_robots_url_with_empty_sitemap(self) -> None:
        mock_head_response = MagicMock()
        mock_head_response.raise_for_status.side_effect = HTTPError()

        mock_session = MagicMock()
        mock_session.head.return_value = mock_head_response

        mock_get_response = MagicMock()
        mock_get_response.text = ""
        mock_session.get.return_value = mock_get_response
        self.assertIsNone(get_sitemap_links(mock_session, self.base_url, f"{self.base_url}/robots.txt"))

    def test_get_sitemap_link_from_robots_url_with_http_error(self) -> None:
        mock_head_response = MagicMock()
        mock_head_response.raise_for_status.side_effect = HTTPError()

        mock_session = MagicMock()
        mock_session.head.return_value = mock_head_response

        mock_get_response = MagicMock()
        mock_get_response.raise_for_status.side_effect = HTTPError()
        mock_session.get.return_value = mock_get_response
        self.assertIsNone(get_sitemap_links(mock_session, self.base_url, f"{self.base_url}/robots.txt"))

    @patch("checker.utils.requests")
    def test_check_broken_link(self, mock_requests) -> None:
        self.assertEqual(check_broken_link(mock_requests, self.base_url), None)

    def test_check_broken_link_with_http_error(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError()

        mock_session = MagicMock()
        mock_session.head.return_value = mock_response
        self.assertEqual(check_broken_link(mock_session, self.base_url), self.base_url)

    def test_check_broken_link_with_request_error(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = RequestException()

        mock_session = MagicMock()
        mock_session.head.return_value = mock_response
        self.assertEqual(check_broken_link(mock_session, self.base_url), None)

    @patch("checker.utils.check_broken_link")
    def test_get_broken_links(self, mock_check_broken_link) -> None:
        mock_check_broken_link.return_value = self.base_url

        mock_session = MagicMock()
        self.assertListEqual(get_broken_links(mock_session, [self.base_url]), [self.base_url])

    @patch("checker.utils.check_broken_link")
    def test_get_broken_links_with_none(self, mock_check_broken_link) -> None:
        mock_check_broken_link.return_value = None

        mock_session = MagicMock()
        self.assertIsNone(get_broken_links(mock_session, [self.base_url]))

    @patch("checker.utils.requests")
    def test_get_broken_links_with_empty_links(self, mock_requests) -> None:
        self.assertIsNone(get_broken_links(mock_requests, []))

    def test_get_page_rank(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": [{"status_code": 200, "rank": 1}]}

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        self.assertEqual(get_page_rank(mock_session, self.base_url), 1)

    def test_get_page_rank_with_http_error(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        self.assertEqual(get_page_rank(mock_session, self.base_url), 0)

    def test_get_page_rank_with_json_error(self) -> None:
        mock_response = MagicMock()
        mock_response.json.side_effect = JSONDecodeError("", "", 0)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        self.assertEqual(get_page_rank(mock_session, self.base_url), 0)

    def test_get_page_rank_with_not_found(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": [{"status_code": 404}]}

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        self.assertEqual(get_page_rank(mock_session, self.base_url), 0)

    @override_settings(DEBUG=True)
    def test_get_page_rank_with_debug(self) -> None:
        mock_session = MagicMock()
        self.assertEqual(get_page_rank(mock_session, self.base_url), 0)
