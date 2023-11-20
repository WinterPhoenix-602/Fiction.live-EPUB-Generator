import math
from bs4 import BeautifulSoup
import os
import string
from ebooklib import epub
import re
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Style
import time
from bs4 import Tag

# Function to validate URL(s)
def validate_urls(urls):
    """
    Accepts either a single string or list of strings as input, and validates those strings as valid story urls from the website fiction.live.
    If a URL is not valid, then it is removed from the list and a message is displayed indicating such.
    If there are no valid URLs, a message is displayed and the program is exited.
    """
    # Regular expression pattern to match valid URLs
    pattern1 = r"^https://fiction\.live/stories//[A-Za-z0-9]+"
    pattern2 = r"^https://fiction\.live/stories/([A-Za-z0-9]+(-[A-Za-z0-9]+)+)/([A-Za-z0-9]+)(/([A-Za-z0-9]+(-[A-Za-z0-9]+)+)/[A-Za-z0-9]+)?"

    valid_urls = []
    invalid_urls = []

    # Loop through each URL and check if it is valid
    for url in urls:
        if re.match(pattern1, url): # If it is valid and in the correct format, append to valid urls
            valid_urls.append(url)
        elif re.match(pattern2, url): # If it is valid and in an incorrect format, convert and then append
            valid_urls.append(f"https://fiction.live/stories//{re.match(pattern2, url).group(3)}")
        else: # If it is invalid, append to invalid urls and display
            invalid_urls.append(url)
            print(f"{Fore.RED}Invalid URL: {url}{Style.RESET_ALL}")

    # If there are no valid URLs, display a message and exit the program
    if not valid_urls:
        print("No valid URLs found.")
        exit()

    return valid_urls

# Function to get the Table of Contents
def get_book_info(url):
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 30)
    driver.get(url)

    # Wait for the Table of Contents to load
    element_locator = (By.CLASS_NAME, "contentsInner")
    element = wait.until(EC.presence_of_element_located(element_locator))

    # Get the Table of Contents
    toc_element = driver.find_element(By.CLASS_NAME, "contentsInner")
    toc_soup = BeautifulSoup(toc_element.get_attribute("innerHTML"), "html.parser")

    # Get the book title, properties, and author
    page_soup = BeautifulSoup(driver.page_source, "html.parser")
    content_rating_tags = page_soup.find_all('span', class_="rating")
    date_string = page_soup.find('span', class_='ut')
    if date_string:
        date_string = date_string.text.strip().split("New")[0]
        date_obj = datetime.datetime.strptime(date_string, "%a, %b %d, %Y, %I:%M %p")
        formatted_date = date_obj.strftime("%Y-%m-%d")
    else:
        formatted_date = "Unknown"
    book_properties = {
        'cover_image': page_soup.find('img', class_="storyImg").get('src'),
        'title': page_soup.find("header", class_="page-title").text.strip(),
        'story_link': url,
        'author': page_soup.find('span', class_="name").text.strip(),
        'author_link': f"https://fiction.live/{page_soup.find('a', class_='inner').get('href')}",
        'published': formatted_date,
        'status': page_soup.find('span', class_="status").text.strip(),
        'content_rating': content_rating_tags[0].find('span').text.strip(),
        'word_count': content_rating_tags[2].find('span').get('data-hint').split()[0],
        'summary': page_soup.find('div', class_="fieldBody").content,
        'tags': [tag.text.strip() for tag in page_soup.find_all('a', {'class': 'tag'})],
    }

    chapter_elements = toc_soup.find_all("a", class_="ng-binding")
    home_chapter = toc_soup.find("a", class_=None)

    if home_chapter:
        chapter_elements.insert(0, home_chapter)

    appendix_elements = toc_soup.find("div", class_="ng-scope").find_all("a", class_="ng-scope")

    driver.quit()

    return book_properties, chapter_elements, appendix_elements

