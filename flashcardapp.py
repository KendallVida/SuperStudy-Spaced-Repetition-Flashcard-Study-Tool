import json as _json
import os
import sqlite3
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk, filedialog


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

class Flashcard:
    """
    Base class for all flashcard types
    Stores question, answer, scheduling data (done using the SM-2 algorithm) and optional tags applied by the user
    """
    def __init__(self, question, answer, tags="", image_path=""):
        #Card content
        self.question = question #e.g "What is the capital of Australia?"
        self.answer = answer #e.g "Canberra"
        self.tags = tags #e.g "maths, english, physics"
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
        #EF' = EF+(0.1-(5-q) * (0.08+(5-q) * 0.02))
        self.easiness = max(1.3, self.easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        self.next_review = (today + timedelta(days=self.interval)).isoformat()

    #Answer Checking
    def check_answer(self, user_input):
        # Return True if input is correct
        return user_input.strip().lower() == self.answer.strip().lower()

class BasicCard(Flashcard): #Simple question and answer card
    CARD_TYPE = "Basic"

    def __init__(self, question, answer, tags="", image_path=""):
        super().__init__(question, answer, tags)
        self.image_path = image_path

class MultipleChoiceCard(Flashcard): #Multiple choice card with list of options
    CARD_TYPE = "Multiple Choice"

    def __init__(self, question, answer, choices, tags=""):
        super().__init__(question, answer, tags)
        self.choices = choices  # List of possible answer options

    def check_answer(self, user_input):
        return user_input.strip().lower() == self.answer.strip().lower()

class ClozeCard(Flashcard): #A "fill in the blanks" card which contains "____" where the answer should be placed
    CARD_TYPE = "Cloze"

    def __init__(self, question, answer, tags="", image_path=""):
        super().__init__(question, answer, tags)
        self.image_path = image_path

class Database:
    """
    Manages the SQlite connection and all database operations
    Two Tables:
    decks - one row per deck (name, stream last_session_date)
    cards - one row per card, linked to a deck via deck_id foreign key
    """

    DB_FILE = "flashcards.db"

    def __init__(self):
        self.conn = sqlite3.connect(self.DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.debug_date = None #Used by debug panel to simulate a date
        self.create_tables()

    def create_tables(self): #Create decks and cards tables if they don't already exist
        self.conn.executescript("""
                    CREATE TABLE IF NOT EXISTS decks (
                        id                INTEGER PRIMARY KEY AUTOINCREMENT,
                        name              TEXT NOT NULL UNIQUE,
                        last_session_date TEXT,
                        streak            INTEGER DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS cards (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        deck_id     INTEGER NOT NULL,
                        type        TEXT NOT NULL,
                        question    TEXT NOT NULL,
                        answer      TEXT NOT NULL,
                        tags        TEXT DEFAULT '',
                        image_path  TEXT DEFAULT '',
                        choices     TEXT DEFAULT '',
                        interval    INTEGER DEFAULT 1,
                        repetitions INTEGER DEFAULT 0,
                        easiness    REAL DEFAULT 2.5,
                        next_review TEXT NOT NULL,
                        FOREIGN KEY (deck_id) REFERENCES decks(id)
                    );
                """)
        self.conn.commit()

    def today(self): #Return current date, or debug date if one has been set
        return self.debug_date if self.debug_date else date.today()

    def create_deck(self, name): #Insert new deck and return its assigned id
        cursor = self.conn.execute("INSERT INTO decks (name) VALUES (?)", (name,))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_decks(self): #Return all decks as a list of Row objects
        return self.conn.execute("SELECT * FROM decks").fetchall()

    def get_deck(self, deck_id): #Return a single deck row by id
        return self.conn.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()

    def update_deck_streak(self, deck_id, streak, last_session_date): #Update daily streak and last session date for deck
        self.conn.execute("UPDATE decks SET streak = ?, last_session_date = ? WHERE id = ?", (streak, last_session_date, deck_id))
        self.conn.commit()

    def delete_deck(self, deck_id): #Delete a deck and all its cards
        self.conn.execute("DELETE FROM cards WHERE deck_id = ?", (deck_id,))
        self.conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
        self.conn.commit()

    def deck_stats(self, deck_id): #Return total, due, and new card counts for a deck
        today = self.today().isoformat()
        total = self.conn.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ?", (deck_id,)).fetchone()[0]
        due = self.conn.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND next_review <= ?", (deck_id, today)).fetchone()[0]
        new = self.conn.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND repetitions = 0", (deck_id,)).fetchone()[0]
        return {"total": total, "due": due, "new": new}

    def add_card(self, deck_id, card): #Insert a new card into the database linked to the given deck
        choices_str = _json.dumps(card.choices) if hasattr(card, "choices") else ""
        self.conn.execute("INSERT INTO cards (deck_id, type, question, answer, tags, image_path, choices, interval, repetitions, easiness, next_review) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",(
            deck_id, card.__class__.__name__,
            card.question, card.answer, card.tags, getattr(card, "image_path", ""), choices_str, card.interval, card.repetitions, card.easiness, card.next_review
        ))
        self.conn.commit()

    def get_due_cards(self, deck_id): #Return all cards due for review today in a deck
        today = self.today().isoformat()
        rows = self.conn.execute("SELECT * FROM cards WHERE deck_id = ? AND next_review <= ?", (deck_id, today)).fetchall()
        return [self.row_to_card(r) for r in rows]

    def get_all_cards(self, deck_id): #Return all cards in a deck as Flashcard objects
        rows = self.conn.execute("SELECT * FROM cards WHERE deck_id = ?",(deck_id,)).fetchall()
        return [self.row_to_card(r) for r in rows]

    def update_card_schedule(self, card_id, interval, repetitions, easiness, next_review): #Update SM-2 scheduling fields after a review
        self.conn.execute("""
            UPDATE cards
            SET interval = ?, repetitions = ?, easiness = ?, next_review = ?
            WHERE id = ?
            """, (interval, repetitions, easiness, next_review, card_id))
        self.conn.commit()

    def delete_card(self, card_id): #Delete a single card by its db id
        self.conn.execute("DELETE FROM cards WHERE id = ?",(card_id,))
        self.conn.commit()

    def row_to_card(self, row): #Convert a database row into the correct Flashcard subclass
        cls = CARD_CLASSES.get(row["type"], BasicCard)
        if cls == MultipleChoiceCard:
            choices = _json.loads(row["choices"]) if row["choices"] else []
            card = MultipleChoiceCard(row["question"], row["answer"], choices, row["tags"])
        else:
            card = cls(row["question"], row["answer"], row["tags"], row["image_path"])
        card.interval = row["interval"]
        card.repetitions = row["repetitions"]
        card.easiness = row["easiness"]
        card.next_review = row["next_review"]
        card.db_id = row["id"]
        return card

    def record_session(self, deck_id): #Update the streak for the given deck after a completed review session
        today = self.today()
        today_str = today.isoformat()
        deck = self.get_deck(deck_id)
        streak = deck["streak"]
        last = deck["last_session_date"]

        if last is None:
            streak = 1
        else:
            gap = (today - date.fromisoformat(last)).days
            if gap == 0:
                return
            elif gap == 1:
                streak += 1
            else:
                streak = 1

        self.update_deck_streak(deck_id, streak, today_str)

CARD_CLASSES = {"BasicCard": BasicCard, "MultipleChoiceCard": MultipleChoiceCard, "ClozeCard": ClozeCard}

def styled_button(parent, text, command, accent=False, danger=False): #Returns a consistently styled tkinter button
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
    """
    Root application window
    Manages database and switches between views
    """
    def __init__(self):
        super().__init__()
        self.title("Flashcard App")
        self.geometry("960x720")
        self.minsize(600, 440) #Prevents window becoming too small to use
        self.configure(bg=COLOURS["bg"])
        self.db = Database()
        self.active_deck = None
        self.container = tk.Frame(self, bg=COLOURS["bg"])
        self.container.pack(fill="both", expand=True)
        self.show_deck_select()

    #View Switching
    def show_deck_select(self): #Replace current view with deck selection screen
        self.clear()
        DeckSelectView(self.container, self).pack(fill="both", expand=True)

    def show_home(self): #Replace current view with home page
        self.clear()
        Home(self.container, self).pack(fill="both", expand=True)

    def show_manage(self): #Replace current view with card management page
        self.clear()
        ManageView(self.container, self).pack(fill="both", expand=True)

    def show_review(self): #Replace current view with review page
        self.clear()
        ReviewView(self.container, self).pack(fill="both", expand=True)

    def clear(self): #Destroy all widgets in frame
        for widget in self.container.winfo_children():
            widget.destroy()

class DeckSelectView(tk.Frame):
    """
    Deck selection screen shown on launch and when returning from a deck.
    Lists all saved decks and allows creating or deleting them.
    """
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self.build_deck_select()

    def build_deck_select(self):
        inner = tk.Frame(self, bg=COLOURS["bg"])
        inner.pack(expand=True)
        tk.Label(inner, text="Flashcards", font=FONT_TITLE, bg=COLOURS["bg"], fg=COLOURS["accent"]).pack(pady=(0,4))
        tk.Label(inner, text="Select a deck to study", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(pady=(0,16))

        self.list_frame = tk.Frame(inner, bg=COLOURS["bg"])
        self.list_frame.pack()
        self.refresh_deck_list()

        #New deck creation row
        new_frame = tk.Frame(inner, bg=COLOURS["bg"])
        new_frame.pack(pady=(16,0))
        tk.Label(new_frame, text="New deck name:", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(side="left", padx=(0,8))
        self.new_deck_entry = tk.Entry(new_frame, font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["text"], insertbackground=COLOURS["text"], relief="flat")
        self.new_deck_entry.pack(side="left", ipady=4, padx=(0,8))
        styled_button(new_frame, "Create", self.create_deck, accent=True).pack(side="left")

    def refresh_deck_list(self): #Clear deck list and refill from db
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        decks = self.app.db.get_all_decks()
        if not decks:
            tk.Label(self.list_frame, text="No decks yet - create one below!", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack()
            return
        for deck in decks:
            stats = self.app.db.deck_stats(deck["id"])
            row = tk.Frame(self.list_frame, bg=COLOURS["surface"], padx=12, pady=8)
            row.pack(fill="x", pady=3)
            info = tk.Frame(row, bg=COLOURS["surface"])
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=deck["name"], font=("Segoe UI", 12, "bold"), bg=COLOURS["surface"], fg=COLOURS["text"]).pack(anchor="w")
            tk.Label(info,
                    text=f"{stats['total']} cards - "
                     f"{stats['due']} due - "
                     f"{deck['streak']} day streak",
                     font=FONT_SMALL, bg=COLOURS["surface"],
                     fg=COLOURS["muted"]).pack(anchor="w")
            styled_button(row, "Open", lambda d=deck: self.open_deck(d), accent=True).pack(side="right", padx=(8,0))
            styled_button(row, "Delete", lambda d=deck: self.delete_deck(d), danger=True).pack(side="right")

    def open_deck(self, deck): #Set active deck; move to homepage
        self.app.active_deck = deck
        self.app.show_home()

    def create_deck(self): #Create new deck with entered name
        name = self.new_deck_entry.get().strip()
        if not name:
            messagebox.showwarning("No name", "Please enter a deck name")
            return
        try:
            deck_id = self.app.db.create_deck(name)
            deck = self.app.db.get_deck(deck_id)
            self.open_deck(deck)
        except sqlite3.IntegrityError:
            messagebox.showwarning("Duplicate Name", f"A deck called '{name} already exists'")

    def delete_deck(self, deck): #Confirm then delete selected deck and all its cards
        confirmed = messagebox.askyesno("Delete Deck",
                                        f"Delete '{deck['name']}' and all its cards? (This cannot be undone)")
        if confirmed:
            self.app.db.delete_deck(deck["id"])
            self.refresh_deck_list()

class Home(tk.Frame):
    """
    Home screen showing deck statistics and navigation
    """
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self.build_home()
        self.debug_date_label = None

    def build_home(self):
        inner = tk.Frame(self, bg=COLOURS["bg"]) #Centred inner frame
        inner.pack(expand=True)
        tk.Label(inner, text="Flashcards", font=FONT_TITLE, bg=COLOURS["bg"], fg=COLOURS["accent"]).pack() #Title
        tk.Label(inner, text=f"Current deck: {self.app.active_deck['name']}", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(pady=(4,0)) #loaded deck text
        #Stats panel - fetched via single database queries
        stats_frame = tk.Frame(inner, bg=COLOURS["surface"], padx=24, pady=16)
        stats_frame.pack(pady=28, ipadx=10)
        deck_id = self.app.active_deck["id"]
        stats = self.app.db.deck_stats(deck_id)
        streak = self.app.db.get_deck(deck_id)["streak"]
        self.stat_row(stats_frame, "total cards", stats["total"], COLOURS["text"], 0)
        self.stat_row(stats_frame, "due today", stats["due"], COLOURS["accent"], 1)
        self.stat_row(stats_frame, "new (unseen)", stats["new"], COLOURS["correct"], 2)
        self.stat_row(stats_frame, "Daily Streak", streak, "#ffaf4a", 3)
        #Navigation
        styled_button(inner, "start review", self.app.show_review, accent=True).pack(pady=(0,12)) #Begin flashcard review
        styled_button(inner, "manage cards", self.app.show_manage, accent=True).pack() #Open ManageView to manage flashcards
        styled_button(inner, "all decks", self.app.show_deck_select).pack(pady=(12,0))

        debug_frame = tk.Frame(self, bg=COLOURS["bg"])
        debug_frame.pack(side="bottom", pady=16)
        self.build_debug_panel(debug_frame) #Create debug panel at bottom of page

    def stat_row(self, parent, label, value, colour, row):
        tk.Label(parent, text=label, font=FONT_BODY, bg=COLOURS["surface"], fg=COLOURS["muted"]).grid(row=row, column=0)
        tk.Label(parent, text=str(value), font=("Segoe UI", 12, "bold"), bg=COLOURS["surface"], fg=colour).grid(row=row, column=1, sticky="e")

    def build_debug_panel(self, debug_frame): #Debug panel for shifting the simulated date
        tk.Label(debug_frame, text="Debug - simulated date:", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(side="left", padx=(0,6))
        #Show the active date
        active = self.app.db.today()
        self.debug_date_label = tk.Label(debug_frame, text=active.isoformat(), font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["accent"] if self.app.db.debug_date else COLOURS["muted"])
        self.debug_date_label.pack(side="left", padx=(0,8))
        #Debugging buttons
        styled_button(debug_frame, "- Day", lambda: self.shift_date(-1), accent=True).pack(side="left", padx=2)
        styled_button(debug_frame, "+ Day", lambda: self.shift_date(1), accent=True).pack(side="left", padx=2)
        styled_button(debug_frame, "Reset", lambda: self.reset_date(), accent=True).pack(side="left", padx=2)

    def shift_date(self, days): #Move simulated time forward or back
        current = self.app.db.today()
        self.app.db.debug_date = current + timedelta(days=days)
        self.app.show_home() #Refresh stats to reflect new date

    def reset_date(self): #Clear the debug date override and return to the real date
        self.app.db.debug_date = None
        self.app.show_home()

class ManageView(tk.Frame):
    """
    Card management screen. Allows users to view card list, add new cards, and delete existing ones
    """
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self.build_manage()

    def build_manage(self): #build screen layout
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
        deck_id = self.app.active_deck["id"]
        for card in self.app.db.get_all_cards(deck_id):
            due_str = "Today" if card.is_due(self.app.db.today()) else card.next_review
            card_type = getattr(card, "CARD_TYPE", "Basic")
            self.tree.insert("", "end", values=(card_type, card.question[:55], card.tags or "-", due_str), iid=str(card.db_id))

    def delete_selected(self): #Remove selected card from db
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Please select a card to delete.")
            return
        card_id = int(selected[0])
        self.app.db.delete_card(card_id)
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
        self.build_add_dialog()

    def build_add_dialog(self):
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
        styled_button(self, "Save Card",self.save, accent=True).pack(pady=14) #Save button

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
            tk.Label(image_row, text="Image(optional):", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"]).pack(side="left")
            tk.Label(image_row, textvariable=self.image_path_var, font=FONT_SMALL, bg=COLOURS["bg"],fg=COLOURS["muted"]).pack(side="left", pady=6)
            styled_button(image_row, "Browse...", self.pick_image).pack(side="left")

    def save(self): #Validate inputs and save
        card_type = self.card_type_var.get()
        question = self.q_entry.get("1.0", "end").strip()
        tags = self.tags_entry.get().strip()

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

        self.app.db.add_card(self.app.active_deck["id"], card)
        self.on_save()
        self.destroy()

    def build_basic_card(self, question, tags): #Construct a BasicCard from the form
        answer = self.a_entry.get().strip()
        if not answer:
            messagebox.showwarning("Missing Field", "Please enter an answer.")
            return None
        return BasicCard(question, answer, tags, self.image_path_var.get())

    def build_mc_card(self, question, tags): #Construct an MC Card from the choices text box
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
        self.queue = app.db.get_due_cards(app.active_deck["id"])
        self.index = 0  # position in the review queue
        self.session_log = []
        self.build_review()
        self.load_card()

    def build_review(self): #Create permanent widgets for review screen
        self.build_header()
        self.build_card_panel()
        self.build_action_buttons()

    def build_header(self): #Build the top bar with the progress label and Home button
        header = tk.Frame(self, bg=COLOURS["bg"])
        header.pack(fill="x", padx=20, pady=(16, 0))
        self.progress_label = tk.Label(header, text="", font=FONT_SMALL, bg=COLOURS["bg"], fg=COLOURS["muted"])
        self.progress_label.pack(side="left")
        styled_button(header, "Home",self.app.show_home,accent=True).pack(side="right")

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
        self.question_label = tk.Label(self.card_frame, text="", font=FONT_CARD, bg=COLOURS["surface"], fg=COLOURS["text"], justify="left")
        self.question_label.pack(anchor="w", pady=(8, 16), fill="x")

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
        self.image_label = None

    def build_action_buttons(self):
        self.action_frame = tk.Frame(self, bg=COLOURS["bg"])
        self.action_frame.pack(pady=8)
        self.submit_btn = styled_button(self.action_frame, "Submit Answer", self.submit, accent=True)
        self.submit_btn.pack(side="left", padx=4)

        #Rating buttons shown only after an answer is submitted
        self.easy_btn = styled_button(self.action_frame, "Easy",lambda: self.rate(5), accent=True)
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
        # Destroy previous image label if one exists
        if self.image_label is not None:
            self.image_label.destroy()
            self.image_label = None

        if not image_path:
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, image_path)

        if not os.path.exists(full_path):
            return
        if not full_path.lower().endswith((".png", ".gif")):
            self.image_label = tk.Label(self.card_frame, text="Image format not supported. Use PNG or GIF", font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["muted"])
            self.image_label.pack()
            return
        try:
            img = tk.PhotoImage(file=full_path)
            self.image_label = tk.Label(self.card_frame, image=img, bg=COLOURS["surface"])
            self.image_label.image = img  # keep reference
            self.image_label.pack(pady=8)

        except Exception:
            self.image_label = tk.Label(self.card_frame, text="Could not load image", font=FONT_SMALL, bg=COLOURS["surface"], fg=COLOURS["muted"])
            self.image_label.pack()
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

        #Record this review as a row in the 2D array
        #Structure: [question, card type, was correct, quality given, date]
        was_correct = quality >= 3
        self.session_log.append([card.question[:40], getattr(card, "CARD_TYPE", "Basic"), "Correct" if was_correct else "Incorrect", quality, self.app.db.today().isoformat()])


        card.update_schedule(quality, self.app.db.today())
        self.app.db.update_card_schedule(card.db_id, card.interval, card.repetitions, card.easiness, card.next_review)
        self.index += 1
        if self.index >= len(self.queue): #When on last card, record the session
            self.app.db.record_session(self.app.active_deck["id"])
            self.app.active_deck = self.app.db.get_deck(self.app.active_deck["id"])
        self.load_card()

   #Session end screens
    def show_complete(self): #Display session complete message
        self.clear_card_area()
        tk.Label(self.card_frame, text="Session complete!", font=FONT_TITLE, bg=COLOURS["surface"], fg=COLOURS["correct"]).pack(pady=30)
        #Count correct from the 2D array, iterating over each row
        correct_count = sum(1 for row in self.session_log if row[2] == "Correct")
        total = len(self.session_log)
        tk.Label(self.card_frame, text=f"{correct_count} of {total} correct", font=FONT_BODY, bg=COLOURS["surface"], fg=COLOURS["muted"]).pack(pady=(0,12))
        #Build treeview to display the 2D array as a table
        tree_frame = tk.Frame(self.card_frame, bg=COLOURS["surface"])
        tree_frame.pack(fill="x", padx=8)
        tree = ttk.Treeview(tree_frame, columns=("question", "type", "result", "quality"), show="headings", style="Custom.Treeview", height=min(len(self.session_log), 6))
        tree.heading("question", text="Question")
        tree.heading("type", text="Type")
        tree.heading("result", text="Result")
        tree.heading("quality", text="Quality")
        tree.column("question", width=260, anchor="w", minwidth=100)
        tree.column("type", width=110, anchor="w", minwidth=60)
        tree.column("result", width=80, anchor="center", minwidth=60)
        tree.column("quality", width=60, anchor="center", minwidth=40)
        tree.pack(fill="x")

        #Interate over the 2D array
        for row in self.session_log:
            tree.insert("", "end", values=(
                row[0], #question
                row[1], #card type
                row[2], #correct/incorrect
                row[3], #quality rating
            ))

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
