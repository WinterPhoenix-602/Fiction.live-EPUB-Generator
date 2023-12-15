import requests
from bs4 import BeautifulSoup
import itertools
import simpleaudio as sa
import sys
import logging
from six import text_type as unicode
logger = logging.getLogger(__name__)
import json
from ebooklib import epub
from exceptions import *
import string
from datetime import datetime
import os
import re
from colorama import Fore, Style

session = requests.Session()
achievements = []
ALERT_SOUND_PATH = r"Sound\alert.wav"
SUCCESS_SOUND_PATH = r"Sound\success.wav"

def play_sound(sound_file):
    """
    Plays a sound file.

    Args:
        sound_file (str): The path to the sound file.

    Returns:
        None
    """
    wave_obj = sa.WaveObject.from_wave_file(sound_file)
    play_obj = wave_obj.play()
    play_obj.wait_done()  # Wait for sound to finish playing

# Function to process URL(s)
def process_urls(urls):
    """
    Validates a list of URLs and returns the valid ones along with their corresponding metadata URLs.

    Args:
        urls (list): A list of URLs to be validated.

    Returns:
        list: A list of dictionaries, where each dictionary contains the valid story URL and its corresponding metadata URL.

    Examples:
        >>> urls = ["https://fiction.live/stories/1234567890abcdef", "https://fiction.live/stories/abcdefg/1234567890abcdef"]
        >>> validate_urls(urls)
        [{'story': 'https://fiction.live/stories//1234567890abcdef', 'meta': 'https://fiction.live/api/node/1234567890abcdef'}, ...]
    """
    # Regular expression pattern to match valid URLs
    pattern = r"^https://fiction.live/stories/([-A-Za-z0-9]+)?/([A-Za-z0-9]{17})(/[-A-Za-z0-9]+/[A-Za-z0-9]+)?"

    valid_urls = []
    invalid_urls = []

    # Loop through each URL and check if it is valid
    for url in urls:
        if re.match(pattern, url): # If it is valid, ensure proper formatting and then append
            valid_urls.append(
                {
                    'story': f"https://fiction.live/stories//{re.match(pattern, url)[2]}",
                    'meta': f"https://fiction.live/api/node/{re.match(pattern, url)[2]}"
                }
            )
        else: # If it is invalid, append to invalid urls and display
            invalid_urls.append(url)
            play_sound(ALERT_SOUND_PATH)
            print(f"{Fore.RED}Invalid URL: {url}{Style.RESET_ALL}")

    # If there are no valid URLs, display a message and exit the program
    if not valid_urls:
        play_sound(ALERT_SOUND_PATH)
        print(f"{Fore.RED}No valid URLs found.{Style.RESET_ALL}")
        exit()

    return valid_urls

def get_book_info(metadata_url):
    """
    Retrieves the metadata of a story from the provided URL.

    Args:
        metadata_url (str): The URL of the story metadata.

    Returns:
        dict: The story metadata as a dictionary.

    Examples:
        >>> metadata_url = "https://fiction.live/api/anonkun/story/12345/metadata"
        >>> get_book_info(metadata_url)
        {'title': 'Story Title', 'author': 'Author Name', ...}
    """

    if story_metadata := session.get(metadata_url).text:
        if story_metadata != "null" and "Cannot GET" not in story_metadata:
            story_metadata = json.loads(story_metadata)
            # gonna need these later for adding details to achievement-granting links in the text
            try:
                achievements = story_metadata['achievements']['achievements']
            except KeyError:
                achievements = []
            return story_metadata
    play_sound(ALERT_SOUND_PATH)
    print(f"{Fore.RED}Error fetching story data at: ({metadata_url}){Style.RESET_ALL}")
    return None

