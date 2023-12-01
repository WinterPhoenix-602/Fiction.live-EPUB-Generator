import requests
from bs4 import BeautifulSoup
import itertools
import sys
import logging
from six import text_type as unicode
logger = logging.getLogger(__name__)
import json
from ebooklib import epub
from exceptions import *
from FictionLiveScraper import save_book
from datetime import datetime
import os
import re
from colorama import Fore, Style

session = requests.Session()
achievements = []

# Function to validate URL(s)
def validate_urls(urls):
    """
    Accepts either a single string or list of strings as input, and validates those strings as valid story urls from the website fiction.live.
    If a URL is not valid, then it is removed from the list and a message is displayed indicating such.
    If there are no valid URLs, a message is displayed and the program is exited.
    """
    # Regular expression pattern to match valid URLs
    pattern1 = r"^https://fiction\.live/stories//([A-Za-z0-9]{17})"
    pattern2 = r"^https://fiction\.live/stories/([A-Za-z0-9]+(-[A-Za-z0-9]*)+)/([A-Za-z0-9]{17})(/([A-Za-z0-9]+(-[A-Za-z0-9]+)+)/[A-Za-z0-9]+)?"

    valid_urls = []
    invalid_urls = []

    # Loop through each URL and check if it is valid
    for url in urls:
        if re.match(pattern1, url): # If it is valid and in the correct format, append to valid urls
            valid_urls.append(
                {
                    'story':url, 
                    'meta':f"https://fiction.live/api/node/{re.match(pattern2, url)[0]}"
                    }
                    )
        elif re.match(pattern2, url): # If it is valid and in an incorrect format, convert and then append
            valid_urls.append(
                {
                    'story': f"https://fiction.live/stories//{re.match(pattern2, url)[3]}",
                    'meta': f"https://fiction.live/api/node/{re.match(pattern2, url)[3]}"
                }
            )
        else: # If it is invalid, append to invalid urls and display
            invalid_urls.append(url)
            print(f"{Fore.RED}Invalid URL: {url}{Style.RESET_ALL}")

    # If there are no valid URLs, display a message and exit the program
    if not valid_urls:
        print("No valid URLs found.")
        exit()

    return valid_urls

def get_book_info(metadata_url):
    if story_metadata := session.get(metadata_url).text:
        if story_metadata != "null":
            story_metadata = json.loads(story_metadata)
            # gonna need these later for adding details to achievement-granting links in the text
            try:
                achievements = story_metadata['achievements']['achievements']
            except KeyError:
                achievements = []
            return story_metadata
    print(f"{Fore.RED}Story does not exist: ({metadata_url})")
    return None


def get_chapters_appendices_and_routes(book_data):
    chapters_list = []
    appendices_list = []
    routes_list = []
    def add_chapter_url(title, bounds, isAppendix = False):
        "Adds a chapter url based on the start/end chunk-range timestamps."
        start, end = bounds
        end -= 1
        chapter_url = f"https://fiction.live/api/anonkun/chapters/{book_data['_id']}/{start}/{end}/"
        if isAppendix:
            appendices_list.append({'title': title, 'url': chapter_url})
            return
        chapters_list.append({'title': title, 'url': chapter_url})

    def add_route_chapter_url(title, route_id):
        "Adds a route chapter url based on the route id."
        chapter_url = f"https://fiction.live/api/anonkun/route/{route_id}/chapters"
        routes_list.append({'title': title, 'url': chapter_url})

    def pair(iterable):
        "[1,2,3,4] -> [(1, 2), (2, 3), (3, 4)]"
        a, b = itertools.tee(iterable, 2)
        next(b, None)
        return list(zip(a, b))

    ## first thing to do is seperate out the appendices
    appendices, maintext, routes = [], [], []
    chapters = book_data['bm'] if 'bm' in book_data else []

    ## not all stories use multiple routes. Those that do have a route id and a title for each route
    if 'route_metadata' in book_data and book_data['route_metadata']:
        for r in book_data['route_metadata']:
            # checking if route title even exists or is None, since most things in the api are optional
            title = r['t'] if 't' in r and r['t'] is not None else ""
            routes.append({"id": r['_id'], "title": title})

    for c in chapters:
        appendices.append(c) if c['title'].startswith('#special') else maintext.append(c)

    ## main-text chapter extraction processing. *should* now handle all the edge cases.
    ## relies on fanficfare ignoring empty chapters!

    titles = [c['title'] for c in maintext]
    titles = ["Home"] + titles

    most_recent_chunk = book_data['cht'] if 'cht' in book_data else 9999999999999998
    times = [c['ct'] for c in maintext]
    times = [book_data['ct']] + times + [most_recent_chunk + 2] # need to be 1 over, and add_url etc does -1

    # doesn't actually run without the call to list.
    list(map(add_chapter_url, titles, pair(times)))

    for a in appendices: # add appendices afterwards
        chapter_start = a['ct']
        chapter_title = "Appendix: " + a['title'][9:] # 'Appendix: ' rather than '#special' at beginning of name
        add_chapter_url(chapter_title, (chapter_start, chapter_start + 2), True) # 1 msec range = this one chunk only

    for r in routes:  # add route at the end, after appendices
        route_id = r['id']  # to get route chapter content, the route id is needed, not the timestamp
        chapter_title = "Route: " + r['title']  # 'Route: ' at beginning of name, since it's a multiroute chapter
        add_route_chapter_url(chapter_title, route_id)
    return chapters_list, appendices_list, routes_list

