import argparse
import os
import re
from datetime import datetime, timedelta

import requests
import yaml
from bs4 import BeautifulSoup
from loguru import logger

DEFAULT_CONFIG = {
    "output_directory": "./papers/",
    "checked_dates": [],
}


def ensure_config_exists() -> None:
    if not os.path.exists("config.yaml"):
        with open("config.yaml", "w") as file:
            yaml.dump(DEFAULT_CONFIG, file)
        logger.info("Created default config.yaml file.")

        # Create the default papers directory if it doesn't exist
        default_output_dir = DEFAULT_CONFIG["output_directory"]
        if not os.path.exists(default_output_dir):
            os.makedirs(default_output_dir)
            logger.info(f"Created default output directory: {default_output_dir}")


def load_config():
    ensure_config_exists()
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)


def save_config(config) -> None:
    with open("config.yaml", "w") as file:
        yaml.dump(config, file)


def get_checked_dates() -> str:
    config = load_config()
    return config.get("checked_dates", [])


def get_output_directory() -> str:
    config = load_config()
    return config["output_directory"]


def add_checked_date(new_date) -> None:
    config = load_config()
    if "checked_dates" not in config:
        config["checked_dates"] = []
    if new_date not in config["checked_dates"]:
        config["checked_dates"].append(new_date)
        # Keep the dates in order
        config["checked_dates"].sort()
    save_config(config)


def get_date_to_check(mode) -> str | None:
    if mode == "daily":
        date_to_check = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return date_to_check
    elif mode == "historical":
        all_dates = set(get_checked_dates())
        today = datetime.now().date()
        for i in range(1, (today - datetime(2023, 5, 3).date()).days + 1):
            date_to_check = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if date_to_check not in all_dates:
                return date_to_check
        logger.info("All historical dates have been checked.")
        return None


def get_paper_info(date) -> list:
    url = f"https://huggingface.co/papers?date={date}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    paper_links = soup.find_all(
        "a",
        href=lambda href: href and href.startswith("/papers/"),
        class_="line-clamp-3 cursor-pointer text-balance",
    )

    paper_info = []
    for link in paper_links:
        paper_id = link["href"].split("/")[-1].split("#")[0]
        title = link.text.strip()
        paper_info.append((paper_id, title))

    return paper_info


def get_arxiv_pdf_link(paper_id) -> str:
    paper_url = f"https://huggingface.co/papers/{paper_id}"
    response = requests.get(paper_url)
    soup = BeautifulSoup(response.content, "html.parser")
    pdf_link = soup.find(
        "a", href=lambda href: href and href.startswith("https://arxiv.org/pdf/")
    )
    return pdf_link["href"] if pdf_link else None


def sanitize_filename(title) -> str:
    title = re.sub(pattern=r'[<>:"/\\|?*]', repl="", string=title)
    title = re.sub(pattern=r"\s+", repl="_", string=title)
    title = title.strip("._")
    return title[:100]


def download_pdf(pdf_url, pdf_title, output_dir) -> None:
    # Sanitize the title for use in filename
    sanitized_title = sanitize_filename(pdf_title.lower())

    # Create a filename using the sanitized title and the last part of the URL
    url_part = pdf_url.split("/")[-1]
    filename = f"{sanitized_title}_{url_part}.pdf"

    full_path = os.path.join(output_dir, filename)

    # Check if the file already exists
    if os.path.exists(full_path):
        logger.info(f"File already exists, skipping: {full_path}")
        return

    # If the file doesn't exist, proceed with download
    response = requests.get(pdf_url)
    if response.status_code == 200:
        with open(full_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Downloaded: {full_path}")
    else:
        logger.info(f"Failed to download: {pdf_url}")


def download_papers(date, output_dir) -> None:
    paper_ids = get_paper_info(date)

    if not paper_ids:
        logger.info(f"No papers found for {date}.")
        return False

    logger.info(f"Found {len(paper_ids)} papers for {date}...")

    all_skipped = True
    downloaded = 0
    for id, title in paper_ids:
        pdf_url = get_arxiv_pdf_link(id)
        if pdf_url:
            downloaded += 1
            download_pdf(pdf_url, title, output_dir)
            all_skipped = False  # At least one paper was downloaded

    if not all_skipped:
        logger.info(f"Finished downloading {downloaded} papers for {date}!")
    return all_skipped


def main() -> None:
    logger.add(
        f"./logs/daily_paper_scraper_{datetime.now().strftime('%Y-%m-%d')}.log",
        colorize=True,
        format="<green>{time:YYYY-MM-DD at HH:mm:ss}</green> | <level>{level}</level> | {message}",
    )
    parser = argparse.ArgumentParser(
        description="Download papers in daily or historical mode."
    )
    parser.add_argument(
        "mode",
        choices=["daily", "historical"],
        help="Choose 'daily' for yesterday's papers or 'historical' for unchecked dates",
    )
    args = parser.parse_args()
    mode = args.mode

    logger.info(f"Using {mode} mode...")
    output_dir = get_output_directory()
    logger.info(f"Output directory: {output_dir}")

    if mode == "daily":
        date_to_check = get_date_to_check(mode)
        logger.info(f"Checking papers for: {date_to_check}")
        if download_papers(date_to_check, output_dir):
            add_checked_date(date_to_check)
    elif mode == "historical":
        checked_dates = set(get_checked_dates())
        start_date = datetime(2023, 5, 3).date()
        date_to_check = datetime.strptime(get_date_to_check(mode), "%Y-%m-%d").date()

        while date_to_check >= start_date:
            date_str = date_to_check.strftime("%Y-%m-%d")
            if date_str not in checked_dates:
                logger.info(f"Checking papers for: {date_str}")
                if download_papers(date_str, output_dir):
                    add_checked_date(date_str)
            else:
                logger.info(f"Skipping already checked date: {date_str}")
            date_to_check -= timedelta(days=1)

        logger.info("Finished processing all historical dates.")

    logger.info(f"Completed {mode} mode, exiting!")


if __name__ == "__main__":
    main()
