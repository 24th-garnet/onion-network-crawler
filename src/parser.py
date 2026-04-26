from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ExtractedLink:
    href: str
    anchor_text: str


@dataclass(frozen=True)
class ParsedPage:
    title: str | None
    meta_description: str | None
    links: list[ExtractedLink]


def parse_html(html: str) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")

    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    meta_description = None
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        meta_description = str(meta["content"]).strip()

    links: list[ExtractedLink] = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        anchor_text = a.get_text(" ", strip=True)
        links.append(ExtractedLink(href=str(href).strip(), anchor_text=anchor_text))

    return ParsedPage(
        title=title,
        meta_description=meta_description,
        links=links,
    )