"""
Task 2 — Crawl bài báo về nghệ sĩ liên quan tới ma tuý.

Hướng dẫn:
    1. Crawl tối thiểu 5 bài báo từ các trang tin tức Việt Nam.
    2. Sử dụng requests + BeautifulSoup giống notebook tham khảo.
    3. Lưu output vào data/landing/news/
    4. Mỗi bài lưu 1 file JSON với metadata (url, title, date_crawled, content).

Cài đặt:
    pip install requests beautifulsoup4 lxml
"""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


ARTICLE_URLS = [
    "https://vnexpress.net/dien-vien-hai-huu-tin-bi-dieu-tra-hai-toi-4475578.html",
    "https://vnexpress.net/nha-thiet-ke-nguyen-cong-tri-bi-bat-vi-lien-quan-ma-tuy-4917929.html",
    "https://vnexpress.net/rapper-binh-gold-tiep-tuc-duong-tinh-voi-ma-tuy-lai-cuop-taxi-4919259.html",
    "https://vnexpress.net/anh-em-ca-si-chi-dan-ru-nhieu-nguoi-choi-ma-tuy-nhu-the-nao-4929804.html",
    "https://vnexpress.net/ca-si-long-nhat-son-ngoc-minh-bi-bat-vi-lien-quan-ma-tuy-5060857.html",
    "https://vnexpress.net/ca-si-miu-le-bi-bat-voi-cao-buoc-to-chuc-su-dung-ma-tuy-5074769.html",
    "https://vnexpress.net/nguoi-mau-andrea-aybar-cung-tro-ly-lam-tiec-ma-tuy-trong-can-ho-cao-cap-5059429.html",
]


def clean_text(text: str) -> str:
    """Làm sạch text nhưng vẫn giữ dấu tiếng Việt và xuống dòng."""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_text_or_empty(soup: BeautifulSoup, selector: str) -> str:
    """Lấy text từ selector, không có thì trả về chuỗi rỗng."""
    tag = soup.select_one(selector)
    return clean_text(tag.get_text(" ", strip=True)) if tag else ""


def extract_paragraphs(soup: BeautifulSoup) -> list[str]:
    """Lấy toàn bộ đoạn text chính của bài VnExpress."""
    article = (
        soup.select_one("article.fck_detail")
        or soup.select_one("article")
        or soup.select_one("div.fck_detail")
        or soup.select_one("div.sidebar-1")
    )

    if article is None:
        return []

    for bad in article.select(
        "script, style, iframe, noscript, table.tplCaption, div.item_slide_show, "
        "div.box_embed_video, div.embed_video_new, div.social_pin, div.banner-ads, "
        "div.related_news, div.list_link, div.box_brief_info, button"
    ):
        bad.decompose()

    paragraphs = []
    for p in article.select("p"):
        text = clean_text(p.get_text(" ", strip=True))
        if not text:
            continue

        lower = text.lower()
        if lower in {"copy link", "trở lại giải trí", "theo dõi vnexpress trên"}:
            continue
        if "độc giả gửi bài" in lower:
            continue

        paragraphs.append(text)

    if not paragraphs:
        text = clean_text(article.get_text("\n", strip=True))
        paragraphs = [line.strip() for line in text.split("\n") if line.strip()]

    seen = set()
    unique_paragraphs = []
    for paragraph in paragraphs:
        if paragraph not in seen:
            seen.add(paragraph)
            unique_paragraphs.append(paragraph)

    return unique_paragraphs


def make_safe_filename(url: str, index: int) -> str:
    """Tạo tên file JSON an toàn từ slug URL."""
    path = urlparse(url).path
    slug = Path(path).stem
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug).strip("-")
    return f"{index:02d}_{slug}.json"


async def crawl_article(url: str) -> dict:
    """
    Crawl một bài báo và trả về dict chứa metadata + content.

    Returns:
        {
            "url": str,
            "title": str,
            "date_crawled": str (ISO format),
            "content_markdown": str
        }
    """
    date_crawled = datetime.now().isoformat(timespec="seconds")
    article = {
        "url": url,
        "title": "",
        "date_crawled": date_crawled,
        "published_time": "",
        "content_markdown": "",
        "metadata": {
            "source_url": url,
            "crawled_at": date_crawled,
            "title": "",
            "published_time": "",
        },
        "content": {
            "paragraphs": [],
            "full_text": "",
        },
        "error": "",
    }

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"

        soup = BeautifulSoup(response.text, "lxml")
        title = get_text_or_empty(soup, "h1.title-detail")
        published_time = get_text_or_empty(soup, "span.date")
        paragraphs = extract_paragraphs(soup)
        full_text = "\n\n".join(paragraphs)

        article["title"] = title
        article["published_time"] = published_time
        article["content_markdown"] = f"# {title}\n\n{full_text}".strip()
        article["metadata"]["title"] = title
        article["metadata"]["published_time"] = published_time
        article["content"]["paragraphs"] = paragraphs
        article["content"]["full_text"] = full_text
    except Exception as exc:
        article["error"] = repr(exc)

    return article


async def crawl_all():
    """Crawl toàn bộ bài báo trong ARTICLE_URLS."""
    setup_directory()

    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        article = await crawl_article(url)

        # Lưu file JSON
        filename = make_safe_filename(url, i)
        filepath = DATA_DIR / filename
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2))
        print(f"  ✓ Saved: {filepath}")
        print(f"  title: {article['title'] or 'Không lấy được title'}")
        print(f"  paragraphs: {len(article['content']['paragraphs'])}")
        if article["error"]:
            print(f"  ERROR: {article['error']}")
        time.sleep(0.5)


if __name__ == "__main__":
    if not ARTICLE_URLS:
        print("⚠ Hãy điền ARTICLE_URLS trước khi chạy!")
        print("Gợi ý: tìm bài báo trên VnExpress, Tuổi Trẻ, Thanh Niên, ...")
    else:
        asyncio.run(crawl_all())
