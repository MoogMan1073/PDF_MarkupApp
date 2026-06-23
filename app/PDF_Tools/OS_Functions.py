import os


def extract_file_name(file_path):
    """
    Extracts the file name without extension from a given file path.

    :param file_path: The file path as a string.
    :return: The file name without the extension.
    """
    base_name = os.path.basename(file_path)  # Extract the file name with extension
    file_name, _ = os.path.splitext(base_name)  # Split the file name and extension
    return file_name
