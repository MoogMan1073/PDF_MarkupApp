# Python Libs
import PyPDF2
from PyPDF2 import PdfMerger, PdfWriter, PdfReader
import re
from tkinter import messagebox
# custom libs
from OS_Functions import *
import tkinter as tk
from tkinter import ttk



def MakePopup(root):
    popup = tk.Toplevel(root)
    popup.title("Loading...")
    popup.geometry("300x100")
    popup.iconbitmap("PDFLogo.ico")

    # Add a progress bar to the popup
    progress_bar = ttk.Progressbar(popup, orient="horizontal", length=250, mode="determinate")
    progress_bar.pack(pady=20)

    # Add a status label
    status_label = tk.Label(popup, text="Loading, please wait...")
    status_label.pack()
    return popup, progress_bar


def getPDFSetLength(PDFPath):

    pdf = PdfReader(PDFPath)
    return len(pdf.pages)


def split_pdf_into_pages(doc_file_path, output_dir, useSheetNum, root):
    try:

        popup, progress_bar = MakePopup(root)

        # This Regular expression
        # identifies the pattern of text
        # that includes the sheet number
        # TODO: this only going to work with sheets that have a max of 3 digits (which is most) \
        #   a check will need to added at some point to accomodate 4 digit drawing sets
        pattern = r"\d{3} \d{3}"
        lastPagePattern = r"\d{3}NTS"

        pattern4digit = r"\d{4} \d{4}"
        lastPagePattern4digit = r"\d{4}NTS"
        input_pdf = PdfReader(open(doc_file_path, "rb"))

        # force the type of the file name to be a string
        # incase python implicitly makes the file name a number or something
        file_name = str(extract_file_name(doc_file_path))

        progress_bar["value"] = 0.0  # Reset progress bar
        for i in range(len(input_pdf.pages)):
            progress = (i+1) / len(input_pdf.pages) * 100
            progress_bar["value"] = progress
            popup.update_idletasks()  # Update the GUI to reflect changes
            root.update()

            output = PdfWriter()
            output.add_page(input_pdf.pages[i])

            if useSheetNum:
                page_text = input_pdf.pages[i].extract_text()

                # Stop the action if not text is found
                if not page_text or page_text == '':
                    popup.destroy()
                    messagebox.showinfo("Input Error", "No text found in these PDF pages!" +
                                        "The input must be a searchable PDF to use the sheet number value."
                                        )
                    return
                # Identify any potential matches for the page number
                matches3digit = re.findall(pattern, page_text)
                matches4digit = re.findall(pattern, page_text)
                # The last page in a set does not follow the page number pattern.
                # so check one more time for the pattern seen in the last page
                if not matches3digit:
                    matches = re.findall(lastPagePattern, page_text)
                    if matches:
                        SheetNum = matches[0][:3]
                        max_digits = 3
                    else:
                        popup.destroy()
                        messagebox.showinfo("Code Error, Code: 3 Digit Check Code Failure")
                # TODO: 4 digit matching hasn't been tested
                elif not matches4digit:
                    matches = re.findall(lastPagePattern, page_text)
                    if matches:
                        SheetNum = matches[0][:4]
                        max_digits = 4
                    else:
                        popup.destroy()
                        messagebox.showinfo("Code Error, Code: 4 Digit Check Code Failure")

                if matches3digit:
                    max_digits = 3
                    SheetNums = matches3digit[-1].split(" ")

                elif matches4digit:
                    max_digits = 4
                    SheetNums = matches4digit[-1].split(" ")

                SheetNum = str(min(int(SheetNums[0]), int(SheetNums[1])))
                pageNumber = SheetNum
                prefix = "-sheet"

            else:
                max_digits = len(str(abs(len(input_pdf.pages))))
                pageNumber = str(i+1)
                pageNumber = pageNumber
                prefix = "-page"

            with open(output_dir + "\\" + file_name + prefix + "%s.pdf" % pageNumber.zfill(max_digits), "wb") as outputStream:
                output.write(outputStream)

        popup.destroy()
        messagebox.showinfo("Success", f"PDF split successfully at '{output_dir}'!")

    except Exception as e:
        messagebox.showerror("ERROR", f"An error occurred: {e}")