# Function to create the EPUB file
def create_book(book_properties, chapter_elements, appendix_elements):
    print("Creating book...")
    book = epub.EpubBook() # Create the book

    # Set metadata properties
    book.set_title(book_properties['title']) # Set the title
    book.set_language("en") # Set the language
    book.add_author(book_properties['author']) # Set the author


    # Create the title page
    title_page = epub.EpubHtml(title="Title Page", file_name="title.xhtml", lang="en")
    # Set the title page content from book properties
    title_page_html = f"""<html xmlns="http://www.w3.org/1999/xhtml">
                            <head>
                                <title>{book_properties["title"]} by {book_properties["author"]}</title>
                                <link href="stylesheet.css" type="text/css" rel="stylesheet" />
                            </head>
                            <body class="fff_titlepage">
                                <h3><a href="{book_properties["story_link"]}">{book_properties["title"]}</a> by <a class="authorlink"'
                                        f'href="{book_properties["author_link"]}">{book_properties["author"]}</a></h3>
                                <div>
                                    <b>Status:</b> {book_properties["status"]}<br />
                                    <b>Published:</b> {book_properties["published"]}<br />
                                    <b>Packaged:</b> {datetime.datetime.now()}<br />
                                    <b>Rating:</b> {book_properties["content_rating"]}<br />
                                    <b>Chapters:</b> {len(chapter_elements)}<br />
                                    <b>Words:</b> {book_properties["word_count"]}<br />
                                    <b>Publisher:</b> fiction.live<br />
                                    <b>Summary:</b> {book_properties["summary"]}<br />
                                    <b>Tags:</b> {", ".join(book_properties["tags"])}<br />
                                </div>
                            </body>
                            </html>"""
    title_page.content = title_page_html.encode('utf-8') # Set the title page content
    book.add_item(title_page)
    book.add_item(epub.EpubNav()) # Add the navigation
    book.toc += (epub.Link(f"title.xhtml", 'Title Page', f"Title Page"),)  # Add the chapter to the table of contents

    chapters_dict, appendix_dict = download_chapters(chapter_elements, appendix_elements) # Download the chapters

    book = format_chapters(book, chapters_dict, appendix_dict) # Format the chapters
    
    book.spine = list(book.get_items()) # Set the spine to the list of chapters
    book.add_item(epub.EpubNcx()) # Add the table of contents

    return book

