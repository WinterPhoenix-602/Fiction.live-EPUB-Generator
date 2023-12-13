from zipfile import ZipFile, ZIP_DEFLATED
import os
import re
import shutil

def extract_epub(epub_path, extract_folder):
    with ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(extract_folder)

def create_epub(folder, new_epub_path):
    with ZipFile(new_epub_path, 'w', compression=ZIP_DEFLATED, compresslevel=8) as zip_ref:
        for root, dirs, files in os.walk(folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder)
                zip_ref.write(file_path, arcname)

def get_temp_folder(original_epub_path):
    return os.path.join(
        os.path.dirname(original_epub_path), 'temp_extracted_folder'
    )

def correct_identifiers(temp_folder_path):
    opf_file_path = os.path.join(temp_folder_path, 'EPUB', 'content.opf')

    # Check if opf_file_path is a file
    if not os.path.isfile(opf_file_path):
        print(f"The path '{opf_file_path}' does not point to a valid file.")
        return False
    
    # Open the OPF file and read its content
    with open(opf_file_path, 'r', encoding='utf-8') as opf_file:
        content = opf_file.read()

    # Define the search pattern for identifiers
    pattern = re.compile(r'<dc:identifier scheme="opf:URL">(.*?)</dc:identifier>', re.DOTALL)

    # Replace the identifiers in the content
    modified_content = re.sub(pattern, r'<dc:identifier opf:scheme="URL">\1</dc:identifier>', content)

    if content == modified_content:
        print(f"No incorrect url tags in {opf_file_path}.")
        return False

    # Write the modified content back to the OPF file
    with open(opf_file_path, 'w', encoding='utf-8') as opf_file:
        opf_file.write(modified_content)
    return True

def fix_url_identifier(epub_path):
    temp_folder_path = get_temp_folder(epub_path)

    # Extract files from the original EPUB
    extract_epub(epub_path, temp_folder_path)

    # Check opf file for incorrect identifiers

    # Create a new EPUB from the new folder after checking opf file for incorrect identifiers
    if save_epub := correct_identifiers(temp_folder_path):
        create_epub(temp_folder_path, epub_path)
        print('EPUB URL tag extraction and replacement completed successfully!')

    # Remove the temporary folder
    shutil.rmtree(temp_folder_path)

def testing():
    pass

if __name__ == "__main__":
    testing()
