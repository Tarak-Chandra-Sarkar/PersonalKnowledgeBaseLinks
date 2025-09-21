import requests
from bs4 import BeautifulSoup
from newspaper import Article
from async_json_logger import AsyncJsonLogger

# Setup logger (reuses same style as pkb_main.py)
logger_setup = AsyncJsonLogger("summary_module", "logs/pkb_log.json")
logger = logger_setup.get_logger()


def extract_text_from_url(url: str) -> str:
    """
    Extracts main content text from a given URL with special handling
    for Medium, GitHub, LinkedIn, and generic sites.
    """
    try:
        logger.info(f"Extracting text from URL: {url}")

        # --- Medium / Blog posts ---
        if "medium.com" in url or "blog" in url:
            article = Article(url)
            article.download()
            article.parse()
            text = article.text.strip()
            logger.info(f"Extracted Medium/Blog content ({len(text)} chars)")
            return text

        # --- LinkedIn (skipped due to scraping rules) ---
        if "linkedin.com" in url:
            msg = "[LinkedIn content skipped: authentication required]"
            logger.warning(f"Skipping LinkedIn URL: {url}")
            return msg

        # --- GitHub repositories ---
        if "github.com" in url:
            # Ensure link points to README
            if url.endswith("/"):
                url += "blob/main/README.md"
            elif "blob" not in url:
                url += "/blob/main/README.md"

            raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob", "")
            response = requests.get(raw_url, timeout=10)
            response.raise_for_status()
            logger.info(f"Extracted GitHub README ({len(response.text)} chars)")
            return response.text.strip()

        # --- Generic fallback (scrape <p> tags) ---
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        text = "\n".join(paragraphs).strip()
        logger.info(f"Extracted generic content ({len(text)} chars)")
        return text

    except Exception as e:
        error_msg = f"[Error extracting text: {e}]"
        logger.error(error_msg)
        return error_msg


def summarize_text_with_llama(text: str, model: str = "ai/llama3.2:1B-Q4_0", max_tokens: int = 100,
                              summary_length: str = "short") -> str:
    """
    Summarizes text using a local Llama model.
    summary_length: "short" (~1-2 Sentences), "medium" (~2-3 Sentences), "long" (~3-5 Sentences)
    """
    if not text or text.startswith("[Error"):
        return text

    instructions = {
        "short": "Summarize in about Strictly 1-2 concise sentences.",
        "medium": "Summarize in Strictly 2-3 concise sentences.",
        "long": "Provide a detailed summary in Strictly 3-5 concise sentences."
    }
    system_msg = instructions.get(summary_length, instructions["short"])

    payload = {
        "model": model,
        "stream": False,
        "options": {"num_predict": max_tokens},
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": text}
        ]
    }

    try:
        logger.info(f"Sending text to Llama for summarization ({len(text)} chars, mode={summary_length})")
        response = requests.post(
            "http://localhost:12434/engines/llama.cpp/v1/chat/completions",
            json=payload, timeout=120
        )
        response.raise_for_status()
        summary = response.json()["choices"][0]["message"]["content"].strip()
        logger.info(f"Generated summary ({len(summary)} chars)")
        return summary

    except Exception as e:
        error_msg = f"[Summarization error: {e}]"
        logger.error(error_msg)
        return error_msg


def summarize_url(url: str, summary_length: str = "short") -> str:
    """
    Full pipeline: extract text from URL -> summarize it.
    """
    logger.info(f"Processing URL: {url}")
    text = extract_text_from_url(url)

    if not text or "LinkedIn content skipped" in text:
        return text

    summary = summarize_text_with_llama(text, summary_length=summary_length)
    return summary