# Function to download the chapters
def download_chapters(chapter_links, appendix_links):
    print("Downloading chapters...")
    chapters_dict = {}
    driver = webdriver.Chrome() # Create a Chrome driver
    for count, chapter in enumerate(chapter_links):
        driver.get(f"https://fiction.live/{chapter.get('href')}") # Get the chapter page
        element_locator = (By.XPATH, "//span[text()='New Comment']") # Set the element locator
        wait =WebDriverWait(driver, 30)
        element = wait.until(EC.presence_of_element_located(element_locator)) # Wait for the element to load

        # Continually scroll to the bottom of the page until no more new elements are loading
        while True:
            old_page = driver.page_source
            chapter_soup = BeautifulSoup(old_page, 'html.parser') # Create a BeautifulSoup object
            # Get the chapter content
            old_chapter_content = chapter_soup.find('div', id="storyPosts")
            old_chapter_content = old_chapter_content.find('div', class_="jadeRepeat ng-scope")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1) # Wait for any new elements to load
            new_page = driver.page_source
            chapter_soup = BeautifulSoup(new_page, 'html.parser') # Create a BeautifulSoup object
            # Get the chapter content
            chapter_content = chapter_soup.find('div', id="storyPosts")
            chapter_content = chapter_content.find('div', class_="jadeRepeat ng-scope")
            if old_chapter_content == chapter_content: # If no new elements loaded, break the loop
                break

        # Get the chapter title
        chapter_title = chapter.text.strip()
        # Create a new tag to hold the chapter title
        title_tag = chapter_soup.new_tag('h3')  # 'h1' for large text
        title_tag.string = chapter_title
        title_tag['style'] = 'font-weight: bold; text-align: center;'  # Make the text bold and centered
        # Add the title tag to the top of the chapter content
        chapter_content.insert(0, title_tag)
        # Add the chapter to the dictionary
        chapters_dict[chapter_title] = chapter_content
        print(f"Chapter {count+1}/{len(chapter_links)} downloaded.")
        
        """COMMENT OUT TO STOP TESTING"""
        #break

    print("Downloading appendix...")
    appendix_dict = {}
    for count, appendix in enumerate(appendix_links):
        driver.get(f"https://fiction.live/{appendix.get('href')}") # Get the appendix page
        element_locator = (By.XPATH, "//a[@class='expandComments showWhenDiscussionOpened']") # Set the element locator
        wait =WebDriverWait(driver, 30)
        element = wait.until(EC.presence_of_element_located(element_locator)) # Wait for the element to load

        # Continually scroll to the bottom of the page until no more new elements are loading
        while True:
            old_page = driver.page_source
            appendix_soup = BeautifulSoup(old_page, 'html.parser') # Create a BeautifulSoup object
            # Get the chapter content
            old_appendix_content = appendix_soup.find('div', id="storyPosts")
            old_appendix_content = old_appendix_content.find('div', class_="jadeRepeat ng-scope")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1) # Wait for any new elements to load
            new_page = driver.page_source
            appendix_soup = BeautifulSoup(new_page, 'html.parser') # Create a BeautifulSoup object
            # Get the chapter content
            appendix_content = appendix_soup.find('div', id="storyPosts")
            appendix_content = appendix_content.find('div', class_="jadeRepeat ng-scope")
            if old_appendix_content == appendix_content: # If no new elements loaded, break the loop
                break
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1) # Wait for any new elements to load
            new_page = driver.page_source
            if old_page == new_page: # If no new elements loaded, break the loop
                break

        # Get the appendix title
        appendix_title = appendix.text.strip()
        # Create a new tag to hold the chapter title
        title_tag = appendix_soup.new_tag('h3')  # 'h1' for large text
        title_tag.string = appendix_title
        title_tag['style'] = 'font-weight: bold; text-align: center;'  # Make the text bold and centered
        # Add the title tag to the top of the chapter content
        appendix_content.insert(0, title_tag)
        # Add the appendix to the dictionary
        appendix_dict[appendix_title] = appendix_content
        print(f"Appendix entry {count+1}/{len(appendix_links)} downloaded.")
        
        """COMMENT OUT TO STOP TESTING"""
        #break

    driver.quit()

    return chapters_dict, appendix_dict
        
# Function to format the chapters
def format_chapters(book, chapters_dict, appendix_dict):
    print("Formatting chapters...")
    # Loop through the chapters
    for count, chapter in enumerate(chapters_dict):
        remove_elements(chapters_dict, chapter) # Remove unwanted elements
        exit_tags(chapters_dict, chapter) # Exit unneeded tags
        format_polls(chapters_dict, chapter) # Format polls

        # Extract the content inside the tag
        chapter_content = chapters_dict[chapter].encode_contents()

        formatted_chapter = epub.EpubHtml(title=chapter, file_name=f"chap_{count+1}.xhtml", lang="en")  # Create the chapter
        formatted_chapter.content = chapter_content  # Set the chapter content
        book.add_item(formatted_chapter)  # Add formatted chapter to the book
        book.toc += (epub.Link(f"chap_{count+1}.xhtml", chapter, f"{chapter}"),)  # Add the chapter to the table of contents
        print(f"Chapter {count+1}/{len(chapters_dict)} formatted.")
        
    print("Formatting appendix...")
    for count, entry in enumerate(appendix_dict):
        remove_elements(appendix_dict, entry) # Remove unwanted elements
        exit_tags(appendix_dict, entry) # Exit unneeded tags
        formatted_entry = epub.EpubHtml(title=chapter, file_name=f"appendix_{count+1}.xhtml", lang="en") # Create the chapter
        formatted_entry.content = appendix_dict[entry].encode("utf-8") # Set the chapter content
        book.add_item(formatted_entry) # Add formatted chapter to the book
        book.toc += (epub.Link(f"appendix_{count+1}.xhtml", entry, f"{entry}"),) # Add the chapter to the table of contents
        print(f"Appendix entry {count+1}/{len(appendix_dict)} formatted.")
    return book

