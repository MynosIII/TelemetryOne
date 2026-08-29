"""CLI for collecting and analysing public F1 GOAT comments."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from contextlib import aclosing
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from .opinion_poll import (
    anonymize_author,
    build_opinion_payload,
    read_jsonl,
    redact_public_text,
    write_json,
    youtube_video_id,
)

CURRENT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
ATOM = "{http://www.w3.org/2005/Atom}"


def _parse_count(value: object) -> int:
    text = str(value or "0").strip().upper().replace(",", "")
    match = re.fullmatch(r"([0-9]*\.?[0-9]+)([KMB])?", text)
    if not match:
        return 0
    multipliers = {None: 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return int(float(match.group(1)) * multipliers[match.group(2)])


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def _fetch_bytes(url: str, *, accept: str, attempts: int = 4) -> bytes:
    """Fetch a public page with bounded retries and content validation."""

    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": CURRENT_BROWSER_UA, "Accept": accept},
        )
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                payload = response.read()
            if payload.strip():
                return payload
            raise ValueError("empty response")
        except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}") from last_error


def discover_youtube(query: str, *, limit: int = 30) -> list[dict[str, str]]:
    """Discover public YouTube videos without an API key from the search result page."""

    url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query})
    page = _fetch_bytes(url, accept="text/html").decode("utf-8", errors="replace")
    pattern = re.compile(
        r'"videoRenderer":\{"videoId":"(?P<id>[^"]+)".*?'
        r'"title":\{"runs":\[\{"text":"(?P<title>(?:\\.|[^"])*)"\}',
        re.DOTALL,
    )
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in pattern.finditer(page):
        video_id = match.group("id")
        if video_id in seen:
            continue
        seen.add(video_id)
        try:
            title = json.loads(f'"{match.group("title")}"')
        except json.JSONDecodeError:
            title = match.group("title")
        found.append(
            {
                "video_id": video_id,
                "title": str(title),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "query": query,
            }
        )
        if len(found) >= limit:
            break
    return found


def _youtube_rows(source: dict[str, object]) -> Iterable[dict[str, object]]:
    try:
        from youtube_comment_downloader import (
            SORT_BY_POPULAR,
            SORT_BY_RECENT,
            YoutubeCommentDownloader,
        )
    except ImportError as exc:
        raise SystemExit('Install collection extras first: pip install -e ".[scrape]"') from exc

    downloader = YoutubeCommentDownloader()
    # Upstream 0.1.76 still advertises Chrome 79, which YouTube no longer serves consistently.
    downloader.session.headers["User-Agent"] = CURRENT_BROWSER_UA
    sort_by = SORT_BY_POPULAR if source.get("sort", "popular") == "popular" else SORT_BY_RECENT
    limit = int(source.get("limit", 400))
    video_id = youtube_video_id(str(source["url"]))
    comments = downloader.get_comments_from_url(
        str(source["url"]), sort_by=sort_by, language=str(source.get("language", "en"))
    )
    for index, comment in enumerate(comments):
        if index >= limit:
            break
        author_id = str(comment.get("channel") or comment.get("author") or comment.get("cid"))
        yield {
            "platform": "youtube",
            "source_id": str(source.get("id", video_id)),
            "source_url": str(source["url"]),
            "source_title": str(source.get("title", video_id)),
            "source_published_date": str(source.get("published_date", "")),
            "query_family": str(source.get("query_family", "all-time-best")),
            "comment_id": str(comment.get("cid", "")),
            "author_hash": anonymize_author("youtube", author_id),
            "text": redact_public_text(str(comment.get("text", ""))),
            "published_at": comment.get("time_parsed") or comment.get("time") or "",
            "likes": _parse_count(comment.get("votes")),
            "is_reply": bool(comment.get("reply", False)),
            "collected_at": datetime.now(UTC).isoformat(),
        }


def _youtube_search_rows(source: dict[str, object]) -> Iterable[dict[str, object]]:
    """Discover neutral debate videos and collect each conversation as its own source."""

    include = re.compile(str(source["title_include_regex"]), re.IGNORECASE)
    driver_names = re.compile(
        r"\b(?:senna|schumacher|hamilton|verstappen|fangio|alonso|prost|lauda|clark|vettel)\b",
        re.IGNORECASE,
    )
    results = discover_youtube(str(source["query"]), limit=int(source.get("max_videos", 30)))
    for result in results:
        title = result["title"]
        if not include.search(title):
            continue
        if source.get("exclude_driver_titles", True) and driver_names.search(title):
            continue
        child = {
            **source,
            "platform": "youtube",
            "id": f"yt-auto-{result['video_id']}",
            "url": result["url"],
            "title": title,
            "limit": int(source.get("limit_per_video", 600)),
        }
        child_count = 0
        try:
            for row in _youtube_rows(child):
                child_count += 1
                yield row
            print(f"[youtube-search] {child['id']}: {child_count} comments", flush=True)
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            print(f"[youtube-search] {child['id']}: skipped ({exc})", file=sys.stderr, flush=True)


def _instagram_rows(source: dict[str, object]) -> Iterable[dict[str, object]]:
    try:
        import instaloader
    except ImportError as exc:
        raise SystemExit('Install collection extras first: pip install -e ".[scrape]"') from exc
    loader = instaloader.Instaloader(download_pictures=False, download_videos=False)
    session_user = source.get("session_user")
    if session_user:
        loader.load_session_from_file(str(session_user))
    post = instaloader.Post.from_shortcode(loader.context, str(source["shortcode"]))
    for index, comment in enumerate(post.get_comments()):
        if index >= int(source.get("limit", 400)):
            break
        yield {
            "platform": "instagram",
            "source_id": str(source["id"]),
            "source_url": str(source["url"]),
            "source_title": str(source.get("title", source["id"])),
            "source_published_date": str(source.get("published_date", "")),
            "query_family": str(source.get("query_family", "all-time-best")),
            "comment_id": str(comment.id),
            "author_hash": anonymize_author("instagram", str(comment.owner.userid)),
            "text": redact_public_text(str(comment.text)),
            "published_at": comment.created_at_utc.isoformat(),
            "likes": int(comment.likes_count),
            "is_reply": False,
            "collected_at": datetime.now(UTC).isoformat(),
        }


def _strip_html(value: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _reddit_rows(source: dict[str, object]) -> Iterable[dict[str, object]]:
    """Collect a Reddit post and its public comments from Reddit's Atom feed."""

    public_url = str(source["url"]).split("?", 1)[0].rstrip("/")
    rss_url = public_url + "/.rss?" + urllib.parse.urlencode(
        {"limit": int(source.get("limit", 500)), "sort": source.get("sort", "top")}
    )
    payload = _fetch_bytes(rss_url, accept="application/atom+xml,application/xml;q=0.9")
    root = ET.fromstring(payload)
    for index, entry in enumerate(root.findall(f"{ATOM}entry")):
        if index >= int(source.get("limit", 500)):
            break
        entry_id = (entry.findtext(f"{ATOM}id") or f"{source['id']}:{index}").strip()
        author = entry.find(f"{ATOM}author/{ATOM}name")
        author_id = author.text.strip() if author is not None and author.text else entry_id
        content = entry.findtext(f"{ATOM}content") or entry.findtext(f"{ATOM}summary") or ""
        link = entry.find(f"{ATOM}link")
        yield {
            "platform": "reddit",
            "source_id": str(source["id"]),
            "source_url": public_url,
            "source_title": str(source.get("title", source["id"])),
            "source_published_date": str(source.get("published_date", "")),
            "query_family": str(source.get("query_family", "all-time-question")),
            "comment_id": entry_id,
            "comment_url": link.get("href", "") if link is not None else "",
            "author_hash": anonymize_author("reddit", author_id),
            "text": redact_public_text(_strip_html(content)),
            "published_at": entry.findtext(f"{ATOM}updated") or "",
            "likes": 0,
            "is_reply": entry_id.startswith("t1_"),
            "collected_at": datetime.now(UTC).isoformat(),
        }


