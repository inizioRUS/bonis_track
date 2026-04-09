from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from core.config import settings


class HabrTool:
    def __init__(self) -> None:
        self.timeout = settings.request_timeout_sec
        self.headers = {
            "User-Agent": "Mozilla/5.0",
        }

    async def get_article_text(self, url: str) -> dict:
        print(url)
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "lxml")

        title_node = soup.select_one("h1")
        title = title_node.get_text(" ", strip=True) if title_node else ""

        article_node = (
            soup.select_one("div.tm-article-body")
            or soup.select_one("div.article-formatted-body")
            or soup.select_one("article")
        )

        if not article_node:
            return {"url": url, "title": title, "text": "", "source": "habr"}

        for bad in article_node.select("script, style, button"):
            bad.decompose()

        parts: list[str] = []
        for node in article_node.find_all(["h2", "h3", "h4", "p", "li", "blockquote", "pre"]):
            text = node.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                parts.append(text)
        print(text)
        return {
            "url": url,
            "title": title,
            "text": "\n\n".join(parts),
            "source": "habr",
        }