def get_book_map(book_data):
    """
    Retrieves the chapters, appendices, and routes from the provided book data.

    Args:
        book_data (dict): The book data containing chapters, appendices, and route metadata.

    Returns:
        tuple: A tuple containing three lists: chapters_list, appendices_list, and routes_list.

    Examples:
        >>> book_data = {'bm': [...], 'route_metadata': [...], ...}
        >>> get_chapters_appendices_and_routes(book_data)
        ([{'title': 'Chapter 1', 'url': 'https://fiction.live/api/anonkun/chapters/...'}, ...], [...], [...])
    """
    chapters_list = []
    appendices_list = []
    routes_list = []
    def add_chapter_url(title, bounds, isAppendix = False):
        """
        Adds a chapter URL based on the start and end chunk-range timestamps.

        Args:
            title (str): The title of the chapter.
            bounds (tuple): A tuple containing the start and end chunk-range timestamps.
            isAppendix (bool, optional): Indicates whether the chapter is an appendix. Defaults to False.

        Returns:
            None
        """
        start, end = bounds
        end -= 1
        chapter_url = f"https://fiction.live/api/anonkun/chapters/{book_data['_id']}/{start}/{end}/"
        if isAppendix:
            appendices_list.append({'title': title, 'url': chapter_url})
            return
        chapters_list.append({'title': title, 'url': chapter_url})

    def add_route_chapter_url(title, route_id):
        """
        Adds a route chapter URL based on the provided route ID.

        Args:
            title (str): The title of the route chapter.
            route_id (str): The ID of the route.

        Returns:
            None
        """
        chapter_url = f"https://fiction.live/api/anonkun/route/{route_id}/chapters"
        routes_list.append({'title': title, 'url': chapter_url})

    def pair(iterable):
        """
        Pairs the elements of the provided iterable into consecutive tuples.

        Args:
            iterable (iterable): The iterable to be paired.

        Returns:
            list: A list of tuples, where each tuple contains two consecutive elements from the iterable.

        Examples:
            >>> iterable = [1, 2, 3, 4]
            >>> pair(iterable)
            [(1, 2), (2, 3), (3, 4)]
        """
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
    """
    Creates a BeautifulSoup object from the provided HTML data.

    Args:
        data (str): The HTML data to be parsed.

    Returns:
        BeautifulSoup: The BeautifulSoup object representing the parsed HTML.

    Examples:
        >>> data = "<p>HTML content</p>"
        >>> make_soup(data)
        <BeautifulSoup object at 0x...>
    """

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
    """
    Formats the chapter body text in the provided chunk.
    In the 'default case' where we're getting boring chapter-chunk body text, just calls utf8fromSoup
    and returns the text as is on the website

    Args:
        chunk (dict): The chunk containing the chapter body text.

    Returns:
        str: The formatted chapter body text.

    Examples:
        >>> chunk = {'b': "<p>Chapter content</p>", ...}
        >>> format_chapter(chunk)
        "<p>Chapter content</p>"
    """

    soup = make_soup(chunk['b'] if 'b' in chunk else "")
    soup = add_spoiler_legends(soup)
    soup = append_achievments(soup)

    return str(soup)

def add_spoiler_legends(soup):
    """
    Adds spoiler legends to the provided BeautifulSoup object.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object to modify.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with spoiler legends added.

    Examples:
        >>> soup = BeautifulSoup("<div><p>Content</p></div>", "html.parser")
        >>> add_spoiler_legends(soup)
        <BeautifulSoup object at 0x...>
    """
    spoilers = soup.find_all('a', class_="tydai-spoiler")
    for link_tag in spoilers:
        link_tag.name = 'fieldset'
        legend = soup.new_tag('legend')
        legend.string = "Spoiler"
        link_tag.insert(0, legend)
    return soup

def fictionlive_normalize(string):
    """
    Normalizes the given string for use in Fiction.live URLs.

    Args:
        string (str): The string to be normalized.

    Returns:
        str: The normalized string.

    Examples:
        >>> string = "Some Example String"
        >>> fictionlive_normalize(string)
        "some-example-string"
    """
    # might be able to use this to preserve titles in normalized urls, if the scheme is the same

    # BUG: in achivement ids these are all replaced, but I *don't* know that the list is complete.
    # should be rare, thankfully. *most* authors don't use any funny characters in the achievment's *ID*
    special_chars = "\"\\,.!?+=/[](){}<>_'@#$%^&*~`;:|" # not the hyphen, which is used to represent spaces

    return string.lower().replace(" ", "-").translate({ord(x) : None for x in special_chars})