class _XenForoPostParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.posts: list[tuple[str, str, str]] = []
        self._author = ""
        self._post_id = ""
        self._capture_depth = 0
        self._quote_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "article" and "message" in classes:
            self._author = attributes.get("data-author") or ""
            self._post_id = attributes.get("data-content") or attributes.get("id") or ""
        if self._capture_depth:
            self._capture_depth += 1
            if tag == "blockquote" or "bbCodeBlock--quote" in classes:
                self._quote_depth += 1
            if tag in {"br", "p", "li"} and not self._quote_depth:
                self._parts.append(" ")
        elif "bbWrapper" in classes:
            self._capture_depth = 1
            self._parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._capture_depth and tag == "br" and not self._quote_depth:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self._capture_depth:
            return
        if tag == "blockquote" and self._quote_depth:
            self._quote_depth -= 1
        self._capture_depth -= 1
        if self._capture_depth == 0:
            text = re.sub(r"\s+", " ", "".join(self._parts)).strip()
            if text:
                self.posts.append((self._post_id, self._author, text))
            self._parts = []
            self._quote_depth = 0

    def handle_data(self, data: str) -> None:
        if self._capture_depth and not self._quote_depth:
            self._parts.append(data)


def _forum_rows(source: dict[str, object]) -> Iterable[dict[str, object]]:
    """Collect paginated XenForo discussions while excluding quoted text."""

    base_url = str(source["url"]).rstrip("/")
    seen_posts: set[str] = set()
    total_limit = int(source.get("limit", 1000))
    for page in range(1, int(source.get("max_pages", 10)) + 1):
        page_url = base_url + ("/" if page == 1 else f"/page-{page}")
        payload = _fetch_bytes(page_url, accept="text/html").decode("utf-8", errors="replace")
        parser = _XenForoPostParser()
        parser.feed(payload)
        new_on_page = 0
        for index, (post_id, author, text) in enumerate(parser.posts):
            stable_id = post_id or f"{source['id']}:{page}:{index}"
            if stable_id in seen_posts:
                continue
            seen_posts.add(stable_id)
            new_on_page += 1
            yield {
                "platform": "forum",
                "source_id": str(source["id"]),
                "source_url": base_url + "/",
                "source_title": str(source.get("title", source["id"])),
                "source_published_date": str(source.get("published_date", "")),
                "query_family": str(source.get("query_family", "all-time-question")),
                "comment_id": stable_id,
                "author_hash": anonymize_author("forum", author or stable_id),
                "text": redact_public_text(text),
                "published_at": "",
                "likes": 0,
                "is_reply": page > 1 or index > 0,
                "collected_at": datetime.now(UTC).isoformat(),
            }
            if len(seen_posts) >= total_limit:
                return
        if not new_on_page:
            return


