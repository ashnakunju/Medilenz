import winsound
import platform
import cv2
import easyocr
import sqlite3
from fuzzywuzzy import fuzz
import re
import time as t
import pyttsx3
import tkinter as tk
from tkinter import messagebox, simpledialog
from PIL import Image, ImageTk
from datetime import datetime
import threading
import integrated_new_no_db

# Global variables
lang_var = ""
cap = None
reader = None
engine = None
conn = None
cursor = None
window = None  # Tkinter root window
label = None  # Camera label
info_label = None  # Information label
medicine_detected = False  # Flag to track if medicine details have been spoken
text_window = None  # Window to display the read text
text_label = None  # Label to display the read text
details_label = None  # Label to display medicine details

# Function to create a new SQLite connection and cursor
def create_db_connection():
    global conn, cursor
    conn = sqlite3.connect("medicine_data.db", check_same_thread=False)
    cursor = conn.cursor()

    # Create tables if not exists
    cursor.execute('''CREATE TABLE IF NOT EXISTS medicine_info
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       text TEXT,
                       used_for TEXT,
                       dosage TEXT,
                       mal_details TEXT,
                       hindi_details TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS reminders
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       medicine_name TEXT,
                       time TEXT)''')
    conn.commit()
    return conn, cursor

# Function to create the text display window
def create_text_window():
    global text_window, text_label, details_label
    text_window = tk.Toplevel(window)
    text_window.title("Medicine Information")
    text_window.geometry("500x300")
    
    # Frame for detected text
    text_frame = tk.Frame(text_window)
    text_frame.pack(pady=10)
    
    tk.Label(text_frame, text="Detected Text:", font=("Arial", 12, "bold")).pack(anchor='w')
    text_label = tk.Label(text_frame, text="No text detected yet", font=("Arial", 12), wraplength=480, justify='left')
    text_label.pack(anchor='w')
    
    # Separator
    tk.Frame(text_window, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=5, pady=5)
    
    # Frame for medicine details
    details_frame = tk.Frame(text_window)
    details_frame.pack(pady=10)
    
    tk.Label(details_frame, text="Medicine Details:", font=("Arial", 12, "bold")).pack(anchor='w')
    details_label = tk.Label(details_frame, text="No details available yet", font=("Arial", 12), wraplength=480, justify='left')
    details_label.pack(anchor='w')
    
    # Make the window stay on top
    text_window.attributes('-topmost', True)

# Function to update the text display
def update_text_display(text, details=None):
    if text_window and text_label:
        text_label.config(text=text)
        
    if details and text_window and details_label:
        details_label.config(text=details)

# Function to store medicine in the database
def store_in_database(text, used_for, dosage=None, mal_details=None, hindi_details=None):
    cursor.execute("INSERT INTO medicine_info (text, used_for, dosage, mal_details, hindi_details) VALUES (?, ?, ?, ?, ?)",
                   (text, used_for, dosage, mal_details, hindi_details))
    conn.commit()

# Function to update medicine dosage
def update_dosage(medicine_id, new_dosage):
    cursor.execute("UPDATE medicine_info SET dosage = ? WHERE id = ?", (new_dosage, medicine_id))
    conn.commit()

# Function to get existing medicine entries
def get_existing_entries():
    cursor.execute("SELECT id, text, used_for, dosage, mal_details, hindi_details FROM medicine_info")
    return cursor.fetchall()

# Function to show existing medicines
def show_existing_entries():
    entries = get_existing_entries()
    entry_window = tk.Toplevel(window)
    entry_window.title("Medicines List")

    for entry in entries:
        label = tk.Label(entry_window, text=f"{entry[1]} - {entry[2]} - Dosage: {entry[3]} - Malayalam: {entry[4]} - Hindi: {entry[5]}")
        label.pack()

        button = tk.Button(entry_window, text="Edit Dosage",
                           command=lambda id=entry[0]: set_dosage(id))
        button.pack()

# Function to set dosage
def set_dosage(medicine_id):
    new_dosage = simpledialog.askstring("Dosage", "Enter the dosage:")
    if new_dosage:
        update_dosage(medicine_id, new_dosage)
        messagebox.showinfo("Success", "Dosage updated successfully")

