# PokerVision

A robust Python application for importing, parsing, and analyzing poker hand histories. Designed with a sleek graphical interface and powerful statistical analysis tools, Poker Tracker empowers you to dive deep into your game performance.

---

## Overview

PokerVision streamlines the process of collecting and analyzing hand histories. Built on Python with a Tkinter GUI, it leverages a local SQLite database to store comprehensive details for each hand, enabling detailed profit analysis, positional insights, and performance tracking.

Below are a few screenshots of the interface in action:

![Graph Tab](images/graph_tab.png "Graph Tab")
*Displays the cumulative profit chart over 12,000 sample hands.*

![Range Tab - Facing Raise](images/range_tab_facing_raise.png "Range Tab - Facing Raise")
*Illustrates raise/call/fold frequencies in a color-coded 13x13 matrix.*

![Range Tab - Facing 3-Bet](images/range_tab_facing_3bet.png "Range Tab - Facing 3-Bet")
*Highlights how often certain hands are raised or called when facing a 3-bet.*

![LeakHelper Tab 1](images/leakhelper_tab_1.png "LeakHelper Tab 1")
*Shows a grid of hands with profit/loss color-coding for quick leak detection.*

![LeakHelper Tab 2](images/leakhelper_tab_2.png "LeakHelper Tab 2")
*Another LeakHelper view focusing on a specific subset of premium hands.*

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
