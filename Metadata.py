from ebooklib import epub
import os
import re

def read_epub_metadata(epub_file_path):
    try:
        # Read EPUB file
        book = epub.read_epub(epub_file_path)

        return {
            'Title': book.get_metadata('DC', 'title')[0][0]
            if book.get_metadata('DC', 'title')
            else 'N/A',
            'Author': ', '.join(
                author[0] for author in book.get_metadata('DC', 'creator')
            )
            if book.get_metadata('DC', 'creator')
            else 'N/A',
            'Language': book.get_metadata('DC', 'language')[0][0]
            if book.get_metadata('DC', 'language')
            else 'N/A',
            'Publisher': book.get_metadata('DC', 'publisher')[0][0]
            if book.get_metadata('DC', 'publisher')
            else 'N/A',
            'Description': book.get_metadata('DC', 'description')[0][0]
            if book.get_metadata('DC', 'description')
            else 'N/A',
            'Identifiers': [identifier[0] for identifier in book.get_metadata('DC', 'identifier')] if book.get_metadata('DC', 'identifier') else [],
        }
    except Exception as e:
        print(f"Error reading EPUB metadata: {e}")
        return None

def add_url_identifier(book, url, cleaned_description):
    book = epub.read_epub(book)

    if existing_identifiers := [
        identifier
        for identifier in book.get_metadata('DC', 'identifier')
        if 'opf:URL' in identifier[1].get('scheme', '')
        and identifier[1].get('scheme', '')
    ]:
        print("opf:URL identifier already exists.")
    else:
        # Add URL identifier
        book.add_metadata('DC', 'identifier', url, {'scheme': 'opf:URL'})
        book.set_unique_metadata('DC', 'description', cleaned_description)
        print(f"opf:URL Identifier added: {url}")

def extract_and_remove_url(description):
    if not (url_match := re.search(r'URL: (https?://\S+)', description)):
        return None, description
    url = url_match[1]
    cleaned_description = description.replace(url_match[0], '').strip()
    return url, cleaned_description

def main():
    # Get EPUB file path from user input
    user_directory = input("Enter the directory containing the EPUB file: ").strip('"')

    # Validate the directory
    if not os.path.exists(user_directory):
        print("Directory not found. Please provide a valid directory path.")
        return

    # List EPUB files in the directory
    epub_files = [file for file in os.listdir(user_directory) if file.lower().endswith('.epub')]

    if not epub_files:
        print("No EPUB files found in the specified directory.")
        return

    # Display EPUB files in the directory
    print("\nEPUB files in the directory:")
    for i, epub_file in enumerate(epub_files, start=1):
        print(f"{i}. {epub_file}")

    # Get user choice
    user_choice = int(input("\nEnter the number of the EPUB file you want to analyze: ")) - 1

    if 0 <= user_choice < len(epub_files):
        selected_epub_file = os.path.join(user_directory, epub_files[user_choice]).strip('"')
        if metadata := read_epub_metadata(selected_epub_file):
            print("\nEPUB Metadata:")
            for key, value in metadata.items():
                print(f"{key}: {value}")

            # Extract URL from the description and remove it
            url, cleaned_description = extract_and_remove_url(metadata['Description'])

            # Add URL Identifier to the EPUB metadata
            if url:
                add_url_identifier(selected_epub_file, url, cleaned_description)
            else:
                print("No URL found in the description.")
        else:
            print("Failed to read EPUB metadata.")
    else:
        print("Invalid choice. Please enter a valid number.")

if __name__ == "__main__":
    main()