# Function to validate if text is valid
def is_valid_text(text):
    letter_count = len(re.findall(r'[a-zA-Z]', text))
    return letter_count >= 7

# Function to play beep sound
def beep_sound(duration=5):
    frequency = 440
    duration_ms = duration * 1000
    if platform.system() == 'Windows':
        winsound.Beep(frequency, duration_ms)
    else:
        pass  # For non-windows OS

# Function to convert text to speech
def speak_detail(detail):
    engine.say(detail)
    engine.runAndWait()

# Function to detect tablets from the camera feed
def detect_tablets(frame, lang):
    global reader, medicine_detected

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    results = reader.readtext(gray)

    for (bbox, text, prob) in results:
        if "tablets" in text.lower():
            same_line_texts = []
            for (nb_bbox, nb_text, nb_prob) in results:
                if abs(nb_bbox[0][1] - bbox[0][1]) < 10 and nb_text.lower() != "tablets":
                    same_line_texts.append(nb_text)

            extracted_text = " ".join(same_line_texts)

            if extracted_text:
                update_text_display(extracted_text)  # Update the text display window
                
                if not is_valid_text(extracted_text):
                    continue

                # Check if medicine exists in the database
                existing_entries = get_existing_entries()
                max_similarity = 0
                matched_entry = None

                for entry in existing_entries:
                    db_text = entry[1]
                    similarity = fuzz.ratio(extracted_text.lower(), db_text.lower())
                    if similarity > max_similarity:
                        max_similarity = similarity
                        matched_entry = entry

                # If medicine exists in the database
                if max_similarity > 80 and not medicine_detected:
                    beep_sound()
                    
                    # Prepare details based on language
                    if lang == "eng":
                        details = f"Used for: {matched_entry[2]}\nDosage: {matched_entry[3]}"
                        integrated_new_no_db.eng(matched_entry[1], matched_entry[2], matched_entry[3])
                    elif lang == "mal":
                        details = f"ഉപയോഗം: {matched_entry[4]}\nഡോസേജ്: {matched_entry[3]}"
                        integrated_new_no_db.mal(matched_entry[1], matched_entry[4], matched_entry[3])
                    elif lang == "hindi":
                        details = f"उपयोग: {matched_entry[5]}\nखुराक: {matched_entry[3]}"
                        integrated_new_no_db.hindi(matched_entry[1], matched_entry[5], matched_entry[3])
                    
                    # Update the display with both text and details
                    update_text_display(f"Detected: {matched_entry[1]}", details)
                    
                    medicine_detected = True  # Set flag to True after speaking details
                    return frame, None, None, None
                else:
                    used_for = input(f"Enter what '{extracted_text}' is used for: ")
                    store_in_database(extracted_text, used_for, dosage=None)
   
    # Return the original frame and None for other values if no medicine is detected
    return frame, None, None, None

# Function to update the camera feed
def update_frame():
    global lang_var, label, medicine_detected

    ret, frame = cap.read()
    if ret:
        result = detect_tablets(frame, lang_var)
        if result is not None:
            processed_frame, _, _, _ = result
            img = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)))
            label.config(image=img)
            label.image = img

        # Stop the camera feed if medicine details have been spoken
        if medicine_detected:
            cap.release()  # Release the camera
            return  # Stop further execution

        window.after(10, update_frame)

# Function to submit language selection
def submit():
    global lang_var
    lang_var = lang_var.get()
    root.destroy()  # Close the language selection dialog
    initialize_main_window()  # Initialize the main Tkinter window

