import json
import os
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk, filedialog

class Flashcard:
    """
    Base class for all flashcard types
    Stores question, answer, scheduling data (done using the SM-2 algorithm) and optional tags applied by the user
    """
    def __init__(self, question, answer, tags="", image_path=""):
        #Card content
        self.question = question
        self.answer = answer
        self.tags = tags
        self.image_path = image_path #e.g "images/diagram.png

        #SM-2 spaced-repetition fields
        self.interval = 1       # Days until next review
        self.repetitions = 0    # Consecutive correct answers
        self.easiness = 2.5     # Difficulty multiplier (min 1.3)
        self.next_review = date.today().isoformat()

    #Scheduling
    def is_due(self, today=None):
        today = today or date.today()
        return today >= date.fromisoformat(self.next_review) # Return true if card is due for review today

    def update_schedule(self, quality, today=None):
        if quality >= 3:
            # Correct
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = round(self.interval * self.easiness)
            self.repetitions += 1
        else:
            # Incorrect
            self.repetitions = 0
            self.interval = 1

        #Adjust how easy card is based on recall quality using SM-2 Formula:
        #EF' = EF+(0.1-(5-q) * (0.08+(5-q) * 0.02)) - SM-2 FORMULA
        self.easiness = max(1.3, self.easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        self.next_review = (today + timedelta(days=self.interval)).isoformat()

    #Answer Checking
    def check_answer(self, user_input):
        # Return True if input is correct
        return user_input.strip().lower() == self.answer.strip().lower()

    #Convert to/from plain dict to JSON for storage

    def to_dict(self):
        return {
            "type": self.__class__.__name__,
            "question": self.question,
            "answer": self.answer,
            "tags": self.tags,
            "interval": self.interval,
            "repetitions": self.repetitions,
            "easiness": self.easiness,
            "next_review": self.next_review,
            "image_path": self.image_path
        }

    @classmethod
    def from_dict(cls, data):
        card = cls(data["question"], data["answer"], data.get("tags", ""), data.get("image_path", ""))
        card.interval = data["interval"]
        card.repetitions = data["repetitions"]
        card.easiness = data["easiness"]
        card.next_review = data["next_review"]
        return card

    def content_to_dict(self):
        return {"image_path": self.image_path}

class BasicCard(Flashcard): #Simple question and answer card
    CARD_TYPE = "Basic"

    def __init__(self, question, answer, tags="", image_path=""):
        super().__init__(question, answer, tags)
        self.image_path = image_path

    def to_dict(self):
        data = super().to_dict()
        data["image_path"] = self.image_path
        return data

    @classmethod
    def from_dict(cls, data):
        card = cls(data["question"], data["answer"], data.get("tags", ""), data.get("image_path", ""))
        card.interval = data["interval"]
        card.repetitions = data["repetitions"]
        card.easiness = data["easiness"]
        card.next_review = data["next_review"]
        return card


class MultipleChoiceCard(Flashcard): #Multiple choice card with list of options
    CARD_TYPE = "Multiple Choice"

    def __init__(self, question, answer, choices, tags=""):
        super().__init__(question, answer, tags)
        self.choices = choices  # List of options

    def check_answer(self, user_input):
        return user_input.strip().lower() == self.answer.strip().lower()

    def to_dict(self):
        data = super().to_dict()
        data["choices"] = self.choices
        return data

    @classmethod
    def from_dict(cls, data): #Reconstructs MC card from saved dictionary
        card = cls(
            data["question"],
            data["answer"],
            data.get("choices", []),
            data.get("tags", "")
        )
        card.interval = data["interval"]
        card.repetitions = data["repetitions"]
        card.easiness = data["easiness"]
        card.next_review = data["next_review"]
        return card

class ClozeCard(Flashcard): #A "fill in the blanks" card which contains "____" where the answer should be placed
    CARD_TYPE = "Cloze"

    def __init__(self, question, answer, tags="", image_path=""):
        super().__init__(question, answer, tags)
        self.image_path = image_path

    def to_dict(self):
        data = super().to_dict()
        data["image_path"] = self.image_path
        return data

    @classmethod
    def from_dict(cls, data):
        card = cls(data["question"], data["answer"], data.get("tags", ""), data.get("image_path", ""))
        card.interval = data["interval"]
        card.repetitions = data["repetitions"]
        card.easiness = data["easiness"]
        card.next_review = data["next_review"]
        return card

CARD_CLASSES = {"BasicCard": BasicCard,
                "MultipleChoiceCard": MultipleChoiceCard,
                "ClozeCard": ClozeCard
                }

def card_from_dict(data):
    #Reconstructs correct flashcard subclass from a saved dictionary
    cls = CARD_CLASSES.get(data.get("type"), BasicCard)
    return cls.from_dict(data)

class Deck:
    #A collection of flashcard objects with file persistence

    SAVE_FILE = "flashcard_data.json"

    def __init__(self):
        self.cards = []
        self.last_session_date = None
        self.streak = 0
        self.debug_date = None

    def today(self):
        #Return current date, or debug date if one is set
        return self.debug_date if self.debug_date else date.today()

    def add_card(self, card):
        #Add flashcard to the deck
        self.cards.append(card)

    def remove_card(self, index):
        #Remove card at a given list index
        if 0 <= index < len(self.cards):
            self.cards.pop(index)

    def due_cards(self):
        #Return a list of cards that are due for review today
        today = self.today()
        return [card for card in self.cards if card.is_due(today)]

    def save(self):
        #Serialise cards to JSON file
        data = {
            "cards":[card.to_dict() for card in self.cards],
            "last_session_date": self.last_session_date,
            "streak": self.streak
        }
        with open(self.SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        #Load cards from JSON file (if exists)
        if not os.path.exists(self.SAVE_FILE):
            return
        with open(self.SAVE_FILE, "r") as f:
            data=json.load(f)
            self.cards = [card_from_dict(d) for d in data["cards"]]
            self.last_session_date = data.get("last_session_date")
            self.streak = data.get("streak", 0)

    def record_session(self):
        today = self.today()
        today_str = today.isoformat()
        if self.last_session_date is None:
            self.streak = 1
        else:
            last = date.fromisoformat(self.last_session_date)
            gap = (today - last).days
            if gap == 0: #Already reviewed today - doesn't increment
                return
            elif gap == 1: #Reviewed yesterday - increase streak
                self.streak += 1
            else:
                self.streak = 1 #Missed day - streak reset
        self.last_session_date = today_str
        self.save()

#GUI LAYER

COLOURS = {
    "bg": "#0d1b2a",       #dark background
    "surface": "#1b263b",  #card background
    "accent": "#90e0ff",   #accent colour
    "correct": "#a7c957",  #green for correct
    "wrong": "#e63946",    #red for incorrect
    "text": "#e0e1dd",     #main text
    "muted": "#6c7086",    #secondary text
    "button_bg": "#1b263b" #button background
}

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_CARD = ("Segoe UI", 14)

def styled_button(parent, text, command, accent=False, danger=False): #Returns a consistently styled tkinter button, simplifying creation and ensuring consistency in the program
    bg = COLOURS["accent"] if accent else (COLOURS["wrong"] if danger else COLOURS["button_bg"])
    return tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=COLOURS["button_bg"],
        font = FONT_BODY, relief="flat",
        padx=16, pady=8, cursor="hand2",
        activebackground=COLOURS["surface"],
        activeforeground=COLOURS["accent"]
    )

class App(tk.Tk):
    #Root app window; Manages deck and switches between "Home" (shows stats and navigation), "Manageview" (add/delete cards), and "Reviewview" (review due cards)
    def __init__(self):
        super().__init__()
        self.title("Flashcard App")
        self.geometry("700x520")
        self.minsize(600, 440) #Prevents window becoming too small to use
        self.configure(bg=COLOURS["bg"])
        self.deck = Deck()
        self.deck.load()
        self.container = tk.Frame(self, bg=COLOURS["bg"])
        self.container.pack(fill="both", expand=True)
        self.show_home()

    #View Switching
    def show_home(self): #Replace current view with Homepage
        self.clear()
        Home(self.container, self).pack(fill="both", expand=True)

    def show_manage(self): #Replace current view with Manageview
        self.clear()
        ManageView(self.container, self).pack(fill="both", expand=True)

    def show_review(self): #Replace current view with Reviewview
        self.clear()
        ReviewView(self.container, self).pack(fill="both", expand=True)

    def clear(self): #Destroy all widgets in frame
        for widget in self.container.winfo_children():
            widget.destroy()

class Home(tk.Frame):
    """
    Home screen showing deck statistics and navigation
    """
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self.build()

    def build(self):
        #Centred inner frame
        inner = tk.Frame(self, bg=COLOURS["bg"])
        inner.pack(expand=True)

        #Title
        tk.Label(inner, text="Flashcards", font=FONT_TITLE, bg=COLOURS["bg"], fg=COLOURS["accent"]).pack()

        #Stats panel
        stats_frame = tk.Frame(inner, bg=COLOURS["surface"], padx=24, pady=16)
        stats_frame.pack(pady=28, ipadx=10)
        total = len(self.app.deck.cards)
        due = len(self.app.deck.due_cards())
        new = sum(1 for c in self.app.deck.cards if c.repetitions == 0)
        self.stat_row(stats_frame, "total cards", total, COLOURS["text"], 0)
        self.stat_row(stats_frame, "due today", due, COLOURS["accent"], 1)
        self.stat_row(stats_frame, "new (unseen)", new, COLOURS["correct"], 2)
        self.stat_row(stats_frame, "Daily Streak", f"{self.app.deck.streak}", "#ffaf4a", 3)

        #Navigation
        styled_button(inner, "start review", self.app.show_review, accent=True).pack(pady=(0,12))
        styled_button(inner, "manage cards", self.app.show_manage, accent=True).pack()
        debug_frame = tk.Frame(self, bg=COLOURS["bg"])
        debug_frame.pack(side="bottom", pady=8)
        self.build_debug_panel()

    def stat_row(self, parent, label, value, colour, row):
        tk.Label(parent, text=label, font=FONT_BODY, bg=COLOURS["surface"], fg=COLOURS["muted"]).grid(row=row, column=0)
        tk.Label(parent, text=str(value), font=("Segoe UI", 12, "bold"), bg=COLOURS["surface"], fg=colour).grid(row=row, column=1, sticky="e")

    def build_debug_panel(self): #Collapsable debug panel for shifting the simulated date
        debug_frame = tk.Frame(self, bg=COLOURS["bg"])
        debug_frame.pack(pady=(8, 0))
        tk.Label(debug_frame, text="Debug - simulated date:", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(side="left", padx=(0,6))
        #Show the active date
        active = self.app.deck.today()
        self.debug_date_label = tk.Label(debug_frame, text=active.isoformat(), font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["accent"] if self.app.deck.debug_date else COLOURS["muted"])
        self.debug_date_label.pack(side="left", padx=(0,8))

        styled_button(debug_frame, "- Day", lambda: self.shift_date(-1), accent=True).pack(side="left", padx=2)
        styled_button(debug_frame, "+ Day", lambda: self.shift_date(1), accent=True).pack(side="left", padx=2)
        styled_button(debug_frame, "Reset", lambda: self.reset_date(), accent=True).pack(side="left", padx=2)

    def shift_date(self, days): #Move simulated time forward or back by given number of days
        current = self.app.deck.today()
        self.app.deck.debug_date = current + timedelta(days=days)
        self.app.show_home() #Refresh stats to reflect new date

    def reset_date(self): #Clear the debug date override and return to the real date
        self.app.deck.debug_date = None
        self.app.show_home()

class ManageView(tk.Frame):
    """
    Card management screen. Allows users to view card list, add new cards, and delete existing ones
    """
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self.build()

    def build(self): #build screen layout
        #Header
        header = tk.Frame(self, bg=COLOURS["bg"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        tk.Label(header, text="manage cards", font=FONT_TITLE, bg=COLOURS["bg"], fg=COLOURS["text"]).pack(side="left")
        styled_button(header, "home", self.app.show_home, accent=True).pack(side="right")

        #Card List (using treeview)
        tree_frame = tk.Frame(self, bg=COLOURS["bg"])
        tree_frame.pack(fill="both", expand=True, padx=20)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.tree = ttk.Treeview(tree_frame, columns=("type", "question", "tags", "due"), show="headings", style="Custom.Treeview", yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.tree.yview)

        self.tree.heading("type", text="type")
        self.tree.heading("question", text="question")
        self.tree.heading("tags", text="tags")
        self.tree.heading("due", text="due")
        self.tree.column("type", width=110, anchor="w", minwidth=80)
        self.tree.column("question", width=260, anchor="w", minwidth=120)
        self.tree.column("tags", width=100, anchor="w", minwidth=60)
        self.tree.column("due", width=100, anchor="center", minwidth=60)
        self.tree.pack(fill="both", expand=True)
        self.refresh_list()

        #Bottom action row
        action_row = tk.Frame(self, bg=COLOURS["bg"])
        action_row.pack(pady=12, padx=20, fill="x")
        styled_button(action_row, "add card", self.open_add_dialog, accent=True).pack(side="left")
        styled_button(action_row, "delete selected", self.delete_selected, danger=True).pack(side="left", padx=8)

    def refresh_list(self): #Clear card list and fill with cards from deck
        for row in self.tree.get_children():
            self.tree.delete(row)
        for card in self.app.deck.cards:
            due_str = "Today" if card.is_due() else card.next_review
            card_type = getattr(card, "CARD_TYPE", "Basic")
            self.tree.insert("", "end", values=(card_type, card.question[:55], card.tags or "-", due_str))

    def delete_selected(self): #Remove selected card from deck and save
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Please select a card to delete.")
            return
        row_index = self.tree.index(selected[0])
        self.app.deck.remove_card(row_index)
        self.app.deck.save()
        self.refresh_list()

    def open_add_dialog(self): #Open window to add dialog to card
        AddCardDialog(self, self.app, self.refresh_list)

class AddCardDialog(tk.Toplevel):
    """
    Dialog for creating a new flashcard.
    Form changes based on the selected card type
    """
    def __init__(self, parent, app, on_save_callback):
        super().__init__(parent)
        self.app = app
        self.on_save = on_save_callback
        self.title("Add New Card")
        self.geometry("500x480")
        self.minsize(420, 400)
        self.resizable(True, True)
        self.configure(bg=COLOURS["bg"])
        self.grab_set()
        self.card_type_var = tk.StringVar(value="Basic")
        self.build()

    def build(self):
        tk.Label(self, text="Add New Card", font=FONT_TITLE,
                 bg=COLOURS["bg"], fg=COLOURS["accent"]).pack(pady=(20, 12))

        #Card type selector
        type_frame = tk.Frame(self, bg=COLOURS["bg"])
        type_frame.pack(pady=(0, 10))
        tk.Label(type_frame, text="Card Type:", font=FONT_BODY,bg=COLOURS["bg"], fg=COLOURS["text"]).pack(side="left", padx=6)
        type_menu = tk.OptionMenu(type_frame, self.card_type_var,"Basic", "Multiple Choice", "Cloze",command=self.on_type_change)
        type_menu.config(bg=COLOURS["button_bg"], fg=COLOURS["text"], font=FONT_SMALL, relief="flat",activebackground=COLOURS["surface"])
        type_menu.pack(side="left")
        self.form_frame = tk.Frame(self, bg=COLOURS["bg"])
        self.form_frame.pack(fill="both", expand=True, padx=30)
        self.build_form("Basic")
        #Save button
        styled_button(self, "Save Card",self.save, accent=True).pack(pady=14)

    def pick_image(self):
        path = filedialog.askopenfilename(parent=self, title="Select image",filetypes=[("Image files", "*.png *.gif")])
        if path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                rel_path = os.path.relpath(path, base_dir)
                self.image_path_var.set(rel_path)
            except ValueError:
                self.image_path_var.set(path)

    def on_type_change(self, value): #Rebuild whenever card type changes
        for widget in self.form_frame.winfo_children():
            widget.destroy()
        self.build_form(value)

    def build_form(self, card_type): #Create appropriate input fields based on card type
        ff = self.form_frame

        #Question (all types)
        tk.Label(ff, text="Question:", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(anchor="w", pady=(10, 2))
        self.q_entry = tk.Text(ff, height=3, font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["text"],insertbackground=COLOURS["text"], relief="flat", padx=6, pady=4)
        self.q_entry.pack(fill="x", expand=False)

        #Choices (Multiple Choice only)
        self.choices_frame = None
        self.choice_entries = []
        if card_type == "Multiple Choice":
            tk.Label(ff, text="Options (one per line, mark correct with *):", font=FONT_SMALL, bg=COLOURS["bg"],fg=COLOURS["muted"]).pack(anchor="w", pady=(8, 2))
            self.choices_text = tk.Text(ff, height=4, font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["text"],insertbackground=COLOURS["text"],relief="flat", padx=6, pady=4)
            self.choices_text.insert("end", "*Correct answer\nOption 2\nOption 3")
            self.choices_text.pack(fill="x")
        else:
            self.choices_text = None

        #Answer hint label for Cloze
        if card_type == "Cloze":
            tk.Label(ff, text="Write ___ in the question where the blank goes", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(anchor="w",pady=(8, 2))

        #Answer (all types except MC which derives it from choices)
        if card_type != "Multiple Choice":
            tk.Label(ff, text="Answer:", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(anchor="w", pady=(8, 2))
            self.a_entry = tk.Entry(ff, font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["text"], insertbackground=COLOURS["text"], relief="flat")
            self.a_entry.pack(fill="x", ipady=4)
        else:
            self.a_entry = None

        #Tags
        tk.Label(ff, text="Tags (optional):", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(anchor="w", pady=(8, 2))
        self.tags_entry = tk.Entry(ff, font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["text"], insertbackground=COLOURS["text"],relief="flat")
        self.tags_entry.pack(fill="x", ipady=4)

        #Image
        if card_type != "Multiple Choice":
            self.image_path_var = tk.StringVar()
            image_row = tk.Frame(ff, bg=COLOURS["bg"])
            image_row.pack(fill="x", pady=(8, 0))
            tk.Label(image_row, text="Image(optional):", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(
                side="left")
            tk.Label(image_row, textvariable=self.image_path_var, font=FONT_SMALL, bg=COLOURS["bg"],
                     fg=COLOURS["muted"]).pack(side="left", pady=6)
            styled_button(image_row, "Browse...", self.pick_image).pack(side="left")

    def save(self): #Validate inputs and save
        card_type = self.card_type_var.get()
        question = self.q_entry.get("1.0", "end").strip()
        tags = self.tags_entry.get().strip()
        image_path = self.image_path_var.get()

        if not question:
            messagebox.showwarning("Missing Field", "Please enter a question.")
            return

        if card_type == "Multiple Choice":
            card = self.build_mc_card(question, tags)
        elif card_type == "Cloze":
            card = self.build_cloze_card(question, tags)
        else:
            card = self.build_basic_card(question, tags)

        if card is None:
            return

        self.app.deck.add_card(card)
        self.app.deck.save()
        self.on_save()
        self.destroy()

    def build_basic_card(self, question, tags): #Construct a BasicCard from the form
        answer = self.a_entry.get().strip()
        if not answer:
            messagebox.showwarning("Missing Field", "Please enter an answer.")
            return None
        return BasicCard(question, answer, tags, self.image_path_var.get())

    def build_mc_card(self, question, tags): #Construct a MC Card from the choices text box
        raw = self.choices_text.get("1.0", "end").strip().splitlines()
        choices = [line.lstrip("*").strip() for line in raw if line.strip()]
        correct = [line.lstrip("*").strip()
                   for line in raw if line.strip().startswith("*")]
        if len(choices) < 2:
            messagebox.showwarning("Not Enough Options","Please enter at least 2 options.")
            return None
        if not correct:
            messagebox.showwarning("No Correct Answer","Mark the correct answer with * at the start.")
            return None
        return MultipleChoiceCard(question, correct[0], choices, tags)

    def build_cloze_card(self, question, tags): #Construct a ClozeCard from the form
        answer = self.a_entry.get().strip()
        if not answer:
            messagebox.showwarning("Missing Field","Please enter the missing word/phrase.")
            return None
        return ClozeCard(question, answer, tags, self.image_path_var.get())


class ReviewView(tk.Frame):
    """
    Review session screen.
    Steps through due cards one at a time using SM-2 algorithm
    Flow for each card:
    1) Show question (and choices for MC)
    2) User submits answer
    3) Shows correct/incorrect
    4) User rates difficulty (1-3 maps to quality 5,3,1)
    5) Card is updated and saved
    6) Next card is loaded
    """
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self.queue = app.deck.due_cards()
        self.index = 0  # position in the review queue
        self.build()
        self.load_card()

    def build(self): #Create permanent widgets for review screen
        self.build_header()
        self.build_card_panel()
        self.build_action_buttons()

    def build_header(self): #Build the top bar with the progress label and Home button
        header = tk.Frame(self, bg=COLOURS["bg"])
        header.pack(fill="x", padx=20, pady=(16, 0))
        self.progress_label = tk.Label(header, text="", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"])
        self.progress_label.pack(side="left")
        styled_button(header, "← Home",self.app.show_home).pack(side="right")

    def build_card_panel(self):
        # Outer frame fills available space
        outer = tk.Frame(self, bg=COLOURS["surface"])
        outer.pack(fill="both", expand=True, padx=24, pady=16)
        canvas = tk.Canvas(outer, bg=COLOURS["surface"], highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        self.card_frame = tk.Frame(self, bg=COLOURS["surface"],padx=28, pady=24)
        canvas_window = canvas.create_window((0,0), window=self.card_frame, anchor="nw")
        def on_canvas_configure(e):
            canvas.itemconfig(canvas_window, width=e.width)
        canvas.bind("<Configure>", on_canvas_configure)
        self.type_label = tk.Label(self.card_frame, text="", font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["muted"])
        self.type_label.pack(anchor="w")
        self.tags_label = tk.Label(self.card_frame, text="", font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["muted"])
        self.tags_label.pack(anchor="w")
        self.question_label = tk.Label(self.card_frame, text="", font=FONT_CARD, bg=COLOURS["surface"], fg=COLOURS["text"], justify="left")
        self.question_label.pack(anchor="w", pady=(8, 16), fill="x")

        def update_wraplength(e):
            self.question_label.config(wraplength=e.width - 56)
        self.card_frame.bind("<Configure>", update_wraplength)

        #Text entry for Basic and Cloze cards
        self.answer_var = tk.StringVar()
        self.answer_entry = tk.Entry(self.card_frame, textvariable=self.answer_var, font=FONT_BODY, bg=COLOURS["bg"], fg=COLOURS["text"],insertbackground=COLOURS["text"],relief="flat")
        self.answer_entry.pack(fill="x", ipady=6)
        self.answer_entry.bind("<Return>", lambda e: self.submit())

        #Container for multiple choice option buttons
        self.mc_frame = tk.Frame(self.card_frame, bg=COLOURS["surface"])
        self.mc_frame.pack(fill="x", pady=4)
        self.feedback_label = tk.Label(self.card_frame, text="", font=("Segoe UI", 12, "bold"), bg=COLOURS["surface"], fg=COLOURS["text"])
        self.feedback_label.pack(pady=(12, 0))
        self.reveal_label = tk.Label(self.card_frame, text="", font=FONT_SMALL, wraplength=540, bg=COLOURS["surface"], fg=COLOURS["muted"])
        self.reveal_label.pack()

    def build_action_buttons(self):
        self.action_frame = tk.Frame(self, bg=COLOURS["bg"])
        self.action_frame.pack(pady=8)
        self.submit_btn = styled_button(self.action_frame, "Submit Answer", self.submit, accent=True)
        self.submit_btn.pack(side="left", padx=4)

        #Rating buttons shown only after an answer is submitted
        self.easy_btn = styled_button(self.action_frame, "Easy",lambda: self.rate(5))
        self.hard_btn = styled_button(self.action_frame, "Hard",lambda: self.rate(3))
        self.wrong_btn = styled_button(self.action_frame, "Wrong",lambda: self.rate(1), danger=True)

    def load_card(self): #Display current card or show completion screen
        if not self.queue:
            self.show_no_due()
            return
        if self.index >= len(self.queue):
            self.show_complete()
            return

        card = self.queue[self.index]
        self.progress_label.config(text=f"Card {self.index + 1} of {len(self.queue)}")

        #Clear previous state
        self.answer_var.set("")
        self.feedback_label.config(text="")
        self.reveal_label.config(text="")
        for widget in self.mc_frame.winfo_children():
            widget.destroy()
        card_type = getattr(card, "CARD_TYPE", "Basic") #Show card type label
        tag_str = f"   -   {card.tags}" if card.tags else ""
        self.type_label.config(text=f"{card_type.upper()}{tag_str}")
        self.question_label.config(text=card.question)
        self.show_image(getattr(card, "image_path", "")) #Show image if card has one
        self.question_label.config(text=card.question)
        if isinstance(card, MultipleChoiceCard): #Show appropriate input method
            self.answer_entry.pack_forget()
            self.build_mc_buttons(card)
        else:
            self.answer_entry.pack(fill="x", ipady=6)
            self.answer_entry.focus()
        self.submit_btn.pack(side="left", padx=4) #Show submit, hide rating buttons
        self.easy_btn.pack_forget()
        self.hard_btn.pack_forget()
        self.wrong_btn.pack_forget()

    def show_image(self, image_path): #Display card image if file exists and is a supported format (PNG or GIF)
        if not image_path or not os.path.exists(image_path):
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, image_path)

        if not full_path.lower().endswith((".png", ".gif")):
            tk.Label(self.card_frame, text="Image format not supported. Use PNG or GIF", font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["muted"]).pack()
            return
        try:
            img = tk.PhotoImage(file=full_path)
            label = tk.Label(self.card_frame, image=img, bg=COLOURS["surface"])
            label.image = img
            label.pack(pady=8)
        except Exception:
            tk.Label(self.card_frame, text="Could not load image", font=FONT_SMALL, bg=COLOURS["surface"],fg=COLOURS["muted"]).pack()

    def build_mc_buttons(self, card): #Create 1 button per choice for mc card
        for choice in card.choices:
            #Each button sets answer and submits on click
            btn = tk.Button(self.mc_frame, text=choice, font=FONT_SMALL, relief="flat", bg=COLOURS["button_bg"], fg=COLOURS["muted"],padx=10, pady=5, cursor="hand2",
                            command=lambda c=choice: self.mc_select(c), activebackground=COLOURS["surface"], activeforeground=COLOURS["accent"])
            btn.pack(fill="x", pady=2)

    def mc_select(self, choice): #Handle MC button click
        self.answer_var.set(choice)
        self.submit()

    def submit(self): #Check answer + show feedback and rating buttons
        user_input = self.answer_var.get().strip()
        if not user_input:
            return

        card = self.queue[self.index]
        correct = card.check_answer(user_input)

        if correct:
            self.feedback_label.config(text="✓  Correct!", fg=COLOURS["correct"])
        else:
            self.feedback_label.config(text="✗  Incorrect", fg=COLOURS["wrong"])
            self.reveal_label.config(text=f"Answer: {card.answer}")

        #Switch to rating buttons
        self.submit_btn.pack_forget()
        self.easy_btn.pack(side="left", padx=4)
        self.hard_btn.pack(side="left", padx=4)
        self.wrong_btn.pack(side="left", padx=4)

    def rate(self, quality): #Apply SM-2, save, and move to next card
        card = self.queue[self.index]
        card.update_schedule(quality, self.app.deck.today())
        self.index += 1
        if self.index >= len(self.queue): #When on last card, record the session
            self.app.deck.record_session()
        else:
            self.app.deck.save()
        self.load_card()

   #Session end screens
    def show_complete(self): #Display session complete message
        self.clear_card_area()
        tk.Label(self.card_frame, text="Session complete!", font=FONT_TITLE, bg=COLOURS["surface"], fg=COLOURS["correct"]).pack(pady=30)
        tk.Label(self.card_frame, text=f"Reviewed {len(self.queue)} card(s).", font=FONT_BODY, bg=COLOURS["surface"], fg=COLOURS["muted"]).pack()
        styled_button(self, "Back to Home", self.app.show_home, accent=True).pack(pady=16)

    def show_no_due(self): #Display message when no new cards are due
        self.clear_card_area()
        tk.Label(self.card_frame, text="Nothing due today!", font=FONT_TITLE, bg=COLOURS["surface"], fg=COLOURS["correct"]).pack(pady=30)
        tk.Label(self.card_frame, text="Add more cards or come back tomorrow.", font=FONT_BODY, bg=COLOURS["surface"], fg=COLOURS["muted"]).pack()
        styled_button(self, "Back to Home", self.app.show_home, accent=True).pack(pady=16)

    def clear_card_area(self): #Remove all dynamic widgets from card frame
        for widget in self.card_frame.winfo_children():
            widget.destroy()
        self.action_frame.pack_forget()

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