def parse_timestamp(timestamp):
    """Parse a timestamp and convert it to a datetime object.

    This function takes in a timestamp and converts it to a datetime object by dividing it by 1000.0 and using the `datetime.fromtimestamp()` method. The resulting datetime object is returned.

    Args:
        timestamp (float): The timestamp to be parsed.

    Returns:
        datetime.datetime: The parsed timestamp as a datetime object."""

    return datetime.fromtimestamp(timestamp / 1000.0, None)

def make_soup(data):
    '''
    Convenience method for getting a bs4 soup.  bs3 has been removed.
    '''

    ## html5lib handles <noscript> oddly.  See:
    ## https://bugs.launchpad.net/beautifulsoup/+bug/1277464 This
    ## should 'hide' and restore <noscript> tags.  Need to do
    ## </?noscript instead of noscript> as of Apr2022 when SB
    ## added a class attr to noscript.  2x replace() faster than
    ## re.sub() in simple test
    data = data.replace("<noscript","<hide_noscript").replace("</noscript","</hide_noscript")

    ## soup and re-soup because BS4/html5lib is more forgiving of
    ## incorrectly nested tags that way.
    soup = BeautifulSoup(data,'html5lib')
    soup = BeautifulSoup(unicode(soup),'html5lib')

    for ns in soup.find_all('hide_noscript'):
        ns.name = 'noscript'

    return soup

def format_chapter(chunk):
    """Handles any formatting in the chapter body text for text chapters.
    In the 'default case' where we're getting boring chapter-chunk body text, just calls utf8fromSoup
    and returns the text as is on the website."""

    soup = make_soup(chunk['b'] if 'b' in chunk else "")
    soup = add_spoiler_legends(soup)
    soup = append_achievments(soup)

    return str(soup)

def add_spoiler_legends(soup):
    # find spoiler links and change link-anchor block to legend block
    spoilers = soup.find_all('a', class_="tydai-spoiler")
    for link_tag in spoilers:
        link_tag.name = 'fieldset'
        legend = soup.new_tag('legend')
        legend.string = "Spoiler"
        link_tag.insert(0, legend)
    return soup

def fictionlive_normalize(string):
    # might be able to use this to preserve titles in normalized urls, if the scheme is the same

    # BUG: in achivement ids these are all replaced, but I *don't* know that the list is complete.
    # should be rare, thankfully. *most* authors don't use any funny characters in the achievment's *ID*
    special_chars = "\"\\,.!?+=/[](){}<>_'@#$%^&*~`;:|" # not the hyphen, which is used to represent spaces

    return string.lower().replace(" ", "-").translate({ord(x) : None for x in special_chars})

def append_achievments(soup):
    # achivements are present in the text as a kind of link, and you get the shiny popup by clicking them.
    achievement_links = soup.find_all('a', class_="tydai-achievement")

    achieved_ids = []
    for link_tag in achievement_links:
        # these are not only prepended by a unicode lightning-bolt, but also format clearly as a link
        # should use .u css selector -- part of output_css defaults? or just let replace_tags_with_spans do it?
        new_u = soup.new_tag('u')
        new_u.string = link_tag.text # copy out the link text into a new element
        # html entities for improved compatability with AZW3 conversion
        link_tag.string = "&#x26A1;" # then overwrite
        link_tag.insert(1, new_u)

        ## while we've got the achievment links, get the ids from the link
        a_id = link_tag['data-id']
        a_id = fictionlive_normalize(a_id)

        achieved_ids.append(a_id)

    if achieved_ids:
        logger.debug("achievements (this chunk): " + ", ".join(achieved_ids))

    # can't replicate the animated shiny announcement popup, so have an end-of-chunk announcement instead
    # TODO: achievement images -- does anyone use them?
    a_source = "<br />\n<fieldset><legend>&#x26A1; Achievement obtained!</legend>\n<h4>{}</h4>\n{}</fieldset>\n"

    for a_id in achieved_ids:
        if a_id in achievements:
            a_title = achievements[a_id]['t']  if 't' in achievements[a_id] else a_id.title()
            a_text = achievements[a_id]['d'] if 'd' in achievements[a_id] else ""
            soup.append(make_soup(a_source.format(a_title, a_text)))
        else:
            a_title = a_id.title()
            error = "<br />\n<fieldset><legend>Error: Achievement not found.</legend>Couldn't find '{}'. Ask the story author to check if the achievment exists."
            soup.append(make_soup(error.format(a_title)))

    return soup

