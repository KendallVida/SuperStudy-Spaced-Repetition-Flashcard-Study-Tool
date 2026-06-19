import json
import math
import os
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk

class Flashcard:
    """
    Base class for all types of flashcard
    Uses SM-2 scheduling algorithm
    """

    def __init__(self, question, answer, tags=""):
        #Card content
        self.question = question
        self.answer = answer
        self.tags = tags

        #SM-2 spaced-repetition fields
        self.interval = 1       # Days until next review
        self.repetitions = 0    # Consecutive correct answers
        self.easiness = 2.5     # Difficulty multiplier (min 1.3)
        self.next_review = date.today().isoformat()

    #  Scheduling

    def is_due(self):
        return date.today() >= date.fromisoformat(self.next_review) # Return true if card is due for review today

    def update_schedule(self, quality):
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

        # Adjust how easy card is based on recall quality using SM-2 Formula:
        #EF' = EF+(0.1-(5-q) * (0.08+(5-q) * 0.02))
        self.easiness = max(1.3, self.easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        self.next_review = (date.today() + timedelta(days=self.interval)).isoformat()

    # Answer Checking
    def check_answer(self, user_input):
        # Return True if input is correct
        return user_input.strip().lower() == self.answer.strip().lower()

    # Convert to/from plain dict to JSON

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
        }

    @classmethod
    def from_dict(cls, data):
        card = cls(data["question"], data["answer"], data.get("tags", ""))
        card.interval = data["interval"]
        card.repetitions = data["repetitions"]
        card.easiness = data["easiness"]
        card.next_review = data["next_review"]
        return card

class BasicCard(Flashcard):
    CARD_TYPE = "Basic"

class MultipleChoiceCard(Flashcard):
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
    def from_dict(cls, data):
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

class ClozeCard(Flashcard):
    CARD_TYPE = "Cloze"

CARD_CLASSES = {"BasicCard": BasicCard,
                "MultipleChoiceCard": MultipleChoiceCard,
                "ClozeCard": ClozeCard
                }

def card_from_dict(data):
    #Reconstructs correct flashcard subclass from a saved dictionary
    cls = CARD_CLASSES.get(data.get("type"), BasicCard)
    return cls.from_dict(data)

class Deck:
    #Collection of Flashcards object with file persistence

    SAVE_FILE = "flashcard_data.json"

    def __init__(self):
        self.cards = []

    def add_card(self, card):
        #Add flashcard to the deck
        self.cards.append(card)

    def remove_card(self, index):
        #Remove card at a given list index
        if 0 <= index < len(self.cards):
            self.cards.pop(index)

    def due_cards(self):
        #Return a list of cards that are due for review today
        return [card for card in self.cards if card.is_due()]

    def save(self):
        #Serialise cards to JSON file
        data = [card.to_dict() for card in self.cards]
        with open(self.SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        #Load cards from JSON file
        if not os.path.exists(self.SAVE_FILE):
            return
        with open(self.SAVE_FILE, "r") as f:
            data=json.load(f)
            self.cards = [card_from_dict(d) for d in data]

COLOURS = {
    "bg": "#1e1e2e",       #dark background
    "surface": "#2a2a3e",  #card background
    "accent": "#7c6af7",   #accent colour
    "correct": "#56cfb2",  #green for correct
    "wrong": "#e06c75",    #red for incorrect
    "text": "#cdd6f4",     #main text
    "muted": "#6c7086",    #secondary text
    "button_bg": "#3b3b52" #button background
}

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_CARD = ("Segoe UI", 14)

def styled_button(parent, text, command, accent=False, danger=False):
    bg = COLOURS["accent"] if accent else (COLOURS["wrong"] if danger else COLOURS["button_bg"])
    return tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=COLOURS["text"],
        font = FONT_BODY, relief="flat",
        padx=16, pady=8, cursor="hand2",
        activebackground=COLOURS["surface"],
        activeforeground=COLOURS["accent"]
    )

