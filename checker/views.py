from urllib.parse import urlsplit

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import TemplateView
from requests import Session
from requests.exceptions import HTTPError

from checker.parser import Parser
from checker.utils import (
    get_broken_links,
    get_page_rank,
    get_robots_link,
    get_sitemap_links,
    verify_captcha,
)


class IndexView(TemplateView):
    template_name = "checker/index.html"


class AboutView(TemplateView):
    template_name = "checker/about.html"


class ContactView(TemplateView):
    template_name = "checker/contact.html"


class CheckView(TemplateView):
    template_name = "checker/check.html"
    template_error = "checker/index.html"

    def post(self, request):
        url = request.POST["url"]

        if not verify_captcha(request.POST["g-recaptcha-response"], request.META["REMOTE_ADDR"]):
            messages.info(request, url)
            messages.error(request, "* Bạn chưa được kiểm tra không phải là robot!")
            return redirect("/")

        # Parsing
        u = urlsplit(url, allow_fragments=False)
        domain = u.netloc
        base_url = f"{u.scheme}://{domain}"
        client = Session()
        try:
            r = client.get(url)
            parsed = Parser(r.content, base_url)
            context = {
                "url": url,
                "title": parsed.title,
                "description": parsed.description,
                "favicon": parsed.favicon,
                "robotsMeta": parsed.robots_meta,
                "headings": parsed.headings,
                "inlineCSS": parsed.inline_css,
                "images": parsed.images,
                "imagesMissAlt": parsed.images_miss_alt,
                "pageRank": get_page_rank(client, domain),
                "robotsTxt": get_robots_link(client, base_url),
                "brokenLinks": get_broken_links(client, parsed.anchors),
                "anchors": parsed.anchors,
            }
            context["sitemaps"] = get_sitemap_links(client, base_url, context["robotsTxt"])
            return render(request, self.template_name, context)
        except HTTPError as e:
            print(f"Failed to get URL: {e}")
            messages.info(request, url)
            messages.error(request, "* Không phân tích được URL. Vui lòng kiểm tra lại!")
            return redirect("/")
        finally:
            client.close()

    def get_context_data(self, **kwargs):
        context = super(CheckView, self).get_context_data()
        context.update(
            {
                "url": "/",
                "title": "Phân tích & Đánh giá SEO cho website của bạn | Đánh Giá Web",
                "description": "Trang phân tích, đánh giá SEO cho website nhanh chóng, chính xác và miễn phí",
                "favicon": "/static/img/favicon.png",
                "robotsMeta": "index, follow, noodp, noydir",
                "headings": {
                    1: ["Phân tích & Đánh giá SEO"],
                    2: ["Nhanh chóng, Chính xác, Miễn phí"],
                },
                "inlineCSS": [],
                "images": ["/images"],
                "imagesMissAlt": [],
                "pageRank": 0,
                "robotsTxt": "/robots.txt",
                "brokenLinks": [],
                "anchors": ["/anchors"],
                "sitemaps": ["/sitemap.xml"],
            }
        )
        return context