# Function to add reminders
def add_reminder():
    reminder_window = tk.Toplevel(window)
    reminder_window.title("Add Reminder")

    # Medicine Selection
    medicine_label = tk.Label(reminder_window, text="Select Medicine:")
    medicine_label.pack()

    medicines = [entry[1] for entry in get_existing_entries()]
    selected_medicine = tk.StringVar(reminder_window)
    selected_medicine.set(medicines[0])

    dropdown = tk.OptionMenu(reminder_window, selected_medicine, *medicines)
    dropdown.pack()

    # Time Selection
    time_label = tk.Label(reminder_window, text="Select Time (24-hour format):")
    time_label.pack()

    time_entry = tk.Entry(reminder_window)
    time_entry.pack()

    def save_reminder():
        medicine_name = selected_medicine.get()
        reminder_time = time_entry.get()
        cursor.execute("INSERT INTO reminders (medicine_name, time) VALUES (?, ?)", (medicine_name, reminder_time))
        conn.commit()
        messagebox.showinfo("Success", "Reminder Added")
        reminder_window.destroy()

    save_button = tk.Button(reminder_window, text="Save Reminder", command=save_reminder)
    save_button.pack()

# Function to open language selection dialog
def language_selection_dialog():
    global lang_var, root

    # Create main window
    root = tk.Tk()
    root.title("Language Selector")
    root.geometry("300x200")

    # Variable to store selected language
    lang_var = tk.StringVar(value="eng")  # Set English as default

    # Create widgets
    label = tk.Label(root, text="Choose your preferred language:", font=('Arial', 12))
    label.pack(pady=10)

    # Malayalam radio button
    mal_radio = tk.Radiobutton(root, text="Malayalam", variable=lang_var, value="mal", font=('Arial', 12))
    mal_radio.pack(anchor='w', padx=50)

    # English radio button
    eng_radio = tk.Radiobutton(root, text="English", variable=lang_var, value="eng", font=('Arial', 12))
    eng_radio.pack(anchor='w', padx=50)

    # Hindi radio button
    hindi_radio = tk.Radiobutton(root, text="Hindi", variable=lang_var, value="hindi", font=('Arial', 12))
    hindi_radio.pack(anchor='w', padx=50)

    # Submit button
    submit_btn = tk.Button(root, text="Submit", command=submit, font=('Arial', 12), bg='#4CAF50', fg='white')
    submit_btn.pack(pady=10)

    root.mainloop()

# Function to initialize the main Tkinter window
def initialize_main_window():
    global window, label, info_label

    # Create the main Tkinter window
    window = tk.Tk()
    window.title("Tablet Detection System")
    window.geometry("800x600")

    # Camera Label
    label = tk.Label(window)
    label.pack()

    # Information Text
    info_label = tk.Label(window, text="No medicine detected yet", font=("Arial", 14))
    info_label.pack()

    # Button to view existing medicines
    tk.Button(window, text="View Medicines", command=show_existing_entries).pack()

    # Button to add reminders
    tk.Button(window, text="Add Reminder", command=add_reminder).pack()

    # Button to quit
    tk.Button(window, text="Quit", command=window.quit).pack()

    # Create the text display window
    create_text_window()

    # Start the camera feed
    start_camera()

    # Run the Tkinter main loop
    window.mainloop()

# Function to initialize camera and start detection
def start_camera():
    global cap, reader, engine, conn, cursor

    # Initialize EasyOCR reader
    reader = easyocr.Reader(['en'])

    # Open camera
    cap = cv2.VideoCapture(0)

    # Adjust camera settings for auto-focus and exposure
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # Enable auto-focus
    cap.set(cv2.CAP_PROP_EXPOSURE, -4)  # Adjust exposure level

    # Initialize text-to-speech engine
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 1)
    engine.setProperty('pitch', 50)

    # Initialize SQLite database
    conn, cursor = create_db_connection()

    # Start the reminder checker thread
    reminder_thread = threading.Thread(target=check_reminders)
    reminder_thread.daemon = True
    reminder_thread.start()

    # Start the camera feed
    update_frame()

# Function to check reminders
def check_reminders():
    while True:
        now = datetime.now().strftime("%H:%M")
        cursor.execute("SELECT medicine_name, time FROM reminders")
        reminders = cursor.fetchall()

        for medicine, reminder_time in reminders:
            if reminder_time == now:
                speak_detail(f"Time to take your medicine: {medicine}")
                beep_sound()
        t.sleep(60)

# ----------------- Main Program ---------------------

# Open language selection dialog
language_selection_dialog()

# Close the database connection
if conn:
    conn.close()