def _phpbb_rows(source: dict[str, object]) -> Iterable[dict[str, object]]:
    """Collect a public phpBB topic, removing quoted blocks before classification."""

    base_url = str(source["url"])
    separator = "&" if "?" in base_url else "?"
    page_size = int(source.get("page_size", 15))
    seen_posts: set[str] = set()
    for page in range(int(source.get("max_pages", 20))):
        page_url = base_url if page == 0 else f"{base_url}{separator}start={page * page_size}"
        payload = _fetch_bytes(page_url, accept="text/html").decode("utf-8", errors="replace")
        new_on_page = 0
        for article in re.findall(r"<article>(.*?)</article>", payload, flags=re.DOTALL):
            post_match = re.search(r'id="post_content(\d+)"', article)
            content_match = re.search(
                r'<div class="content">(.*?)</div>', article, flags=re.DOTALL
            )
            if not post_match or not content_match:
                continue
            post_id = post_match.group(1)
            if post_id in seen_posts:
                continue
            seen_posts.add(post_id)
            new_on_page += 1
            author_match = re.search(
                r'class="username(?:-coloured)?"[^>]*>(.*?)</a>', article, flags=re.DOTALL
            )
            body = re.sub(
                r"<blockquote.*?</blockquote>", " ", content_match.group(1), flags=re.DOTALL
            )
            text = _strip_html(body)
            author = _strip_html(author_match.group(1)) if author_match else post_id
            yield {
                "platform": "forum",
                "source_id": str(source["id"]),
                "source_url": base_url,
                "source_title": str(source.get("title", source["id"])),
                "source_published_date": str(source.get("published_date", "")),
                "query_family": str(source.get("query_family", "all-time-ranking")),
                "comment_id": post_id,
                "author_hash": anonymize_author("forum", author),
                "text": redact_public_text(text),
                "published_at": "",
                "likes": 0,
                "is_reply": page > 0 or new_on_page > 1,
                "collected_at": datetime.now(UTC).isoformat(),
            }
        if not new_on_page:
            return