def count_votes(chunk):
    """So, fiction.live's api doesn't return the counted votes you see on the website.
    After all, it needs to allow for things like revoking a vote,
    with the count live and updated in realtime on your client.
    So instead we get the raw vote-data, but have to count it ourselves."""

    # optional.
    choices = chunk['choices'] if 'choices' in chunk else []

    def counter(votes):
        output = [0] * len(choices)
        for vote in votes.values():
            ## votes are either a single option-index or a list of option-indicies, depending on the choice type
            if 'multiple' in chunk and chunk['multiple'] == False:
                vote = [vote] # normalize to list
            for v in vote:
                # v should only be int, but there is at least one story where some unrelated string was returned,
                #   so let's just ignore non-int values here
                if not isinstance(v, int):
                    continue
                if 0 <= v <= len(choices):
                    output[v] += 1
        return output

    # I believe that verified is always a subset of all votes, but that's not enforced here
    total_votes = counter(chunk['votes'] if 'votes' in chunk else {})
    verified_votes = counter(chunk['userVotes'] if 'userVotes' in chunk else {})

    # Choices can link to route chapters, where the index of the choice in list 'choices' is a key in the
    #   'routes' dict and the dict value is the route id.
    # That route id is needed for the url to create the internal link from the choice to the route chapter.
    routes = chunk['routes'] if 'routes' in chunk else {}
    if choices and len(routes) > 0:
        altered_choices = []
        for i, choice in enumerate(choices):
            choice_index = str(i)
            if choice_index in routes.keys():
                route_chunkrange_url = "https://fiction.live/api/anonkun/route/{c_id}/chapters"
                route_url = route_chunkrange_url.format(c_id=routes[choice_index])
                choice_link = f"<a data-orighref='{route_url}' >{choice}</a>"
                altered_choices.append(choice_link)
            else:
                altered_choices.append(choice)
        choices = altered_choices

    return zip(choices, verified_votes, total_votes)

def format_choice(chunk):

    options = count_votes(chunk)

    # crossed-out writeins. authors can censor user-written choices, and (optionally) offer a reason.
    x_outs = [int(x) for x in chunk['xOut']] if 'xOut' in chunk else []
    x_reasons = chunk['xOutReasons'] if 'xOutReasons' in chunk else {}

    closed = "closed" if 'closed' in chunk else "open" # BUG: check on reopened votes

    num_voters = len(chunk['votes']) if 'votes' in chunk else 0

    vote_title = chunk['b'] if 'b' in chunk else "Choices"

    output = ""
    # start with the header
    output += f"<h4><span>{vote_title} — <small>Voting {closed}"
    output += f" — {num_voters}" + " voters</small></span></h4>\n"

    # we've got everything needed to build the html for our vote table.
    output += "<table class=\"voteblock\">\n"

    # filter out the crossed-out options, which display last
    for index, (choice_text, verified_votes, total_votes) in enumerate(options):
        if index in x_outs or total_votes < num_voters / 2:
            continue
        output += "<tr class=\"choiceitem\"><td>" + str(choice_text) + "</td><td class=\"votecount\">"
        if verified_votes > 0:
            output += f"★{str(verified_votes)}/"
        output += str(total_votes)+ " </td></tr>\n"

    output += "</table>\n"

    return output

