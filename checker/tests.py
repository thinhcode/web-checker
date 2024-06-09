from django.test import TestCase

from checker.parser import Parser


class ParserTests(TestCase):
    def setUp(self) -> None:
        self.base_url = "https://test.com"

    def test_content_empty(self) -> None:
        self.assertRaises(ValueError, Parser, content=b"", base_url=self.base_url)

    def test_title(self) -> None:
        parser = Parser(b"<title>Title</title>", self.base_url)
        self.assertEqual(parser.title, "Title")

        # Not found
        parser = Parser(b"Title", self.base_url)
        self.assertIsNone(parser.title)

    def test_description(self) -> None:
        parser = Parser(b"<meta name='description' content='Description'>", self.base_url)
        self.assertEqual(parser.description, "Description")

        # Not found
        parser = Parser(b"Description", self.base_url)
        self.assertIsNone(parser.description)

    def test_favicon(self) -> None:
        parser = Parser(b"<link rel='icon' href='favicon.ico'>", self.base_url)
        self.assertEqual(parser.favicon, f"{self.base_url}/favicon.ico")

        # Not found
        parser = Parser(b"Favicon", self.base_url)
        self.assertIsNone(parser.favicon)

    def test_robots_meta(self) -> None:
        parser = Parser(b"<meta name='robots' content='noindex, nofollow'>", self.base_url)
        self.assertEqual(parser.robots_meta, "noindex, nofollow")

        # Not found
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

        # Not found
        parser = Parser(b"Headings", self.base_url)
        self.assertDictEqual(parser.headings, {1: None, 2: None, 3: None, 4: None, 5: None, 6: None})

    def test_anchors(self) -> None:
        # Internal links
        parser = Parser(b"<a href='#'></a><a href='/'></a>", self.base_url)
        self.assertIsNone(parser.anchors)

        # javascript, mailto, tel links
        parser = Parser(b"<a href='javascript:'></a><a href='mailto:'></a><a href='tel:'></a>", self.base_url)
        self.assertIsNone(parser.anchors)

        # Page link
        parser = Parser(
            b"<a href='https://test.com/page1'>"
            b"</a><a href='//test.com/page2'>"
            b"</a><a href='/page3'></a>"
            b"<a href='page4'></a>",
            self.base_url,
        )
        for idx, anchor in enumerate(sorted(parser.anchors)):
            self.assertEqual(anchor, f"{self.base_url}/page{idx + 1}")

        # Duplicate links
        parser = Parser(b"<a href='page'></a><a href='page'></a>", self.base_url)
        self.assertListEqual(parser.anchors, [f"{self.base_url}/page"])

        # Not found
        parser = Parser(b"Anchors", self.base_url)
        self.assertIsNone(parser.anchors)

    def test_inline_css(self) -> None:
        parser = Parser(b"<div style='color:red'></div>", self.base_url)
        self.assertListEqual(parser.inline_css, ['<div style="color:red">'])

        # Not found
        parser = Parser(b"Inline CSS", self.base_url)
        self.assertIsNone(parser.inline_css)

    def test_images(self) -> None:
        parser = Parser(b"<img src='image.png'>", self.base_url)
        self.assertListEqual(parser.images, ['<img src="image.png">'])

        # Not found
        parser = Parser(b"Images", self.base_url)
        self.assertIsNone(parser.images)

    def test_images_miss_alt(self) -> None:
        parser = Parser(b"<img src='image.png'>", self.base_url)
        self.assertListEqual(parser.images_miss_alt, ['<img src="image.png">'])

        # Not found
        parser = Parser(b"Images", self.base_url)
        self.assertIsNone(parser.images_miss_alt)