class App(tk.Tk):
    #Root app window; Manages deck and switches between "Homeview" (shows stats and navigation), "Manageview" (add/delete cards), and "ReviewView" (review due cards)
    def __init__(self):
        super().__init__()
        self.title("Flashcard App")
        self.geometry("700x520") #Temporary; Done for now to allow for easier formatting as final UI configuration is decided as ratios between components is constant
        self.resizable(False, False)
        self.configure(bg=COLOURS["bg"])
        self.deck = Deck()
        self.deck.load()
        self.container = tk.Frame(self, bg=COLOURS["bg"])
        self.container.pack(fill="both", expand=True)
        self.show_home()

    #View Switching
    def show_home(self):
        self._clear()
        Home(self.container, self).pack(fill="both", expand=True)

    def show_manage(self):
        self._clear()
        ManageView(self.container, self).pack(fill="both", expand=True)

    def show_review(self):
        self._clear()
        ReviewView(self.container, self).pack(fill="both", expand=True)

    def _clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()

class Home(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self._build()

    def _build(self):
        #Title
        tk.Label(self, text="Flashcards", font=FONT_TITLE, bg=COLOURS["bg"], fg=COLOURS["accent"]).pack(pady=(36,4))

        #Stats panel
        stats_frame = tk.Frame(self, bg=COLOURS["surface"], padx=24, pady=16)
        stats_frame.pack(pady=28, ipadx=10)
        total = len(self.app.deck.cards)
        due = len(self.app.deck.due_cards())
        new = sum(1 for c in self.app.deck.cards if c.repetitions == 0)
        self.stat_row(stats_frame, "total cards", total, COLOURS["text"], 0)
        self.stat_row(stats_frame, "due today", due, COLOURS["accent"], 1)
        self.stat_row(stats_frame, "new (unseen)", new, COLOURS["correct"], 2)

        #Navigation
        styled_button(self, "start review", self.app.show_review, accent=True).pack(pady=(0,12))
        styled_button(self, "manage_cards", self.app.show_manage).pack()

    def stat_row(self, parent, label, value, colour, row):
        tk.Label(parent, text=label, font=FONT_BODY, bg=COLOURS["surface"], fg=COLOURS["muted"]).grid(row=row, column=0)
        tk.Label(parent, text=str(value), font=("Segoe UI", 12, "bold"), bg=COLOURS["surface"], fg=colour).grid(row=row, column=1, sticky="e")

class ManageView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app
        self._build()

    def _build(self):
        #Header
        header = tk.Frame(self, bg=COLOURS["bg"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        tk.Label(header, text="manage cards", font=FONT_TITLE, bg=COLOURS["bg"], fg=COLOURS["text"]).pack(side="left")
        styled_button(header, "home", self.app.show_home).pack(side="right")

        #Card List
        tree_frame = tk.Frame(self, bg=COLOURS["bg"])
        tree_frame.pack(fill="both", expand=True, padx=20)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview", background=COLOURS["surface"], foreground=COLOURS["text"],
                        fieldbackground=COLOURS["surface"], rowheight=28, font=FONT_SMALL)
        style.configure("Custom.Treeview.Heading", background=COLOURS["button_bg"], foreground=COLOURS["accent"], font=("Segoe UI", 10, "bold"))
        self.tree = ttk.Treeview(tree_frame, columns=("type", "question", "due"), show="headings", style="Custom.Treeview", height=10)
        self.tree.heading("type", text="type")
        self.tree.heading("question", text="question")
        self.tree.heading("due", text="due")
        self.tree.column("type", width=130, anchor="w")
        self.tree.column("question", width=360, anchor="w")
        self.tree.column("due", width=100, anchor="center")
        self.refresh_list()

        #Bottom row
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
            self.tree.insert(" ", "end", values=(card_type, card.questions[:55], due_str))

    def delete_selected(self): #Remove selected card from deck and save
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Please select a card to delete.")
            return
        row_index = self.tree.index(selected[0])
        self.app.deck.remove_card(row_index)
        self.app.deck.save()
        self.refresh_list()

class AddCardDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app

class ReviewView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