def combine_pdfs(input_directory, output_file, root):
    """
    Combines PDF files in a directory in order based on numbers in their filenames.

    :param input_directory: Directory containing the PDF files.
    :param output_file: Name of the output combined PDF file.
    """

    try:
        popup, progress_bar = MakePopup(root)
        # Get all PDF files in the input directory
        pdf_files = [f for f in os.listdir(input_directory) if f.endswith('.pdf')]

        # Extract numbers from filenames for sorting
        def extract_number(filename):
            match = re.search(r'\d+', filename)
            return int(match.group()) if match else float('inf')  # Place files without numbers at the end

        # Sort PDF files based on extracted numbers
        pdf_files.sort(key=extract_number)

        # Create a PdfMerger object
        pdf_merger = PdfMerger()

        # Merge PDFs
        i = 0
        for pdf_file in pdf_files:
            progress = (i + 1) / len(pdf_files) * 100
            progress_bar["value"] = progress
            popup.update_idletasks()  # Update the GUI to reflect changes
            root.update()
            i += 1
            pdf_path = os.path.join(input_directory, pdf_file)
            pdf_merger.append(pdf_path)

        # Write the combined PDF to the output file
        with open(output_file, 'wb') as output_pdf:
            pdf_merger.write(output_pdf)

        popup.destroy()
        messagebox.showinfo("Success", f"PDF saved successfully at '{output_file}'!")

    except Exception as e:
        messagebox.showerror("ERROR", f"An error occurred: {e}")


def insert_pdf_pages(target_pdf_path, insert_pdf_path, output_pdf_path, insert_index, root):

    writer = PdfWriter()

    # Append the whole target PDF first
    writer.append(target_pdf_path)

    # Insert the other PDF at the specified position
    # (position is 0-based: 0 = before first page, len(...) = append at end)
    writer.merge(insert_index, insert_pdf_path)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    '''
    try:
        popup, progress_bar = MakePopup(root)

        with open(target_pdf_path, "rb") as f_target, open(insert_pdf_path, "rb") as f_insert:
            target_pdf = PdfReader(f_target)
            insert_pdf = PdfReader(f_insert)

            if not (0 <= insert_index <= len(target_pdf.pages)):
                raise IndexError("Insert index is out of range.")

            writer = PdfWriter()

            progress_bar["value"] = 0
            popup.update_idletasks()
            root.update()

            # Before insertion
            for i in range(insert_index):
                writer.add_page(target_pdf.pages[i])

            progress_bar["value"] = 30
            popup.update_idletasks()
            root.update()

            # Inserted PDF
            for page in insert_pdf.pages:
                writer.add_page(page)

            progress_bar["value"] = 60
            popup.update_idletasks()
            root.update()

            # After insertion
            for i in range(insert_index, len(target_pdf.pages)):
                writer.add_page(target_pdf.pages[i])

            progress_bar["value"] = 100
            popup.update_idletasks()
            root.update()

            with open(output_pdf_path, "wb") as output_file:
                writer.write(output_file)

        popup.destroy()
        messagebox.showinfo("Success", f"PDF saved successfully at '{output_pdf_path}'!")
    except Exception as e:
        # For debugging, you might also want to log traceback.format_exc()
        messagebox.showerror("ERROR", f"An error occurred: {e}")
    '''

def swap_pdf_page(original_pdf_path, new_page_pdf_path, output_pdf_path, page_index, root):
    try:
        popup, progress_bar = MakePopup(root)
        # Read the original PDF
        original_pdf = PdfReader(original_pdf_path)
        # Read the new page from the single-page PDF
        new_page_pdf = PdfReader(new_page_pdf_path)

        # Check if the new page PDF has exactly one page
        if len(new_page_pdf.pages) != 1:
            raise ValueError("The new page PDF must contain exactly one page.")

        # Check if the page index is valid
        if page_index < 0 or page_index >= len(original_pdf.pages):
            raise IndexError("Page index is out of range for the original PDF.")

        # Create a PdfWriter object
        writer = PdfWriter()

        # Add all pages from the original PDF, replacing the target page
        for i, page in enumerate(original_pdf.pages):
            if i == page_index:
                # Replace the page at the specified index
                writer.add_page(new_page_pdf.pages[0])
            else:
                # Add the original page
                writer.add_page(page)

        # Write the output PDF to the specified path
        with open(output_pdf_path, "wb") as output_file:
            writer.write(output_file)

        popup.destroy()
        messagebox.showinfo("Success", f"PDF saved successfully at '{output_pdf_path}'!")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def remove_pages_from_pdf(input_pdf_path, output_pdf_path, pages_to_remove, root):
    try:
        popup, progress_bar = MakePopup(root)
        # Parse the pages to remove
        remove_set = set()
        for part in pages_to_remove.split(","):
            if "-" in part:  # Handle range
                start, end = map(int, part.split("-"))
                remove_set.update(range(start, end + 1))
            else:  # Handle single page
                remove_set.add(int(part))

        # Read the input PDF
        with open(input_pdf_path, "rb") as infile:
            reader = PyPDF2.PdfReader(infile)
            writer = PyPDF2.PdfWriter()

            # Iterate through all pages and add only those not in the remove_set
            for i, page in enumerate(reader.pages, start=1):
                progress = (i + 1) / len(reader.pages) * 100
                progress_bar["value"] = progress
                popup.update_idletasks()  # Update the GUI to reflect changes
                root.update()
                if i not in remove_set:
                    writer.add_page(page)

            # Write the output PDF
            with open(output_pdf_path, "wb") as outfile:
                writer.write(outfile)

        popup.destroy()
        return True

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        return False
