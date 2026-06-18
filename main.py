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
    "text": "cdd6f4",     #main text
    "muted": "6c7086",    #secondary text
    "button_bg": "3b3b52" #button background
}

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_CARD = ("Segoe UI", 14)

class App(tk.Tk):
    #Root app window; Manages deck and switches between "Homeview" (shows stats and navigation), "Manageview" (add/delete cards), and "ReviewView" (review due cards)
    def __init__(self):
        super().__init__()
        self.title("Flashcard App")
        self.geometry("700x520")
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
        HomeView(self.container, self).pack(fill="both", expand=True)

    def show_manage(self):
        self._clear()
        ManageView(self.container, self).pack(fill="both", expand=True)

    def show_review(self):
        self._clear()
        ReviewView(self.container, self).pack(fill="both", expand=True)

    def _clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()

class HomeView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app

class ManageView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOURS["bg"])
        self.app = app

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

