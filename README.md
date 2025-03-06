# PokerVision

A robust Python application for importing, parsing, and analyzing poker hand histories. Designed with a sleek graphical interface and powerful statistical analysis tools, Poker Tracker empowers you to dive deep into your game performance.

---

## Overview

PokerVision streamlines the process of collecting and analyzing hand histories. Built on Python with a Tkinter GUI, it leverages a local SQLite database to store comprehensive details for each hand, enabling detailed profit analysis, positional insights, and performance tracking.

Below are a few screenshots of the interface in action:

![Graph Tab](images/Graph.png "Graph Tab")
*Displays the cumulative profit chart over 12,000 sample hands, with some key stats.*

![Range Tab - Facing Raise](images/Range.png "Range Tab - Facing Raise")
*Illustrates raise/call/fold frequencies in a color-coded 13x13 matrix.*

![LeakHelper Tab 1](images/Leaks.png "LeakHelper Tab 1")
*Shows a grid of hands with profit/loss color-coding for quick leak detection.*

---

## Key Features

- **Efficient Hand Importing:**  
  Import hand histories from TXT and ZIP files. The application automatically extracts and parses essential data such as hand IDs, stakes, timestamps, player positions, hole cards, and action sequences.

- **Comprehensive Data Management:**  
  - Uses an SQLite database (`poker_data.db`) to store extensive hand details.  
  - Tracks metrics including total pot, rake, hero contributions, and profit calculations (with adjustable rakeback).

- **User-Friendly Interface:**  
  - **Import / Hands Tab:** Quickly load and view hand histories with sorting and filtering options.
  - **Graph Tab:** Visualize performance trends and profit metrics using interactive charts.
  - **Range Analysis Tab:** Explore starting hand ranges and preflop scenarios.
  - **LeakHelper Tab:** Identify potential weaknesses in your game.

- **Advanced Analysis Tools:**  
  - Deduces player position based on button placement in 6-max games.
  - Calculates detailed profit metrics, including adjusted profit after considering rakeback.
  - Determines key preflop scenarios such as open raises, 3-bets, and 4-bets.

- **Extensive Sample Data:**  
  Comes pre-loaded with **12,000 hands of sample data** to get you started immediately on performance analysis.

---

## Installation

### Prerequisites
- **Python 3.x**
- **SQLite3** (included with Python)
- **Tkinter** (included with Python)
- **NumPy**
- **Matplotlib**

### Setup Steps
1. **Download or Clone:**  
   Ensure `pokervision.py` and the sample dataset are in your working directory.

2. **Install Dependencies:**  
   Open your terminal and run:
   ```bash
   pip install numpy matplotlib