def exit_tags(chapters_dict, chapter):
    # Find content
    content = chapters_dict[chapter].find_all('article', class_='chapter')
    # Loop through the content of the chapter
    for chunk in content:
        # Extract the content within the <div> tag
        content_div = chunk.find('div', class_='chapterContent')
        content_fieldBody = content_div.find('div', class_='fieldBody')
        if content_fieldBody:
            content_fieldBody.unwrap()
        chunk.unwrap()


def remove_element_by_selector(chapters_dict, chapter_key, selector, decompose_parent=False):
    elements_to_remove = chapters_dict[chapter_key].select(selector)
    for element in elements_to_remove:
        if decompose_parent:
            parent = element.find_parent()
            parent.decompose()
        else:
            element.decompose()

def remove_elements(chapters_dict, chapter_key):
    # Define selectors for elements to remove
    selectors = {
        'footnotes': {'selector': 'footer', 'decompose_parent': False},
        'verified_results': {'selector': 'span.userVote.hint--top', 'decompose_parent': False},
        'xOut_options': {'selector': 'tr.choiceItem.xOut', 'decompose_parent': False},
        'comments': {'selector': 'td.icon.discussChoice.comment', 'decompose_parent': False},
        'auto_close_containers': {'selector': 'div.autoCloseContainer', 'decompose_parent': False},
        'custom_choices': {'selector': 'div.custom-choice', 'decompose_parent': False},
        'edit_containers': {'selector': 'div.editContainer', 'decompose_parent': False},
        'reader_suggestions': {'selector': 'div.value', 'decompose_parent': True},
        'empty_reader_posts': {'selector': 'div.readerPosts.fieldBody:empty', 'decompose_parent': True}
    }

    # Remove each type of element using defined selectors
    for element_type, options in selectors.items():
        remove_element_by_selector(chapters_dict, chapter_key, options['selector'], options['decompose_parent'])

def find_polls(chapters_dict, chapter):
    return [table_element.parent for table_element in chapters_dict[chapter].find_all('table', class_='poll')]

def extract_participants(poll_head):
    if match := re.search(r'(?<=-Voting closed - )\d+(?= voters)', poll_head.text):
        participants = int(match.group())
        return participants if participants != 0 else None
    elif 'be the first to vote' in poll_head.text:
        return None
    return None

def format_poll_head(poll_head):
    if "Voting closed -" in poll_head.text:
        if "Choices -V" in poll_head.text:
            poll_head.string = f'Poll: {poll_head.text.replace("Choices -Voting closed - ", "")}'  
        else:
            poll_head.string = f'Poll: {poll_head.text.replace("Voting closed -", "")}'

def collect_options_info(poll_options):
    options_info = []
    for option in poll_options:
        option_text = option.find('td', class_="text").find('span')
        option_result = option.find('td', class_="result")
        total_votes = int(option_result.contents[0].text)
        options_info.append({"option": option, "option_text": option_text, "total_votes": total_votes})
    return options_info

def sort_options_info(options_info):
    plus_options = []
    options_info = sorted(options_info, key=lambda x: x["total_votes"], reverse=True)
    if any(isinstance(value, Tag) and value.text.startswith('+') for dictionary in options_info for value in dictionary.values()):
            plus_options = [x for x in options_info if x["option_text"].text.startswith('+')]
            options_info = [x for x in options_info if not x["option_text"].text.startswith('+')] + plus_options
    return options_info, plus_options

def find_winners(options_info, plus_options):
    winners = []
    previous_max_votes = 0
    for option_info in options_info:
        total_votes = option_info["total_votes"]
        if total_votes > previous_max_votes and option_info not in plus_options:
            winners = [option_info]
            previous_max_votes = total_votes
        elif total_votes == previous_max_votes and option_info not in plus_options:
            winners.append(option_info)
    return winners

def find_options_to_decompose(options_info, winners, participants):
    options_to_decompose = []
    for option_info in options_info:
        total_votes = option_info["total_votes"]
        if total_votes < math.ceil(participants / 2) and option_info not in winners:
            options_to_decompose.append(option_info)
    return options_to_decompose

def decompose_options(options_info, options_to_decompose):
    for option_info in options_to_decompose:
        option = option_info["option"]
        option.decompose()
        options_info.remove(option_info)

