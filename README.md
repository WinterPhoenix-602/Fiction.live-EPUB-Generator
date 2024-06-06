# Fiction.live EPUB Generator

## Overview

This Python script is designed to create EPUB files from stories on the [fiction.live](https://fiction.live) website. It utilizes web scraping with Selenium and HTML parsing with BeautifulSoup to extract story information and chapter content. The EPUB files are generated using the ebooklib library.

## Features

- Validates fiction.live story URLs.
- Retrieves book information (title, author, chapters, etc.) from the provided URL.
- Downloads and formats chapters and appendix entries.
- Handles and formats polls within the chapters.
- Creates EPUB files with metadata, a title page, table of contents, and formatted chapters.
- Allows customization of the EPUB file name and handles duplicate names.
- Provides a user-friendly interface for inputting URLs and specifying the output directory.

## Requirements

- Python 3.x
- [Selenium](https://www.selenium.dev/documentation/en/)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [ebooklib](https://github.com/aerkalov/ebooklib)
- [Chrome WebDriver](https://sites.google.com/chromium.org/driver/)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/WinterPhoenix-602/Fiction.live-EPUB-Generator
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Download and install the [Chrome WebDriver](https://sites.google.com/chromium.org/driver/).

## Usage

1. Run the script:

```bash
python fiction_live_epub_generator.py
```

2. Enter the story URL(s) when prompted.

3. Specify the directory to save the EPUB file(s). (You may edit the script to include a default directory, which can then be accessed by entering 'def' when prompted for a directory.)

4. The script will generate EPUB files for each provided URL and save them to the specified directory.

## Example

```bash
python FictionLiveScraper.py
Enter Story URL(s): https://fiction.live/stories/Example-Story/Example-Story-ID https://fiction.live/stories//Example-Story-ID2
```