def append_achievments(soup):
    """
    Appends achievements to the provided BeautifulSoup object.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object to modify.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with achievements appended.

    Examples:
        >>> soup = BeautifulSoup("<div><p>Content</p></div>", "html.parser")
        >>> append_achievments(soup)
        <BeautifulSoup object at 0x...>
    """
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
    """
    Counts the votes for each choice option in the provided chunk.

    Args:
        chunk (dict): The chunk containing the votes and choices.

    Returns:
        tuple: A tuple containing lists of choice options, verified votes, and total votes.

    Examples:
        >>> chunk = {'votes': {'uid1': [0, 1], 'uid2': 2}, 'choices': ['Choice 1', 'Choice 2'], ...}
        >>> count_votes(chunk)
        (["Choice 1", "Choice 2"], [0, 1], [0, 1])
    """
    # optional.
    choices = chunk['choices'] if 'choices' in chunk else []

    def counter(votes):
        """
        Counts the votes for each choice option.

        Args:
            votes (dict): A dictionary containing the votes, where the keys are voter IDs and the values are the chosen option(s).

        Returns:
            list: A list containing the count of votes for each choice option.

        Examples:
            >>> votes = {'uid1': [0, 1], 'uid2': 2, ...}
            >>> counter(votes)
            [1, 1, 1, 0, ...]
        """
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

    return (choices, verified_votes, total_votes)

def format_choice(chunk):
    """
    Formats the choice options and vote counts from the provided chunk.

    Args:
        chunk (dict): The chunk containing choice options and vote counts.

    Returns:
        str: The formatted HTML output of the choice options and vote counts.

    Examples:
        >>> chunk = {'votes': {'uid1': 'Vote 1', 'uid2': 'Vote 2'}, 'xOut': [1, 3], ...}
        >>> format_choice(chunk)
        "<h4><span>Choices — <small>Voting open — 2 voters</small></span></h4>\n<table class='voteblock'>...</table>"
    """

    options = count_votes(chunk)

    # crossed-out writeins. authors can censor user-written choices, and (optionally) offer a reason.
    x_outs = [int(x) for x in chunk['xOut']] if 'xOut' in chunk else []
    x_reasons = chunk['xOutReasons'] if 'xOutReasons' in chunk else {}

    closed = "closed" if 'closed' in chunk else "open" # BUG: check on reopened votes

    num_voters = len(chunk['votes']) if 'votes' in chunk else 0

    # Find the winner and tied options
    max_votes = 0
    for index, total_votes in enumerate(options[2]):
        if not options[0][index].startswith("+") and total_votes > max_votes:
            max_votes = total_votes
    winning_options = [
        (options[0][index], options[1][index], options[2][index])
        for index, total_votes in enumerate(options[2])
        if total_votes >= max_votes / 2 or total_votes >= max_votes
    ]
    # Sort the winning options by total votes and then by option text
    if len(winning_options) > 1:
        winning_options.sort(key=lambda x: (not x[0].startswith('+'), x[2], x[1]), reverse=True)

    vote_title = chunk['b'] if 'b' in chunk else "Choices"

    output = ""
    # start with the header
    output += f"<h4><span>{vote_title} — <small>Voting {closed}"
    output += f" — {num_voters}" + " voters</small></span></h4>\n"

    # we've got everything needed to build the html for our vote table.
    output += "<table class=\"voteblock\">\n"

    # Generate HTML for the winning options
    for choice_text, verified_votes, total_votes in winning_options:
        output += "<tr class=\"choiceitem\"><td>" + str(choice_text) + "</td><td class=\"votecount\">"
        if verified_votes > 0:
            output += f"★{str(verified_votes)}/"
        output += str(total_votes) + " </td></tr>\n"


    output += "</table>\n"

    return output