def format_readerposts(chunk):

    closed = "Closed" if 'closed' in chunk else "Open"

    posts = chunk['votes'] if 'votes' in chunk else {}
    dice = chunk['dice'] if 'dice' in chunk else {}

    # now matches the site and does *not* include dicerolls as posts!
    num_votes = (
        f"{len(posts)} posts" if len(posts) != 0 else "be the first to post."
    )

    posts_title = chunk['b'] if 'b' in chunk else "Choices"

    output = ""
    output += f"<h4><span>{posts_title} — <small> Posting {closed}"
    output += f" — {num_votes}" + "</small></span></h4>\n"

    ## so. a voter can roll with their post. these rolls are in a seperate dict, but have the **same uid**.
    ## they're then formatted with the roll above the writein for that user.
    ## I *think* that formatting roll-only before writein-only posts is correct, but tbh, it's hard to tell.
    ## writeins are usually opened by the author for posts or rolls, not both at once.
    ## people tend to only mix the two by accident.
    if dice != {}:
        for uid, roll in dice.items():
            output += '<div class="choiceitem">'
            if roll: # optional. just because there's a list entry for it doesn't mean it has a value!
                output += f'<div class="dice">{str(roll)}' + '</div>\n'
            if uid in posts:
                if post := posts[uid]:
                    output += str(post)
                del posts[uid] # it's handled here with the roll instead of later
            output += '</div>'

    keepReaderPosts = False
    if keepReaderPosts:
        for post in posts.values():
            if post:
                output += f'<div class="choiceitem">{str(post)}' + '</div>\n'

    return output

def format_unknown(chunk):
    raise NotImplementedError(
        f"Unknown chunk type ({chunk}) in fiction.live story."
    )

def getChapterText(url):

    chunk_handler = {
        "choice"     : format_choice,
        "readerPost" : format_readerposts,
        "chapter"    : format_chapter
    }

    response = session.get(url)
    data = json.loads(response.text)

    if data == []:
        return ""
    # and *now* we can assume there's at least one chunk in the data -- chapters can be totally empty.

    # are we trying to read an appendix? check the first chunk to find out.
    getting_appendix = len(data) == 1 and 't' in data[0] and data[0]['t'].startswith("#special")

    text = ""

    for count, chunk in enumerate(data):

        # logger.debug(count) # pollutes the debug log, shows which chunk crashed the handler

        text += "<div>" # chapter chunks aren't always well-delimited in their contents

        # appendix chunks are mixed in with other things
        if not getting_appendix and 't' in chunk and chunk['t'].startswith("#special"): # t = title = bookmark
            continue

        handler = chunk_handler.get(chunk['nt'], format_unknown) # nt = node type
        text += handler(chunk)
        text += "</div><br />\n"

    ## soup to repair the most egregious HTML errors.
    return BeautifulSoup(text, "html.parser")

# Function to print messages with carriage return for loading effect
def print_loading(message):
    sys.stdout.write('\r' + message)
    sys.stdout.flush()

def get_book_content(chapters_list, appendices_list, routes_list, book):
    print("Downloading Chapters...")
    for count, chapter in enumerate(chapters_list):
        chapter['content'] = getChapterText(chapter['url'])
        if type(chapter['content']) == BeautifulSoup:
            chapter['content'] = chapter['content'].encode_contents()
        else:
            continue
        epub_chapter = epub.EpubHtml(title=chapter['title'], file_name=f"chap_{count+1}.xhtml", lang="en")  # Create the chapter
        epub_chapter.content = chapter['content']  # Set the chapter content
        book.add_item(epub_chapter)  # Add formatted chapter to the book
        book.toc += (epub.Link(f"chap_{count+1}.xhtml", chapter['title'], f"{chapter['title']}"),)  # Add the chapter to the table of contents
        print_loading(f"Chapter {count+1}/{len(chapters_list)} downloaded.")
    if appendices_list:
        print("\nDownloading Appendices...")
        for count, appendix in enumerate(appendices_list):
            appendix['content'] = getChapterText(appendix['url'])
            if type(appendix['content']) == BeautifulSoup:
                appendix['content'] = appendix['content'].encode_contents()
            else:
                continue
            epub_chapter = epub.EpubHtml(title=appendix['title'], file_name=f"appendix_{count+1}.xhtml", lang="en")  # Create the chapter
            epub_chapter.content = appendix['content']  # Set the appendix content
            book.add_item(epub_chapter)  # Add formatted appendix to the book
            book.toc += (epub.Link(f"appendix_{count+1}.xhtml", appendix['title'], f"{appendix['title']}"),)  # Add the appendix to the table of contents
            print_loading(f"Appendix {count+1}/{len(appendices_list)} downloaded.")
    if routes_list:
        print("\nDownloading Routes...")
        for count, route in enumerate(routes_list):
            route['content'] = getChapterText(route['url'])
            if type(route['content']) == BeautifulSoup:
                route['content'] = route['content'].encode_contents()
            else:
                continue
            epub_chapter = epub.EpubHtml(title=route['title'], file_name=f"route_{count+1}.xhtml", lang="en")  # Create the chapter
            epub_chapter.content = route['content']  # Set the route content
            book.add_item(epub_chapter)  # Add formatted route to the book
            book.toc += (epub.Link(f"route_{count+1}.xhtml", route['title'], f"{route['title']}"),)  # Add the route to the table of contents
            print_loading(f"Route {count+1}/{len(routes_list)} downloaded.")
    return book


