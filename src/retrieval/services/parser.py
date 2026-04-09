from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

from core.config import settings
from utils.text import normalize_text


@dataclass
class ParsedArticle:
    title: str
    text: str
    metadata: dict[str, Any]


class ArticleParserService:
    def __init__(self):
        self.timeout = settings.REQUEST_TIMEOUT
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            )
        }

    def parse_url(self, url: str) -> ParsedArticle:
        if "habr.com" not in url:
            raise ValueError("Only habr.com URLs are supported")

        html = self._download(url)
        return self._parse_habr_article(html, url)

    def _download(self, url: str) -> str:
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _parse_habr_article(self, html: str, url: str) -> ParsedArticle:
        soup = BeautifulSoup(html, "html.parser")

        title = self._extract_title(soup)
        text = self._extract_article_text(soup)

        if not title:
            raise ValueError("Could not extract article title")
        if not text:
            raise ValueError("Could not extract article text")

        metadata = {
            "source": "habr",
            "url": url,
            "author": self._extract_author(soup),
            "tags": self._extract_tags(soup),
        }

        return ParsedArticle(
            title=title,
            text=text,
            metadata=metadata,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        selectors = [
            "h1.tm-title.tm-title_h1 span",
            "h1.tm-title span",
            "h1",
        ]
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                return normalize_text(node.get_text(" ", strip=True))
        return ""

    def _extract_article_text(self, soup: BeautifulSoup) -> str:
        selectors = [
            "div.tm-article-body",
            "div.article-formatted-body",
            "div.tm-article-presenter__body",
            "article",
        ]

        article_node = None
        for selector in selectors:
            article_node = soup.select_one(selector)
            if article_node:
                break

        if not article_node:
            return ""

        for bad in article_node.select("script, style, button"):
            bad.decompose()

        blocks: list[str] = []

        for node in article_node.find_all(
            ["h2", "h3", "h4", "p", "li", "blockquote", "pre", "code"]
        ):
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append(text)

        return "\n\n".join(blocks).strip()

    def _extract_author(self, soup: BeautifulSoup) -> str:
        selectors = [
            "a.tm-user-info__username",
            "span.tm-user-info__userpic + div a",
            "a[rel='author']",
        ]
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                return normalize_text(node.get_text(" ", strip=True))
        return ""

    def _extract_tags(self, soup: BeautifulSoup) -> list[str]:
        tags = []
        for node in soup.select("a.tm-tags-list__link, a[href*='/tag/']"):
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                tags.append(text)
        return list(dict.fromkeys(tags))