def format_readerposts(chunk):
    """
    Formats the reader posts and dice rolls from the provided chunk.

    Args:
        chunk (dict): The chunk containing reader posts and dice rolls.

    Returns:
        str: The formatted HTML output of the reader posts and dice rolls.

    Examples:
        >>> chunk = {'votes': {'uid1': 'Post 1', 'uid2': 'Post 2'}, 'dice': {'uid1': 'Roll 1', 'uid2': 'Roll 2'}, ...}
        >>> format_readerposts(chunk)
        "<h4><span>Choices — <small> Posting Open — 2 posts</small></span></h4>\n<div class='choiceitem'>...</div>"
    """

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
    keepReaderPosts = False
    if dice == {} and not keepReaderPosts:
        return ''
    
    for uid, roll in dice.items():
        output += '<div class="choiceitem">'
        if roll: # optional. just because there's a list entry for it doesn't mean it has a value!
            output += f'<div class="dice">{str(roll)}' + '</div>\n'
        if uid in posts and keepReaderPosts:
            if post := posts[uid]:
                output += str(post)
            del posts[uid] # it's handled here with the roll instead of later
        output += '</div>'

    if keepReaderPosts:
        for post in posts.values():
            if post:
                output += f'<div class="choiceitem">{str(post)}' + '</div>\n'

    return output

def format_unknown(chunk):
    play_sound(ALERT_SOUND_PATH)
    raise NotImplementedError(
        f"Unknown chunk type ({chunk}) in fiction.live story."
    )

def getChapterText(url):
    """
    Retrieves the text content of a chapter from the provided URL.

    Args:
        url (str): The URL of the chapter.

    Returns:
        BeautifulSoup: A BeautifulSoup object containing the parsed HTML content of the chapter.

    Examples:
        >>> url = "https://fiction.live/chapter1"
        >>> getChapterText(url)
        <BeautifulSoup object at 0x...>
    """
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
        text += "</div>\n"

    ## soup to repair the most egregious HTML errors.
    return BeautifulSoup(text, "html.parser")

# Function to print messages with carriage return for loading effect
def print_loading(message):
    """
    Prints a loading message to the standard output.

    Args:
        message (str): The loading message to be printed.

    Returns:
        None
    """
    sys.stdout.write('\r' + message)
    sys.stdout.flush()

def remove_empty_tags(soup):
    """
    Removes empty tags from the provided BeautifulSoup object.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object to modify.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object.

    Examples:
        >>> soup = BeautifulSoup("<div><p>Soup.</p><span></span></div>", "html.parser")
        >>> remove_empty_tags(soup)
        <div><p>Soup.</p></div>
    """
    # Find all tags in the BeautifulSoup object
    if not (all_tags := soup.find_all()):
        return ""
        
    # Loop through all tags
    for tag in all_tags:
        # Check if the tag is empty (no content)
        if not tag.contents and not tag.text.strip() and tag.name != 'img' and tag.name != 'br':
            # Remove the empty tag
            tag.decompose()

    # Return the modified BeautifulSoup object
    return soup if soup.find_all() else ""

def img_url_trans(imgurl):
    """
    Transforms the image URL to the new CDN URL format.

    Args:
        imgurl (str): The original image URL.

    Returns:
        str: The transformed image URL.

    Examples:
        >>> img_url_trans("https://example.com/image.jpg")
        "https://cdn6.fiction.live/file/fictionlive/image.jpg"
    """
    # logger.debug("pre--imgurl:%s"%imgurl)
    imgurl = re.sub(r'(\w+)\.cloudfront\.net',r'cdn6.fiction.live/file/fictionlive',imgurl)
    imgurl = re.sub(r'www\.filepicker\.io/api/file/(\w+)',r'cdn4.fiction.live/fp/\1',imgurl)
    imgurl = re.sub(r'cdn[34].fiction.live/(.+)',r'cdn6.fiction.live/file/fictionlive/\1',imgurl)
    # logger.debug("post-imgurl:%s"%imgurl)
    return imgurl

