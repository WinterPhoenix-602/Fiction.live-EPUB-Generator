from ebooklib import epub
from pathlib import Path
from ReadEpub import fix_url_identifier

def find_epub_files(directory):
    epub_files = []
    # Convert the input to a Path object
    directory_path = Path(directory)
    
    # Iterate over all files and subdirectories in the given directory
    for item in directory_path.iterdir():
        # Skip directories with names ".calnotes" or ".caltrash"
        if item.is_dir() and item.name.lower() in (".calnotes", ".caltrash"):
            continue
        
        # Check if it's a directory
        if item.is_dir():
            # Recursively call the function for subdirectories
            epub_files.extend(find_epub_files(item))
        # Check if it's a file with a .epub extension
        elif item.is_file() and item.suffix.lower() == '.epub':
            epub_files.append(item)

    return epub_files

def main():
    # Get EPUB file path from user input
    if epub_paths := find_epub_files(r"C:\Users\caide\Calibre Library"):    
        for path in epub_paths:
            fix_url_identifier(path)
    else:
        print("No EPUB files found in the specified directory.")


if __name__ == "__main__":
    main()
