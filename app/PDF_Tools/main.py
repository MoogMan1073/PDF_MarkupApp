# Python Libraries
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinterdnd2 import DND_FILES, TkinterDnD
from PyInstaller.utils.hooks import collect_data_files
from pdf2docx import Converter
from pdf2image import convert_from_path
from PIL import Image, ImageTk
from screeninfo import get_monitors
# Custom Functions
from PDF_Manipulator import *


datas = collect_data_files('tkinterdnd2')

def create_gui():

    # region Tab 1 (Split) functions
    def SplitPDFTab(tab):
        # PDF File Selection
        notebook.add(tab, text="PDF Page Splitter")

        ttk.Label(tab, text="PDF File:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        pdf_file_entry.grid(row=0, column=1, padx=10, pady=10)
        pdf_file_entry.drop_target_register(DND_FILES)
        pdf_file_entry.dnd_bind('<<Drop>>', lambda event, tf=pdf_file_entry, isPDF = True: drop(event, tf,isPDF))
        ttk.Button(tab, text="Browse", command=select_pdf_file).grid(row=0, column=2, padx=10, pady=10)

        # Output Directory Selection
        ttk.Label(tab, text="Output Directory:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        output_dir_entry.grid(row=1, column=1, padx=10, pady=10)
        output_dir_entry.drop_target_register(DND_FILES)
        output_dir_entry.dnd_bind('<<Drop>>', lambda event, tf=output_dir_entry, isPDF = False: drop(event, tf, isPDF))
        ttk.Button(tab, text="Browse", command=select_output_directory).grid(row=1, column=2, padx=10, pady=10)



        radio_true.grid(row=2, column=0, padx=10, pady=10)
        radio_false.grid(row=2, column=1, padx=10, pady=10)
        # Split Button
        ttk.Button(tab, text="Split PDF", command=perform_split).grid(row=2, column=2, pady=20)

    def select_pdf_file():
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            pdf_file_entry.delete(0, tk.END)
            pdf_file_entry.insert(0, file_path)

    def select_output_directory():
        directory = filedialog.askdirectory()
        if directory:
            output_dir_entry.delete(0, tk.END)
            output_dir_entry.insert(0, directory)

    def perform_split():
        pdf_file_path = pdf_file_entry.get()
        output_dir = output_dir_entry.get()

        if not pdf_file_path or not output_dir:
            messagebox.showerror("Error", "Both PDF file and output directory must be specified.")
            return

        split_pdf_into_pages(pdf_file_path, output_dir, useSheetNum.get(), root)
# endregion

    # region Tab 2 (Combine) Functions
    def CombinePDFTab(tab):

        notebook.add(tab, text="PDF Page Combiner")

        # Input Directory Selection
        ttk.Label(tab, text="Input Directory:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        input_dir_entry.grid(row=0, column=1, padx=10, pady=10)
        input_dir_entry.drop_target_register(DND_FILES)
        input_dir_entry.dnd_bind('<<Drop>>', lambda event, tf=input_dir_entry, isPDF = False: drop(event, tf, isPDF))
        ttk.Button(tab, text="Browse", command=select_input_directory).grid(row=0, column=2, padx=10, pady=10)

        # Output File Selection
        ttk.Label(tab, text="Output File:").grid(row=1, column=0, padx=10, pady=10, sticky="e")

        output_file_entry.grid(row=1, column=1, padx=10, pady=10)
        output_file_entry.drop_target_register(DND_FILES)
        output_file_entry.dnd_bind('<<Drop>>', lambda event, tf=output_file_entry, isPDF = True: drop(event, tf,isPDF))
        ttk.Button(tab, text="Browse", command=select_output_file).grid(row=1, column=2, padx=10, pady=10)

        # Combine Button
        ttk.Button(tab, text="Combine PDFs", command=perform_combine).grid(row=2, column=1,
                                                                                                  pady=20)
    def select_input_directory():
        directory = filedialog.askdirectory()
        if directory:
            input_dir_entry.delete(0, tk.END)
            input_dir_entry.insert(0, directory)

    def select_output_file():
        file_path = filedialog.asksaveasfilename(filetypes=[("PDF Files", "*.pdf")], defaultextension=".pdf")
        if file_path:
            output_file_entry.delete(0, tk.END)
            output_file_entry.insert(0, file_path)

    def perform_combine():
        input_directory = input_dir_entry.get()
        output_file = output_file_entry.get()

        if not input_directory or not output_file:
            messagebox.showerror("Error", "Both input directory and output file must be specified.")
            return

        combine_pdfs(input_directory, output_file, root)

# endregion

    # region Tab 3 (Swap) functions
    def SwapPDFTab(tab):
        # Tab 3: PDF Page Swapper
        notebook.add(tab, text="PDF Page Swapper")

        ttk.Label(tab, text="Original PDF:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        t1_original_pdf_entry.grid(row=0, column=1, padx=10, pady=10)
        t1_original_pdf_entry.drop_target_register(DND_FILES)
        t1_original_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=t1_original_pdf_entry, isPDF = True: drop(event, tf,isPDF))
        ttk.Button(tab, text="Browse", command=select_original_pdf).grid(row=0, column=2, padx=10, pady=10)

        ttk.Label(tab, text="New Page PDF:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        t1_new_page_pdf_entry.grid(row=1, column=1, padx=10, pady=10)
        t1_new_page_pdf_entry.drop_target_register(DND_FILES)
        t1_new_page_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=t1_new_page_pdf_entry, isPDF = True: drop(event, tf,isPDF))
        ttk.Button(tab, text="Browse", command=select_new_page_pdf).grid(row=1, column=2, padx=10, pady=10)

        ttk.Label(tab, text="Output PDF:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        t1_output_pdf_entry.grid(row=2, column=1, padx=10, pady=10)
        t1_output_pdf_entry.drop_target_register(DND_FILES)
        t1_output_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=t1_output_pdf_entry, isPDF = True: drop(event, tf,isPDF))
        ttk.Button(tab, text="Browse", command=t3_select_output_pdf).grid(row=2, column=2, padx=10, pady=10)

        ttk.Label(tab, text="Page Index:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        page_index_entry.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        ttk.Button(tab, text="Swap Page", command=perform_swap).grid(row=4, column=1, pady=20)

    def select_original_pdf():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            t1_original_pdf_entry.delete(0, tk.END)
            t1_original_pdf_entry.insert(0, path)

    def select_new_page_pdf():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            t1_new_page_pdf_entry.delete(0, tk.END)
            t1_new_page_pdf_entry.insert(0, path)

    def t3_select_output_pdf():
        path = filedialog.asksaveasfilename(filetypes=[("PDF Files", "*.pdf")], defaultextension=".pdf")
        if path:
            t1_output_pdf_entry.delete(0, tk.END)
            t1_output_pdf_entry.insert(0, path)

    def perform_swap():
        original_pdf_path = t1_original_pdf_entry.get()
        new_page_pdf_path = t1_new_page_pdf_entry.get()
        output_pdf_path = t1_output_pdf_entry.get()

        MaxPage = getPDFSetLength(original_pdf_path)
        if int(page_index_entry.get()) < 0 or int(page_index_entry.get()) > MaxPage:
            messagebox.showerror("Invalid Index Entered", f"Enter a number between 1 and {MaxPage}.")
            return

        try:
            page_index = int(page_index_entry.get())-1
        except ValueError:
            messagebox.showerror("Error", "Page index must be a valid integer.")
            return

        if not original_pdf_path or not new_page_pdf_path or not output_pdf_path:
            messagebox.showerror("Error", "All fields must be filled.")
            return

        swap_pdf_page(original_pdf_path, new_page_pdf_path, output_pdf_path, page_index, root)
# endregion

    # region Tab 4 (Insert) functions
    def InsertPDFTab(tab):
        notebook.add(tab, text="PDF Inserter")
        # Target PDF Selection
        ttk.Label(tab, text="Target PDF:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        target_pdf_entry.grid(row=0, column=1, padx=10, pady=10)
        target_pdf_entry.drop_target_register(DND_FILES)
        target_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=target_pdf_entry, isPDF = True: drop(event, tf, isPDF))
        ttk.Button(tab, text="Browse", command=select_target_pdf).grid(row=0, column=2, padx=10, pady=10)

        # Insert PDF Selection
        ttk.Label(tab, text="Insert PDF:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        insert_pdf_entry.grid(row=1, column=1, padx=10, pady=10)
        insert_pdf_entry.drop_target_register(DND_FILES)
        insert_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=insert_pdf_entry, isPDF = True: drop(event, tf,isPDF))
        ttk.Button(tab, text="Browse", command=select_insert_pdf).grid(row=1, column=2, padx=10, pady=10)

        # Output PDF Selection
        ttk.Label(tab, text="Output PDF:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        output_pdf_entry.grid(row=2, column=1, padx=10, pady=10)
        output_pdf_entry.drop_target_register(DND_FILES)
        output_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=output_pdf_entry, isPDF = True: drop(event, tf, isPDF))
        ttk.Button(tab, text="Browse", command=select_output_pdf).grid(row=2, column=2, padx=10, pady=10)

        # Insert Index
        ttk.Label(tab, text="Insert Index:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        insert_index_entry.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        # Insert Button
        ttk.Button(tab, text="Insert PDF", command=perform_insert).grid(row=4, column=1, pady=20)


    def select_target_pdf():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            target_pdf_entry.delete(0, tk.END)
            target_pdf_entry.insert(0, path)

    def select_insert_pdf():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            insert_pdf_entry.delete(0, tk.END)
            insert_pdf_entry.insert(0, path)

    def select_output_pdf():
        path = filedialog.asksaveasfilename(filetypes=[("PDF Files", "*.pdf")], defaultextension=".pdf")
        if path:
            output_pdf_entry.delete(0, tk.END)
            output_pdf_entry.insert(0, path)

    def perform_insert():
        target_pdf_path = target_pdf_entry.get()
        insert_pdf_path = insert_pdf_entry.get()
        output_pdf_path = output_pdf_entry.get()

        MaxPage = getPDFSetLength(target_pdf_path)
        if int(insert_index_entry.get()) < 0 or int(insert_index_entry.get()) > MaxPage:
            messagebox.showerror("Invalid Index Entered", f"Enter a number between 1 and {MaxPage}.")
            return

        try:
            insert_index = int(insert_index_entry.get())-1
        except ValueError:
            messagebox.showerror("Error", "Insert index must be a valid integer.")
            return

        if not target_pdf_path or not insert_pdf_path or not output_pdf_path:
            messagebox.showerror("Error", "All fields must be filled.")
            return

        insert_pdf_pages(target_pdf_path, insert_pdf_path, output_pdf_path, insert_index, root)

#endregion

    # region Tab 5 (Delete) Functions
    def DeletePDFTab(tab):
        notebook.add(tab5, text="PDF Deleter")
        # Input PDF selection
        ttk.Label(tab, text="Input PDF:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        t5_input_pdf_entry.grid(row=0, column=1, padx=10, pady=5)
        t5_input_pdf_entry.drop_target_register(DND_FILES)
        t5_input_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=t5_input_pdf_entry, isPDF = True: drop(event, tf, isPDF))
        ttk.Button(tab, text="Browse", command=t5_select_input_pdf).grid(row=0, column=2, padx=10, pady=5)

        # Output PDF selection
        ttk.Label(tab, text="Output PDF:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        t5_output_pdf_entry.grid(row=1, column=1, padx=10, pady=5)
        t5_output_pdf_entry.drop_target_register(DND_FILES)
        t5_output_pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=t5_output_pdf_entry, isPDF = True: drop(event, tf, isPDF))
        ttk.Button(tab, text="Browse", command=t5_select_output_pdf).grid(row=1, column=2, padx=10, pady=5)

        # Pages to remove
        ttk.Label(tab, text="Pages to Remove (e.g., 1,3,5-7):").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        t5_pages_entry.grid(row=2, column=1, padx=10, pady=5)

        # Process button
        ttk.Button(tab, text="Remove Pages", command=t5_process_pdf).grid(row=3, column=0, columnspan=3, pady=10)

    def t5_select_input_pdf():
        file_path = filedialog.askopenfilename(
            filetypes=[("PDF Files", "*.pdf")],
            title="Select Input PDF"
        )
        t5_input_pdf_entry.delete(0, tk.END)
        t5_input_pdf_entry.insert(0, file_path)

    def t5_select_output_pdf():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            title="Save Output PDF As"
        )
        t5_output_pdf_entry.delete(0, tk.END)
        t5_output_pdf_entry.insert(0, file_path)

    def t5_process_pdf():
        input_pdf = t5_input_pdf_entry.get()
        output_pdf = t5_output_pdf_entry.get()
        pages_to_remove = t5_pages_entry.get()

        if not input_pdf or not output_pdf or not pages_to_remove:
            messagebox.showerror("Error", "All fields are required!")
            return

        if remove_pages_from_pdf(input_pdf, output_pdf, pages_to_remove, root):
            messagebox.showinfo("Success", f"Pages removed successfully! Output saved as {output_pdf}")

    # endregion

    #region Tab 6 (Rotate) Functions
    def rotate_pdf(input_file, output_file, rotation_angle=90):
        try:
            # Open the input PDF file
            reader = PdfReader(input_file)
            writer = PdfWriter()

            # Rotate each page
            for page in reader.pages:
                page.rotate(rotation_angle)
                writer.add_page(page)

            # Write the rotated PDF to an output file
            with open(output_file, 'wb') as output_pdf:
                writer.write(output_pdf)
            messagebox.showinfo("Success", "PDF rotated and saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def create_pdf_tab(notebook):
        # Create a new frame for the tab
        pdf_tab = ttk.Frame(notebook)
        notebook.add(pdf_tab, text="Rotate PDF")

        # Input file selection
        ttk.Label(pdf_tab, text="Input PDF:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        input_path = tk.StringVar()
        input_entry = ttk.Entry(pdf_tab, textvariable=input_path, width=50)
        input_entry.drop_target_register(DND_FILES)
        input_entry.dnd_bind('<<Drop>>', lambda event, tf=input_entry, isPDF = True: drop(event, tf, isPDF))
        input_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(pdf_tab, text="Browse", command=lambda: select_file(input_path)).grid(row=0, column=2, padx=10,
                                                                                         pady=10)

        # Output file selection
        ttk.Label(pdf_tab, text="Output PDF:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        output_path = tk.StringVar()
        output_entry = ttk.Entry(pdf_tab, textvariable=output_path, width=50)
        output_entry.drop_target_register(DND_FILES)
        output_entry.dnd_bind('<<Drop>>', lambda event, tf=output_entry, isPDF = True: drop(event, tf, isPDF))
        output_entry.grid(row=1, column=1, padx=10, pady=10)
        ttk.Button(pdf_tab, text="Browse", command=lambda: save_file(output_path)).grid(row=1, column=2, padx=10,
                                                                                        pady=10)

        # Rotation angle selection
        ttk.Label(pdf_tab, text="Rotation Angle:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        rotation_angle_map = {"Clockwise": 90, "Upside Down": 180, "Counterclockwise": 270}
        rotation_label = tk.StringVar(value="Clockwise")
        rotation_dropdown = ttk.OptionMenu(
            pdf_tab, rotation_label, "Clockwise", *rotation_angle_map.keys()
        )
        rotation_dropdown.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        # Process button
        ttk.Button(
            pdf_tab,
            text="Rotate PDF",
            command=lambda: rotate_pdf(input_path.get(), output_path.get(), rotation_angle_map[rotation_label.get()])
        ).grid(row=3, column=1, padx=10, pady=20)

        return pdf_tab

    def select_file(path_var):
        filename = filedialog.askopenfilename(
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if filename:
            path_var.set(filename)

    def save_file(path_var):
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if filename:
            path_var.set(filename)
    #endregion

    #region Tab 7 (Convert to Docx) Functions
    def PDFToDocxTab(tab):
        notebook.add(tab, text="PDF → Word")

        # PDF path entry
        ttk.Label(tab, text="Select PDF File:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        pdf_path_var = tk.StringVar()
        pdf_entry = ttk.Entry(tab, textvariable=pdf_path_var, width=50)
        pdf_entry.drop_target_register(DND_FILES)
        pdf_entry.dnd_bind('<<Drop>>', lambda event, tf=pdf_entry, isPDF=True: drop(event, tf, isPDF))
        pdf_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(tab, text="Browse", command=lambda: browse_pdf(pdf_path_var)).grid(row=0, column=2)

        # Convert button
        ttk.Button(
            tab,
            text="Convert to Word",
            command=lambda: convert_pdf_to_docx(pdf_path_var)
        ).grid(row=1, column=1, pady=20)

    def browse_pdf(path_var):
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file:
            path_var.set(file)

    def convert_pdf_to_docx(path_var):
        pdf_path = path_var.get()
        if not pdf_path:
            messagebox.showerror("Error", "Please select a PDF first.")
            return

        docx_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Document", "*.docx")]
        )
        if not docx_path:
            return  # cancelled

        try:
            cv = Converter(pdf_path)
            cv.convert(docx_path)
            cv.close()
            messagebox.showinfo("Success", f"Saved as:\n{docx_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    #endregion

    # region Tab 8 (Crop PDF) Functions

    sample_prompt = (
    "Please perform OCR on the attached cropped images.\n"
    "Make an abbreviated version of all the text in a column titled, 'TAG.'\n"
    "The TAG column should contain no spaces or special characters.\n"
    "Underscores can be used if they make the output more human-readable.\n"
    "Then, combine the entire text into a single column titled 'DESCRIPTION.'\n"
    )

    def PDFCropTab(parent):
        # PDF Cropper state
        parent.pdf_paths = []
        parent.pdf_save_dir = ''
        parent.crop_regions = []
        parent.pdf_index = 0
        parent.crop_index = 0
        parent.scale = 1.0
        parent.erase_mode = False


        # Input controls
        frm = ttk.Frame(parent)
        frm.pack(pady=10, padx=10, fill='x')
        parent.pdf_in_var = tk.StringVar()
        file_to_crop = ttk.Entry(frm, textvariable=parent.pdf_in_var, width=50)
        file_to_crop.drop_target_register(DND_FILES)
        file_to_crop.dnd_bind('<<Drop>>', lambda event, tf=file_to_crop, isPDF=True: drop(event, tf, isPDF))
        file_to_crop.grid(row=0, column=0)
        ttk.Button(frm, text='Browse PDF(s)', command=lambda: _browse_pdfs(parent)).grid(row=0, column=1)
        parent.pdf_save_var = tk.StringVar()
        ttk.Entry(frm, textvariable=parent.pdf_save_var, width=50).grid(row=1, column=0)
        ttk.Button(frm, text='Browse Folder', command=lambda: _browse_pdf_save(parent)).grid(row=1, column=1)

        # Action buttons
        btns = ttk.Frame(parent)
        btns.pack(pady=5)
        ttk.Button(btns, text='Define Crop Regions', command=lambda: _open_pdf_crop_window(parent)).pack(side='left',
                                                                                                         padx=5)
        ttk.Button(btns, text='Submit & Crop → PNG', command=lambda: _run_pdf_crop_multi(parent)).pack(side='left',
                                                                                                       padx=5)
        parent.prompt_frame = ttk.LabelFrame(parent, text="Sample ChatGPT OCR Prompt")
        parent.prompt_frame.pack(fill='both', expand=True, padx=10, pady=10)
        parent.prompt_box = scrolledtext.ScrolledText(parent.prompt_frame,
                                               wrap=tk.WORD,
                                               height=8)

        parent.prompt_box.pack(fill="both", expand=True, padx=5, pady=5)

        # Browse methods

    def _browse_pdfs(self):
        files = filedialog.askopenfilenames(title='Select PDFs', filetypes=[('PDF', '*.pdf')])
        if files:
            self.pdf_paths = list(files)
            names = '; '.join(os.path.basename(f) for f in files)
            self.pdf_in_var.set(names)

    def _browse_pdf_save(self):
        d = filedialog.askdirectory(title='Select save folder')
        if d:
            self.pdf_save_dir = d
            self.pdf_save_var.set(d)

        # Crop window

    def _open_pdf_crop_window(self):
        if not self.pdf_paths:
            messagebox.showwarning('No PDFs', 'Pick at least one PDF first.')
            return
        # Convert PDFs to PNG lists of pages
        pages_list = [convert_from_path(p, poppler_path=r"poppler/Library/bin") for p in self.pdf_paths]
        pages = pages_list[0]
        self.png_pages = pages
        if not any(self.crop_regions):
            self.crop_regions = [[] for _ in pages]
        self.crop_index = 0
        self.scale = 1.0
        self.erase_mode = False

        win = tk.Toplevel()
        win.title('PNG Crop Tool')
        win.geometry('900x650')
        # Canvas + scrollbars
        cont = ttk.Frame(win);
        cont.pack(fill='both', expand=True)
        vbar = ttk.Scrollbar(cont, orient='vertical')
        hbar = ttk.Scrollbar(cont, orient='horizontal')
        c = tk.Canvas(cont, bg='lightgray', xscrollcommand=hbar.set, yscrollcommand=vbar.set, cursor='cross')
        hbar.config(command=c.xview);
        vbar.config(command=c.yview)
        hbar.pack(side='bottom', fill='x');
        vbar.pack(side='right', fill='y');
        c.pack(fill='both', expand=True)

        self._cv = c
        self._orig_img = self.png_pages[0]



        def _render():
            c.delete('all')
            w, h = self._orig_img.size
            sw, sh = int(w * self.scale), int(h * self.scale)
            resized = self._orig_img.resize((sw, sh), Image.LANCZOS)
            self._tkimg = ImageTk.PhotoImage(resized)
            c.create_image(0, 0, anchor='nw', image=self._tkimg)
            for x1, y1, x2, y2 in self.crop_regions[self.crop_index]:
                c.create_rectangle(x1 * self.scale, y1 * self.scale, x2 * self.scale, y2 * self.scale, outline='red')
            c.config(scrollregion=c.bbox('all'))

        def _nav(dir):
            ni = self.crop_index + dir
            if 0 <= ni < len(self.png_pages):
                self.crop_index = ni
                self._orig_img = self.png_pages[ni]
                _render()

        def _zoom(f):
            self.scale *= f;
            _render()

        def _erase(e):
            x = c.canvasx(e.x) / self.scale;
            y = c.canvasy(e.y) / self.scale
            for i, (x1, y1, x2, y2) in enumerate(self.crop_regions[self.crop_index]):
                if x1 <= x <= x2 and y1 <= y <= y2:
                    del self.crop_regions[self.crop_index][i]
                    _render();
                    break

        def _on_press(e):
            if self.erase_mode:
                _erase(e)
            else:
                _draw_start(e)

        def _on_drag(e):
            if not self.erase_mode: _draw_drag(e)

        def _on_release(e):
            if not self.erase_mode: _draw_end(e)

        def _draw_start(e):
            x = c.canvasx(e.x) / self.scale;
            y = c.canvasy(e.y) / self.scale
            c._dx0, c._dy0 = x, y
            c._currect = c.create_rectangle(x * self.scale, y * self.scale, x * self.scale, y * self.scale,
                                            outline='red')

        def _draw_drag(e):
            x = c.canvasx(e.x);
            y = c.canvasy(e.y);
            c.coords(c._currect, c._dx0 * self.scale, c._dy0 * self.scale, x, y)

        def _draw_end(e):
            x1, y1 = c._dx0, c._dy0;
            x2 = c.canvasx(e.x) / self.scale;
            y2 = c.canvasy(e.y) / self.scale
            self.crop_regions[self.crop_index].append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

        # Bindings
        c.bind('<ButtonPress-1>', _on_press);
        c.bind('<B1-Motion>', _on_drag);
        c.bind('<ButtonRelease-1>', _on_release)
        c.bind('<MouseWheel>', lambda e: _zoom(1.1 if e.delta > 0 else 1 / 1.1))
        c.bind('<Button-4>', lambda e: _zoom(1.2));
        c.bind('<Button-5>', lambda e: _zoom(1 / 1.2))

        # Toolbar
        bar = ttk.Frame(win);
        bar.pack(fill='x', pady=5)

        def _toggle():
            self.erase_mode = not self.erase_mode; btn.config(text=('Draw Mode' if self.erase_mode else 'Erase Mode'))

        btn = ttk.Button(bar, text='Erase Mode', command=_toggle);
        btn.pack(side='left', padx=3)
        for txt, cmd in [('‹ Prev', lambda: _nav(-1)), ('Next ›', lambda: _nav(1)), ('Zoom In', lambda: _zoom(1.2)),
                         ('Zoom Out', lambda: _zoom(1 / 1.2)),
                         ('Clear All', lambda: self.crop_regions[self.crop_index].clear() or _render()),
                         ('Close', win.destroy)]: ttk.Button(bar, text=txt, command=cmd).pack(side='left', padx=3)


        win.update_idletasks()  # force layout so canvas.winfo_width()/winfo_height() are valid
        place_on_active_monitor(win, win.winfo_width(), win.winfo_height())
        cw = c.winfo_width()
        ch = c.winfo_height()

        iw, ih = self._orig_img.size  # original PIL image dims
        # choose the smaller ratio so the whole image fits:
        self.scale = min(cw / iw, ch / ih)*1000
        _render()

    def _run_pdf_crop_multi(self):
        if not (self.pdf_paths and self.pdf_save_dir): messagebox.showerror('Missing Info',
                                                                            'Select files and folder'); return
        base = os.path.splitext(os.path.basename(self.pdf_paths[0]))[0]
        for idx, regs in enumerate(self.crop_regions):
            for ridx, (x1, y1, x2, y2) in enumerate(regs, 1):
                crop = self.png_pages[idx].crop((x1, y1, x2, y2))
                fn = f"{base}_pg{idx + 1}_r{ridx}.png"
                crop.save(os.path.join(self.pdf_save_dir, fn))
        messagebox.showinfo('Done', 'All cropped PNGs saved.')
        self.prompt_box.insert("1.0", sample_prompt)

    #endregion

    def drop(event, text_field, isPDF):
        # This drop event will populate a text field with the path of the file that is
        # dropped on it
        file_path = event.data
        if file_path.startswith("{") and file_path.endswith("}"):
            file_path = file_path[1:-1]
        text_field.delete(0, tk.END)
        if isPDF:
            if file_path.lower().endswith(".pdf"):
                text_field.insert(0, file_path)
            else:
                messagebox.showerror("Error", "The loaded file is not a PDF document. Please select a PDF document.")
        else:
            last_part_of_path = file_path.split("/")[-1]
            if "." in last_part_of_path:
                messagebox.showerror("Error", "The content loaded does not appear to be a directory. " 
                                              "If the content loaded was a directory, "
                                              "The Last directory used can not include a '.' character.")
            else:
                text_field.insert(0, file_path)

    def place_on_active_monitor(root, win_w, win_h):
        # get pointer pos (global coordinates)
        mx, my = root.winfo_pointerx(), root.winfo_pointery()

        # find the monitor containing the pointer
        for m in get_monitors():
            if m.x <= mx < m.x + m.width and m.y <= my < m.y + m.height:
                # center your window on that monitor
                x = m.x + (m.width - win_w) // 2
                y = m.y + (m.height - win_h) // 2
                root.geometry(f"{win_w}x{win_h}+{x}+{y}")
                return

    # Create the main window
    root = TkinterDnD.Tk()
    #root.tk.call('package', 'require', 'tkdnd')

    root.title("PDF Utility App")
    root.geometry("650x250")
    root.iconbitmap("pdf.ico")
    place_on_active_monitor(root, 700, 250)
    # Create a Notebook widget
    notebook = ttk.Notebook(root)

    # region Tab Creation
    # Create Each tab with its specified function
    # Tab 1 is used to split a PDF set into multiple pages
    tab1 = ttk.Frame(notebook)
    pdf_file_entry = ttk.Entry(tab1, width=50)
    output_dir_entry = ttk.Entry(tab1, width=50)
    useSheetNum = tk.BooleanVar(value=False)
    radio_true = ttk.Radiobutton(tab1, text="Use Sheet Number", variable=useSheetNum, value=True)
    radio_false = ttk.Radiobutton(tab1, text="Use Page Number", variable=useSheetNum, value=False)
    SplitPDFTab(tab1)

    # Tab 2 is used to combine PDF pages into a single set
    tab2 = ttk.Frame(notebook)
    input_dir_entry = ttk.Entry(tab2, width=50)
    output_file_entry = ttk.Entry(tab2, width=50)
    CombinePDFTab(tab2)

    # Tab 3 is used to swap out a single PDF page from a PDF Set
    tab3 = ttk.Frame(notebook)
    t1_original_pdf_entry = ttk.Entry(tab3, width=50)
    t1_new_page_pdf_entry = ttk.Entry(tab3, width=50)
    t1_output_pdf_entry = ttk.Entry(tab3, width=50)
    page_index_entry = ttk.Entry(tab3, width=10)
    SwapPDFTab(tab3)

    # Tab 4 is used to insert a PDF page or set into another PDF page or set
    tab4 = ttk.Frame(notebook)
    target_pdf_entry = ttk.Entry(tab4, width=50)
    insert_pdf_entry = ttk.Entry(tab4, width=50)
    output_pdf_entry = ttk.Entry(tab4, width=50)
    insert_index_entry = ttk.Entry(tab4, width=10)
    InsertPDFTab(tab4)

    # Tab 5 is used to delete pages from a PDF set
    tab5 = ttk.Frame(notebook)
    t5_input_pdf_entry = ttk.Entry(tab5, width=50)
    t5_output_pdf_entry = ttk.Entry(tab5, width=50)
    t5_pages_entry = ttk.Entry(tab5, width=50)
    DeletePDFTab(tab5)
    # endregion

    # Tab 6 is used to rotate PDFs
    create_pdf_tab(notebook)

    # --- new PDF→Word tab ---
    tab7 = ttk.Frame(notebook)
    PDFToDocxTab(tab7)

    tab8 = ttk.Frame(notebook)
    notebook.add(tab8, text="PDF Cropper")
    PDFCropTab(tab8)

    # Pack the Notebook
    notebook.pack(expand=True, fill="both")
    # Run the main loop
    root.mainloop()


if __name__ == '__main__':
    # Run the GUI
    create_gui()
