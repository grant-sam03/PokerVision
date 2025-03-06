# Poker Tracker

## Overview

`poker_tracker.py` is a comprehensive Python-based application designed to import, parse, and analyze poker hand histories. The tool combines a graphical user interface (GUI) built with Tkinter, a robust SQLite database for data storage, and matplotlib for interactive visualization. It is ideal for tracking and reviewing poker performance, offering detailed analysis of hand actions, profit calculations, and more.

## Features

- **Hand History Import:**  
  - Supports importing hand histories from plain text (TXT) files and ZIP archives.
  - Automatically extracts and parses hand data, including hand IDs, stakes, timestamps, player positions, hole cards, and action sequences for GGPoker Cash Games.

- **Database Integration:**  
  - Creates and manages a local SQLite database (`poker_data.db`) to store detailed hand information.
  - Stores various metrics such as total pot, rake, hero profit, hero contributions, and adjusted profit (including rakeback).

- **Graphical User Interface:**  
  - **Import / Hands Tab:** Import hand history files and view a sortable, filterable list of hands.
  - **Graph Tab:** Visualize statistical insights like profit trends and Big Blind (BB) performance.
  - **Range Analysis Tab:** Analyze starting hand ranges and preflop scenarios.
  - **LeakHelper Tab:** Tools to help identify potential areas for improvement in your game.

- **Advanced Hand Analysis:**  
  - Deduction of hero position based on button position in 6-max games.
  - Calculation of hero contributions and profit, taking into account factors like rake, jackpots, and multiple showdown scenarios.
  - Determination of preflop scenarios (e.g., open, 3bet, 4bet) and opportunities such as raising first in.

## Sample Data

The package includes **12,000 hands of sample data** to help you explore and test the application’s features right away. This sample data provides a robust dataset for analyzing performance and visualizing trends without needing to immediately import your own hand histories.

## Requirements

- **Python 3.x**
- **SQLite3** (usually bundled with Python)
- **Tkinter** (typically included with Python installations)
- **NumPy**
- **Matplotlib**

Other standard libraries such as `os`, `re`, `json`, `zipfile`, `tempfile`, and `datetime` are used in the project.

## Installation and Setup

1. **Clone or Download the Repository:**  
   Ensure that `poker_tracker.py` and the accompanying sample data are located in your project directory.

2. **Install Dependencies:**  
   If necessary, install the required packages using pip:
   ```bash
   pip install numpy matplotlib
(Note: Tkinter and SQLite3 are usually available by default with Python.)

Run the Application:
Launch the app by running:
bash
Copy
python poker_tracker.py
The GUI will open, allowing you to import hand histories and begin your analysis.
Usage
Importing Hand Histories:
Navigate to the "Import / Hands" tab to load hand history files. The application supports both TXT and ZIP file formats.

Analyzing Data:

Use the "Graph" tab to view interactive charts and statistics.
Filter and sort hands based on criteria like stake, date, or profit.
Explore range analysis to see detailed metrics on starting hand performance.
Customizing Settings:
Adjust settings such as the rakeback percentage to tailor profit calculations and other statistics to your specific needs.
