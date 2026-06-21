# Installation Instuctions
### Step 1 - Check Python installation
Open a terminal or command prompt and run `python --version`.\
If you see `Python 3.8` or higher, skip to step 2.\
If a lower version appears, try `python3 --version`.\
If python is not installed, download it from https://www.python.org/downloads.

## Step 2 - Check Tkinter installation
Tkinter is Pythons built in GUI library and comes included with most Python installations. \
You can ensure tkiner is installed on your machine by running `python -m tkinter` in your terminal / command prompt.\
If it is installed, a small graphical window should pop up on screen.

## Step 3 - Run the program
Run the main python file of `flashcardapp.py` directly to open the program and begin use.

# Operation Instructions & Features
To create a flashcard, press the "manage card" button on the homepage and then press "add card" on the manage card page.\
You are then prompted with 3 card types, basic, multiple choice, and cloze.\
Basic flashcards only require a question and an answer.\
Multiple choice flashcards allow multiple options differentiated by line in an input box, with the correct option being differentiated by a *.\
Cloze cards feature a blank word in the question, with the answer being used to fill in the blank spot.\
Cloze and Basic cards are functionally the same, with the distinction being a way of catagorising the flashcards.\
Tags can be assigned to cards in order to catagorise them (e.g Maths, English, Physics).\
Images can also be assigned to flashcards. They can only be .png and .gif files.\
Card information including the type, question, tags, and next review date can be viewed on the manage cards page.\
On the home page, you can see your due flashcards, the flashcards due today, the new (unseen) flashcards, and your daily streak.\
After completing a flashcard, you will be prompted with whether the answer was correct or not.\
You then choose your difficulty completing the flashcard (easy, hard, wrong), which will determine when it is next to be reviewed.\
There is a debug function at the bottom of the page allowing for the incrementation of the functional date.\
This also allows you to check how many flashcards you will have due on future days using the currently saved information.\
Cards should not be done while this debugging tool is in use since it will affect saved flashcard information and will impact the learning experience.



