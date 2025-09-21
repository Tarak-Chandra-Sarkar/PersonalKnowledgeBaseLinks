import os
import re
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
import markdown
from datetime import datetime
from category_keywords import CATEGORY_KEYWORDS
import summarizer
import logging
from async_json_logger import AsyncJsonLogger
import argparse

# Set up logger
logger_setup = AsyncJsonLogger("personal_knowledge_base", "logs/pkb_log.json", level=logging.DEBUG)
logger = logger_setup.get_logger()

# Path setup
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
NEW_LINKS_FILE = os.path.join(BASE_DIR, 'links', 'new_links.md')
CATEGORIES_DIR = os.path.join(BASE_DIR, 'categories')

if not os.path.exists(CATEGORIES_DIR):
    os.makedirs(CATEGORIES_DIR)


def read_links_from_file(filepath):
    """Read links line by line from a file."""
    try:
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.warning(f"File not found: {filepath}")
        return []


def remove_invalid_chars(raw_text: str) -> str:
    """Remove non-printable characters from a string."""
    clean_text = re.sub(r'[^\x00-\x7F]', '', raw_text)
    return clean_text


def fetch_title(url):
    """Fetch webpage title, fallback to URL if unavailable."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else url
        return title
    except Exception as ex:
        logger.error(f"Title fetch failed for {url}: {str(ex)}")
        return url  # fallback


def infer_category_and_tags(title):
    """Infer category and tags based on keywords in the title."""
    title_lower = title.lower()
    matched_cats = set()
    tags = set()

    for keyword, (cat, tag_list) in CATEGORY_KEYWORDS.items():
        if keyword in title_lower:
            matched_cats.add(cat)
            tags.update(tag_list)

    category = list(matched_cats)[0] if matched_cats else "Uncategorized"
    return category, sorted(tags)


def append_to_category_file(category, title, summary, link, tags=None):
    """Append a link entry to the appropriate category markdown file."""
    category_file = os.path.join(CATEGORIES_DIR, f'{category}.md')
    date_added = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tag_str = " ".join(tags) if tags else ""
    link_entry = f"- [{title}]({link}) : {summary} {tag_str} - Added on: [{date_added}]\n"

    if not os.path.exists(category_file):
        with open(category_file, 'w') as file:
            file.write(f"# {category}\n\n")

    with open(category_file, 'a') as file:
        file.write(link_entry)


def process_new_links(summary_length="short"):
    """Process new links from new_links.md file."""
    links = read_links_from_file(NEW_LINKS_FILE)
    logger.info(f"Found {len(links)} new links.")

    for link in links:
        try:
            raw_title = fetch_title(link)
            title = remove_invalid_chars(raw_title)

            summary = summarizer.summarize_url(link, summary_length=summary_length)

            category, tags = infer_category_and_tags(title)
            append_to_category_file(category, title, summary, link, tags)

            logger.info(f"Processed link: {title} ({category}) with tags {tags}")

        except Exception as ex:
            logger.error(f"Failed to process link {link}: {str(ex)}")
            continue

    print(f"Processed {len(links)} new links.")


def search_links(query):
    """Search all category files for links matching a query."""
    results = []
    for category_file in os.listdir(CATEGORIES_DIR):
        if category_file.endswith('.md'):
            category_path = os.path.join(CATEGORIES_DIR, category_file)
            with open(category_path, 'r') as file:
                content = file.readlines()

                for line in content:
                    match = re.match(r'- \[(.+?)\]\((http[s]?://[^\)]+)\) : (.+?) (#[\w\s#]*)? - Added on:', line)
                    if match:
                        title, link, summary, tags = match.groups()
                        tags = tags.strip() if tags else ""
                        if (query.lower() in title.lower() or
                            query.lower() in summary.lower() or
                            query.lower() in tags.lower()):
                            results.append({
                                'title': title,
                                'link': link,
                                'summary': summary,
                                'tags': tags,
                                'category': category_file.replace('.md', '')
                            })
    return results



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Personal Knowledge Base Manager")
    parser.add_argument("--process", action="store_true", help="Process new links from new_links.md")
    parser.add_argument("--summary-length", choices=["short", "medium", "long"], default="short",
                        help="Length of generated summaries")
    parser.add_argument("--search", type=str, help="Search query for stored links")

    args = parser.parse_args()

    logger.info("PKB Service started")

    if args.process:
        process_new_links(summary_length=args.summary_length)

    if args.search:
        results = search_links(args.search)
        for result in results:
            print(f"{result['title']} ({result['category']}): {result['link']}")

    logger_setup.stop()