# Function to create the EPUB file
def create_book(book_data, book_number, total_books):
    print(f"Creating book... {book_number}/{total_books}")
    book = epub.EpubBook() # Create the book

    # Set metadata properties
    book.set_title(book_data['t']) # Set the title
    book.add_author(book_data['u'][0]['n']) # Set the author
    book.add_item(epub.EpubNav()) # Add the navigation

    # Create the title page
    title_page = epub.EpubHtml(title="Title Page", file_name="title.xhtml", lang="en")

    chapters_list, appendices_list, routes_list = get_chapters_appendices_and_routes(book_data)

    # Set the title page content from book properties
    title_page_html = f"""<html xmlns="http://www.w3.org/1999/xhtml">
                            <head>
                                <title>{book_data["t"]} by {book_data['u'][0]['n']}</title>
                                <link href="stylesheet.css" type="text/css" rel="stylesheet" />
                            </head>
                            <body class="fff_titlepage">
                                <h3><a href="https://fiction.live/stories//{book_data["_id"]}">{book_data["t"]}</a> by <a class="authorlink"
                                        href="https://fiction.live/user/{book_data['u'][0]['n']}">{book_data['u'][0]['n']}</a></h3>
                                <div>
                                    <b>Status:</b> {book_data["storyStatus"]}<br />
                                    <b>Published:</b> {parse_timestamp(book_data["rt"])}<br />
                                    <b>Updated:</b> {parse_timestamp(book_data["cht"])}<br />
                                    <b>Packaged:</b> {datetime.now()}<br />
                                    <b>Rating:</b> {book_data["contentRating"]}<br />
                                    {f'<b>Chapters:</b> {len(chapters_list)}<br />' if chapters_list else ''}
                                    {f'<b>Appendices:</b> {len(appendices_list)}<br />' if appendices_list else ''}
                                    {f'<b>Routes:</b> {len(routes_list)}<br />' if routes_list else ''}
                                    <b>Words:</b> {book_data["w"]}<br />
                                    <b>Publisher:</b> fiction.live<br />
                                    {f'<b>Description:</b> {book_data["d"].strip()}<br />' if book_data.get('d') else ''}
                                    {f'<b>Synopsis:</b> {book_data["b"].strip()}<br />' if book_data.get('b') else ''}
                                    <b>Tags:</b> {", ".join(book_data["ta"])}<br />
                                    {f'<b>Spoiler Tags:</b> {", ".join(book_data["spoilerTags"])}<br />' if book_data["spoilerTags"] else ''}
                                </div>
                            </body>
                            </html>"""
    title_page.content = title_page_html.encode('utf-8') # Set the title page content
    book.add_item(title_page)
    book.toc += (epub.Link("title.xhtml", 'Title Page', "Title Page"),)  # Add the title page to the table of contents

    book = get_book_content(chapters_list, appendices_list, routes_list, book)

    book.spine = list(book.get_items()) # Set the spine to the list of chapters
    book.add_item(epub.EpubNcx()) # Add the table of contents

    return book

# The main function
def main():  # sourcery skip: hoist-statement-from-loop
    # Get the URL(s) of the Table of Contents or Chapter
    #story_urls = input("Enter Story URL(s): ")
    #story_urls = "https://fiction.live/stories/Shifting-The-Temporal-Tides/8J6NzhNiq7fE6XHnd" # Testing url 1
    story_urls = "https://fiction.live/stories/A-Hero-s-Journey/9jH3ggZgk9JdJWQWt" # Testing url 2
    story_urls = story_urls.split(" ") if " " in story_urls else [story_urls]
    # Check if the URL(s) is/are valid
    valid_urls = validate_urls(story_urls)

    # Get the directory where the EPUB file will be saved
    while True:
        #dir_path = input("Enter the directory where you want to save the EPUB file(s): ") # Get the directory path from the user
        dir_path = "C:\\Users\\caide\\Desktop\\Personal Projects\\Epub Editing\\Fiction.live\\API" # Test directory
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
    for count, book_urls in enumerate(valid_urls):
        book_data = get_book_info(book_urls['meta'])
        book = epub.EpubBook()
        if book_data is None:
            del book
            continue
        book = create_book(book_data, count+1, len(valid_urls))
        book.add_metadata('DC', 'url', book_urls['story'])
        save_book(book, dir_path)
        del book

# Run the main function if the script is run directly
if __name__ == "__main__":
     main()