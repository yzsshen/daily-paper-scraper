import os
import re

import requests
from bs4 import BeautifulSoup


def get_paper_info(date):
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


def get_arxiv_pdf_link(paper_id):
    paper_url = f"https://huggingface.co/papers/{paper_id}"
    response = requests.get(paper_url)
    soup = BeautifulSoup(response.content, "html.parser")
    pdf_link = soup.find(
        "a", href=lambda href: href and href.startswith("https://arxiv.org/pdf/")
    )
    return pdf_link["href"] if pdf_link else None


def sanitize_filename(title):
    title = re.sub(pattern=r'[<>:"/\\|?*]', repl="", string=title)
    title = re.sub(pattern=r"\s+", repl="_", string=title)
    title = title.strip("._")
    return title[:100]


def download_pdf(pdf_url, pdf_title, output_dir):
    # Sanitize the title for use in filename
    sanitized_title = sanitize_filename(pdf_title.lower())

    # Create a filename using the sanitized title and the last part of the URL
    url_part = pdf_url.split("/")[-1]
    filename = f"{sanitized_title}_{url_part}.pdf"

    full_path = os.path.join(output_dir, filename)

    # Check if the file already exists
    if os.path.exists(full_path):
        print(f"File already exists, skipping: {full_path}")
        return

    # If the file doesn't exist, proceed with download
    response = requests.get(pdf_url)
    if response.status_code == 200:
        with open(full_path, "wb") as f:
            f.write(response.content)
        print(f"Downloaded: {full_path}")
    else:
        print(f"Failed to download: {pdf_url}")


def main() -> None:
    output_dir = "./papers/"

    paper_ids = get_paper_info("2023-05-04")
    print(paper_ids)

    for id, title in paper_ids:
        pdf_url = get_arxiv_pdf_link(id)

        download_pdf(pdf_url, title, output_dir)


if __name__ == "__main__":
    main()