def sort_options_by_votes(options_info, poll):
    options_table = poll.find('tbody')
    options_table.clear()
    for option_info in options_info:
        option = option_info["option"]
        options_table.append(option)

# Function to format polls
def format_polls(chapters_dict, chapter):
    # Find polls
    polls = find_polls(chapters_dict, chapter)
    # Format polls
    for poll in polls:
        poll_head = poll.find('h4', class_="poll-head")

        participants = extract_participants(poll_head)
        if participants is None:
            poll.decompose()
            continue

        format_poll_head(poll_head)

        poll_options = poll.find_all('tr', class_="choiceItem")

        options_info = collect_options_info(poll_options)

        options_info, plus_options = sort_options_info(options_info)
        
        winners = find_winners(options_info, plus_options)
        
        # Create a list of options to decompose
        options_to_decompose = find_options_to_decompose(options_info, winners, participants)

        decompose_options(options_info, options_to_decompose)

        sort_options_by_votes(options_info, poll)


# Save the EPUB file
def save_book(book, dir_path):
    # Check if the directory already contains a file with the same name
    book_title = book.title
    epub_path = os.path.join(dir_path, f"{book_title.replace(' ', '_')}.epub")

    # Check if the book title contains invalid characters
    epub_path = validate_filename(book, dir_path, epub_path, book_title)

    # Write the EPUB file to the specified directory
    print("Writing EPUB file...")
    with open(epub_path, 'wb') as epub_file:
        epub.write_epub(epub_file, book)
    print(f"EPUB file written to {Fore.YELLOW}{epub_path}{Style.RESET_ALL}")

def validate_filename(book, dir_path, epub_path, book_title):
    invalid_chars = set(string.punctuation.replace('_', ''))
    if any(char in invalid_chars for char in book_title):
        print("The book title contains invalid characters. Invalid characters will be replaced with '-'")
        new_title = "".join(["-" if char in invalid_chars else char for char in book_title])
        epub_path = os.path.join(dir_path, f"{new_title.replace(' ', '_')}.epub")
        book.set_title(new_title)
    while os.path.isfile(epub_path):
        response = input("An EPUB file with this name already exists in the directory. Do you want to overwrite it? (y/n) ")
        if response.lower() == "y":
            os.remove(epub_path)
            break
        elif response.lower() == "n":
            # Get a new name for the EPUB file
            book_title = input("Enter a new name for the EPUB file: ").replace(' ', '_')
            book.set_title(book_title)
            epub_path = os.path.join(dir_path, f"{book_title}.epub")
        else:
            print("Invalid response. Please enter 'y' or 'n'.")
    return epub_path

# The main function
def main():  # sourcery skip: hoist-statement-from-loop
    # Get the URL(s) of the Table of Contents or Chapter
    story_urls = input("Enter Story URL(s): ")
    #story_urls = "https://fiction.live/stories/Shifting-The-Temporal-Tides/8J6NzhNiq7fE6XHnd" # Testing url 1
    #story_urls = "https://fiction.live/stories/A-Hero-s-Journey/9jH3ggZgk9JdJWQWt" # Testing url 2
    story_urls = story_urls.split(" ") if " " in story_urls else [story_urls]
    # Check if the URL(s) is/are valid
    story_urls = validate_urls(story_urls)

    # Get the directory where the EPUB file will be saved
    while True:
        #dir_path = input("Enter the directory where you want to save the EPUB file(s): ") # Get the directory path from the user
        dir_path = "C:\\Users\\caide\\Desktop\\Personal Projects\\Epub Editing\\Fiction.live\\Epubs" # Test directory
        # Check if the directory is valid
        try:
            if not os.path.isdir(dir_path):
                raise ValueError
        except ValueError:
            print("Invalid directory. Please enter a valid directory.")
            continue
        else:
            break

    # Loop through the URLs and create an EPUB file for each one
    for url in story_urls:
        book_properties, chapter_elements, appendix_elements = get_book_info(url)
        book = create_book(book_properties, chapter_elements, appendix_elements)
        save_book(book, dir_path)
        del book

# Run the main function if the script is run directly
if __name__ == "__main__":
     main()