def format_images(img_elements):
    """
    Formats the image elements in the provided list.

    Args:
        img_elements (list): A list of BeautifulSoup image elements.

    Returns:
        None

    Examples:
        >>> img_elements = [img_element1, img_element2, ...]
        >>> format_images(img_elements)
    """
    for img in img_elements:
        try:
            # some pre-existing epubs have img tags that had src stripped off.
            if img.has_attr('src'):
                img['src'] = img_url_trans(img['src'])
        except AttributeError as ae:
            logger.info(
                f"Parsing for img tags failed--probably poor input HTML.  Skipping img({img})"
            )

def get_book_content(chapters_list, appendices_list, routes_list, book):
    """
    Downloads and adds chapters, appendices, and routes to the provided EPUB book.

    Args:
        chapters_list (list): A list of dictionaries containing chapter information, including title and URL.
        appendices_list (list): A list of dictionaries containing appendix information, including title and URL.
        routes_list (list): A list of dictionaries containing route information, including title and URL.
        book (epub.EpubBook): The EPUB book to which the content will be added.

    Returns:
        epub.EpubBook: The EPUB book with the added content.

    Examples:
        >>> chapters_list = [{'title': 'Chapter 1', 'url': 'https://fiction.live/chapter1'}, ...]
        >>> appendices_list = [{'title': 'Appendix A', 'url': 'https://fiction.live/appendixA'}, ...]
        >>> routes_list = [{'title': 'Route X', 'url': 'https://fiction.live/routeX'}, ...]
        >>> book = epub.EpubBook()
        >>> get_book_content(chapters_list, appendices_list, routes_list, book)
        <epub.EpubBook object at 0x...>
    """
    print("Downloading Chapters...")
    for count, chapter in enumerate(chapters_list):
        chapter['content'] = getChapterText(chapter['url'])
        if type(chapter['content']) != BeautifulSoup:
            continue
        remove_empty_tags(chapter['content'])
        if img_elements := chapter['content'].find_all('img'):
            format_images(img_elements)
        chapter['content'] = chapter['content'].encode_contents()
        epub_chapter = epub.EpubHtml(title=chapter['title'], file_name=f"chap_{count+1}.xhtml", lang="en")  # Create the chapter
        epub_chapter.content = chapter['content']  # Set the chapter content
        book.add_item(epub_chapter)  # Add formatted chapter to the book
        book.toc += (epub.Link(f"chap_{count+1}.xhtml", chapter['title'], f"{chapter['title']}"),)  # Add the chapter to the table of contents
        print_loading(f"Chapter {count+1}/{len(chapters_list)} downloaded.")
    if appendices_list:
        print("\nDownloading Appendices...")
        for count, appendix in enumerate(appendices_list):
            appendix['content'] = getChapterText(appendix['url'])
            appendix['content'] = remove_empty_tags(appendix['content'])
            if type(appendix['content']) != BeautifulSoup:
                continue
            appendix['content'] = appendix['content'].encode_contents()
            epub_chapter = epub.EpubHtml(title=appendix['title'], file_name=f"appendix_{count+1}.xhtml", lang="en")  # Create the chapter
            epub_chapter.content = appendix['content']  # Set the appendix content
            book.add_item(epub_chapter)  # Add formatted appendix to the book
            book.toc += (epub.Link(f"appendix_{count+1}.xhtml", appendix['title'], f"{appendix['title']}"),)  # Add the appendix to the table of contents
            print_loading(f"Appendix {count+1}/{len(appendices_list)} downloaded.")
    if routes_list:
        print("\nDownloading Routes...")
        for count, route in enumerate(routes_list):
            route['content'] = getChapterText(route['url'])
            if type(route['content']) != BeautifulSoup:
                continue
            remove_empty_tags(route['content'])
            route['content'] = route['content'].encode_contents()
            epub_chapter = epub.EpubHtml(title=route['title'], file_name=f"route_{count+1}.xhtml", lang="en")  # Create the chapter
            epub_chapter.content = route['content']  # Set the route content
            book.add_item(epub_chapter)  # Add formatted route to the book
            book.toc += (epub.Link(f"route_{count+1}.xhtml", route['title'], f"{route['title']}"),)  # Add the route to the table of contents
            print_loading(f"Route {count+1}/{len(routes_list)} downloaded.")
    return book