async def _x_rows_async(source: dict[str, object]) -> list[dict[str, object]]:
    try:
        from twscrape import API
    except ImportError as exc:
        raise SystemExit('Install collection extras first: pip install -e ".[scrape]"') from exc
    api = API(str(source.get("account_db", "accounts.db")), raise_when_no_account=True)
    rows: list[dict[str, object]] = []
    async with aclosing(
        api.search(str(source["query"]), limit=int(source.get("limit", 400)))
    ) as tweets:
        async for tweet in tweets:
            rows.append(
                {
                    "platform": "x",
                    "source_id": str(source["id"]),
                    "source_url": "https://x.com/search?q=" + str(source["query"]),
                    "source_title": str(source.get("title", source["query"])),
                    "source_published_date": str(source.get("published_date", "")),
                    "query_family": str(source.get("query_family", "all-time-best")),
                    "comment_id": str(tweet.id),
                    "author_hash": anonymize_author("x", str(tweet.user.id)),
                    "text": redact_public_text(str(tweet.rawContent)),
                    "published_at": tweet.date.isoformat(),
                    "likes": int(tweet.likeCount or 0),
                    "is_reply": tweet.inReplyToTweetId is not None,
                    "collected_at": datetime.now(UTC).isoformat(),
                }
            )
    return rows


def collect(
    config_path: Path, output_path: Path, *, shard_index: int = 0, shard_count: int = 1
) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    enabled_index = -1
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for source in config["sources"]:
            if not source.get("enabled", True):
                continue
            enabled_index += 1
            if enabled_index % shard_count != shard_index:
                continue
            platform = source["platform"]
            source_count = 0
            try:
                if platform == "youtube":
                    rows: Iterable[dict[str, object]] = _youtube_rows(source)
                elif platform == "youtube_search":
                    rows = _youtube_search_rows(source)
                elif platform == "reddit":
                    rows = _reddit_rows(source)
                elif platform == "forum":
                    rows = _forum_rows(source)
                elif platform == "phpbb_forum":
                    rows = _phpbb_rows(source)
                elif platform == "instagram":
                    rows = _instagram_rows(source)
                elif platform == "x":
                    rows = asyncio.run(_x_rows_async(source))
                else:
                    raise ValueError(f"Unsupported platform: {platform}")
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    handle.flush()
                    total += 1
                    source_count += 1
                print(f"[{platform}] {source['id']}: {source_count} comments", flush=True)
            except Exception as exc:
                if not config.get("continue_on_error", True):
                    raise
                print(f"[{platform}] {source['id']}: skipped ({exc})", file=sys.stderr, flush=True)
    return total


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the TelemetryOne public-opinion ranking")
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect_parser = subparsers.add_parser(
        "collect", help="Collect public comments from a source config"
    )
    collect_parser.add_argument("--config", type=Path, required=True)
    collect_parser.add_argument("--output", type=Path, required=True)
    collect_parser.add_argument("--shard-index", type=int, default=0)
    collect_parser.add_argument("--shard-count", type=int, default=1)
    build_parser_ = subparsers.add_parser(
        "build", help="Classify JSONL comments and export site JSON"
    )
    build_parser_.add_argument("--input", type=Path, nargs="+", required=True)
    build_parser_.add_argument("--output", type=Path, required=True)
    build_parser_.add_argument("--exclude-source", action="append", default=[])
    build_parser_.add_argument("--exclude-source-file", type=Path)
    discover_parser = subparsers.add_parser(
        "discover-youtube", help="Discover public YouTube videos for a neutral query"
    )
    discover_parser.add_argument("--query", required=True)
    discover_parser.add_argument("--limit", type=int, default=30)
    discover_parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "collect":
        if not 0 <= args.shard_index < args.shard_count:
            raise SystemExit("--shard-index must be between 0 and --shard-count - 1")
        count = collect(
            args.config,
            args.output,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
        print(f"Collected {count} public comments -> {args.output}")
        return 0
    if args.command == "discover-youtube":
        results = discover_youtube(args.query, limit=args.limit)
        serialized = json.dumps(results, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized + "\n", encoding="utf-8")
            print(f"Discovered {len(results)} videos -> {args.output}")
        else:
            print(serialized)
        return 0
    excluded_sources = set(args.exclude_source)
    if args.exclude_source_file:
        exclusion_payload = json.loads(args.exclude_source_file.read_text(encoding="utf-8"))
        excluded_sources.update(exclusion_payload.get("source_ids", []))
    rows = [
        row
        for row in read_jsonl(args.input)
        if str(row.get("source_id", "")) not in excluded_sources
    ]
    payload = build_opinion_payload(rows)
    write_json(args.output, payload)
    print(f"Built {payload['quality']['validVotes']} explicit votes -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