# Function to create the EPUB file
def create_book(book_data, book_number, total_books):
    """
    Creates an EPUB book based on the provided book data.

    Args:
        book_data (dict): A dictionary containing the book data, including title, author, chapters, appendices, routes, and other metadata.
        book_number (int): The number of the book being created.
        total_books (int): The total number of books to be created.

    Returns:
        epub.EpubBook: The created EPUB book.

    Examples:
        >>> book_data = {'t': 'Test Book', 'u': [{'n': 'John Doe'}], ...}
        >>> book_number = 1
        >>> total_books = 2
        >>> create_book(book_data, book_number, total_books)
        <epub.EpubBook object at 0x...>
    """
    print(f'Creating book {book_number}/{total_books} "{book_data["t"]}".')
    book = epub.EpubBook() # Create the book

    # Set metadata properties
    book.set_title(book_data['t']) # Set the title
    book.add_author(book_data['u'][0]['n']) # Set the author
    book.add_metadata('DC', 'date', f'{parse_timestamp(book_data["rt"])}') # Set the publish date
    description = f''
    if book_data.get('b') and book_data.get('d'):
        description += book_data["b"].strip() + '\n' + book_data["d"].strip()
    elif book_data.get('b') or book_data.get('d'):
        description += book_data.get('b', '').strip() + book_data.get('d', '').strip()
    else:
        description = 'Description not found.'
    book.add_metadata('DC', 'description', description) # Set the description
    book.add_metadata('DC', 'publisher', 'fiction.live') # Set the publisher
    book.add_metadata('DC', 'identifier', f'url:https://fiction.live/stories//{book_data["_id"]}') # Add URL identifier
    book.add_metadata('DC', 'subject', 'Web Scraped') # Add Web Scraped tag
    includeSpoilerTags = False
    if book_data.get("spoilerTags", []):
        book_data["ta"] = [tag for tag in book_data.get("ta", []) if tag not in book_data.get("spoilerTags", [])]
        if includeSpoilerTags:
            for spoiler_tag in book_data["spoilerTags"]:
                book.add_metadata('DC', 'subject', spoiler_tag) # Add spoiler tags
    for tag in book_data["ta"]:
        book.add_metadata('DC', 'subject', tag) # Add tags
    

    # Create the title page
    title_page = epub.EpubHtml(title="Title Page", file_name="title.xhtml", lang="en")

    chapters_list, appendices_list, routes_list = get_book_map(book_data)

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
                                    {f'<b>Spoiler Tags:</b> {", ".join(book_data["spoilerTags"])}<br />' if book_data.get("spoilerTags") and includeSpoilerTags else ''}
                                </div>
                            </body>
                            </html>"""
    title_page.content = title_page_html.encode('utf-8') # Set the title page content
    book.add_item(title_page)
    book.add_item(epub.EpubNav()) # Add the navigation
    book.toc += (epub.Link("title.xhtml", 'Title Page', "Title Page"),)  # Add the title page to the table of contents

    book = get_book_content(chapters_list, appendices_list, routes_list, book)

    book.spine = list(book.get_items()) # Set the spine to the list of chapters
    book.add_item(epub.EpubNcx()) # Add the table of contents

    return book

def get_valid_directory():
    while True:
        dir_path = input("Enter the directory where you want to save the EPUB file(s): ")

        if dir_path.lower() == 'def':
            dir_path = r"C:\Users\caide\Desktop\Personal Projects\Epub Editing\Fiction.live\API"

        if '"' in dir_path:
            dir_path = dir_path.strip('"')

        dir_path = os.path.normpath(dir_path)

        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            break

        play_sound(ALERT_SOUND_PATH)
        print(f"{Fore.RED}Invalid directory. Please enter a valid directory.{Style.RESET_ALL}")
    return dir_path

# Save the EPUB file
def save_book(book, dir_path):
    # Check if the directory already contains a file with the same name
    book_title = book.title
    epub_path = os.path.join(dir_path, f"{book_title.replace(' ', '_')}.epub")

    # Check if the book title contains invalid characters
    epub_path = validate_filename(book, dir_path, epub_path, book_title)

    # Write the EPUB file to the specified directory
    print("\nWriting EPUB file...")
    with open(epub_path, 'wb') as epub_file:
        epub.write_epub(epub_file, book)
    play_sound(SUCCESS_SOUND_PATH)
    print(f"EPUB file written to {Fore.GREEN}{epub_path}{Style.RESET_ALL}\n")

def validate_filename(book, dir_path, epub_path, book_title):
    invalid_chars = set(string.punctuation.replace('_', ''))
    if any(char in invalid_chars for char in book_title):
        print(f"\n{Fore.YELLOW}The book title contains invalid characters. Invalid characters will be replaced with '-'{Style.RESET_ALL}\r")
        new_title = "".join(["-" if char in invalid_chars else char for char in book_title])
        epub_path = os.path.join(dir_path, f"{new_title.replace(' ', '_')}.epub")
        book.set_title(new_title)
    while os.path.isfile(epub_path):
        play_sound(ALERT_SOUND_PATH)
        response = input("\nAn EPUB file with this name already exists in the directory. Do you want to overwrite it? (y/n) ")
        if response.lower() == "y":
            os.remove(epub_path)
            break
        elif response.lower() == "n":
            # Get a new name for the EPUB file
            book_title = input("Enter a new name for the EPUB file: ").replace(' ', '_')
            epub_path = os.path.join(dir_path, f"{book_title}.epub")
        else:
            play_sound(ALERT_SOUND_PATH)
            print(f"{Fore.YELLOW}Invalid response. Please enter 'y' or 'n'.")
    return epub_path

# The main function
def main():  # sourcery skip: hoist-statement-from-loop
    r"""
    Main function for creating EPUB files from story URLs.

    Gets the URL(s) of the Table of Contents or Chapter from user input.
    Splits the URL(s) into a list if multiple URLs are provided.
    Validates the URL(s) to ensure they are valid.
    Gets the directory where the EPUB file(s) will be saved from user input.
    Loops through the URLs and creates an EPUB file for each one.

    Args:
        None

    Returns:
        None

    Raises:
        ValueError: If the directory path is invalid.

    Examples:
        main()
        Enter Story URL(s): https://fiction.live/stories/story-1/12345678912345678
        Enter the directory where you want to save the EPUB file(s): C:\\Users\\username\\Desktop\\Folder
        Creating book... 1/1
        Downloading Chapters...
        Chapter 26/26 downloaded.
        Downloading Appendices...
        Appendix 5/5 downloaded.
        The book title contains invalid characters. Invalid characters will be replaced with '-'
        Writing EPUB file...
        EPUB file written to C:\Users\username\Desktop\Folder\story-1.epub"""
    # Get the URL(s) of the Table of Contents or Chapter
    story_urls = input("Enter Story URL(s): ")
    #story_urls = "https://fiction.live/stories/Broodhive/irT23yRJJF4N2H5hr/home" # Testing url 1
    #story_urls = "https://fiction.live/stories/A-Hero-s-Journey/9jH3ggZgk9JdJWQWt" # Testing url 2
    story_urls = story_urls.split(" ") if " " in story_urls else [story_urls]
    # Check if the URL(s) is/are valid
    valid_urls = process_urls(story_urls)

    # Get the directory where the EPUB file will be saved
    dir_path = get_valid_directory()

    # Loop through the URLs and create an EPUB file for each one
    for count, book_urls in enumerate(valid_urls):
        book_data = get_book_info(book_urls['meta'])
        book = epub.EpubBook()
        if book_data is None:
            del book
            continue
        book = create_book(book_data, count+1, len(valid_urls))
        save_book(book, dir_path)
        del book

# Run the main function if the script is run directly
if __name__ == "__main__":
    main()
