from constants import DB_FILE, RANKS
import sqlite3
import tkinter as tk

# Utility Functions
def apply_sort(self):
    """Apply the selected sorting option to the hand history display."""
    sort_option = self.sort_options.get()
    
    # If "None" is selected, just refresh without sorting
    if sort_option == "None":
        self.refresh_import_tab_no_sort()
        return
    
    # Clear current display
    for row in self.tree.get_children():
        self.tree.delete(row)
    
    # Build query with appropriate ORDER BY clause
    if sort_option == "Date (newest first)":
        order_by = "ORDER BY date_time DESC"
    elif sort_option == "Date (oldest first)":
        order_by = "ORDER BY date_time ASC"
    elif sort_option == "Profit (highest first)":
        order_by = "ORDER BY hero_profit DESC"
    elif sort_option == "Profit (lowest first)":
        order_by = "ORDER BY hero_profit ASC"
    elif sort_option == "Position":
        order_by = "ORDER BY hero_position"
    elif sort_option == "Stake":
        order_by = "ORDER BY stake"
    else:
        order_by = "ORDER BY rowid DESC"  # Default
    
    # Execute query with only the required columns
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    query = f"""
        SELECT hand_id, date_time, stake, hero_position, hero_cards, ROUND(hero_profit, 2) as hero_profit
        FROM hands
        {order_by}
    """
    
    # Execute query and update display
    c.execute(query)
    rows = c.fetchall()
    conn.close()
    
    for row in rows:
        # Format the date to show date and time on a single line
        date_parts = row[1].split() if len(row) > 1 and row[1] else ["", ""]
        formatted_date = f"{date_parts[0]} {date_parts[1] if len(date_parts) > 1 else ''}"
        
        # Create a new row with the formatted date
        formatted_row = (formatted_date,) + row[0:1] + row[2:5] + row[5:]
        self.tree.insert("", tk.END, values=formatted_row)

def calculate_range_stats(scenario=None, position=None):
    """Compute frequencies by starting hand type for a given preflop scenario and position."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if scenario == 'open':
        query = """
            SELECT hero_cards, preflop_action 
            FROM hands 
            WHERE hero_cards IS NOT NULL 
            AND hero_cards != ''
            AND had_rfi_opportunity = 1
        """
        params = []
        
    elif scenario == 'faces_open':
        # Facing a raise - uses had_3bet_op
        query = """
            SELECT hero_cards, preflop_action 
            FROM hands 
            WHERE hero_cards IS NOT NULL 
            AND hero_cards != ''
            AND had_3bet_op = 1
        """
        params = []
        
    elif scenario == 'faces_3bet':
        # Facing a 3bet - should be identical logic but with had_4bet_op
        query = """
            SELECT hero_cards, preflop_action 
            FROM hands 
            WHERE hero_cards IS NOT NULL 
            AND hero_cards != ''
            AND had_4bet_op = 1
        """
        params = []
        
    else:
        query = """
            SELECT hero_cards, preflop_action 
            FROM hands 
            WHERE hero_cards IS NOT NULL 
            AND hero_cards != ''
        """
        params = []
    
    if position:
        query += " AND hero_position = ?"
        params.append(position)
    
    query += " ORDER BY date_time DESC"
    
    c.execute(query, params)
    rows = c.fetchall()
    
    totals = {}
    raises = {}
    calls = {}
    
    for hero_cards, preflop_action in rows:
        key = normalize_hand(hero_cards)
        if not key:
            continue
        
        totals[key] = totals.get(key, 0) + 1
        if preflop_action:
            preflop_action = preflop_action.lower()
            if 'raises' in preflop_action:
                raises[key] = raises.get(key, 0) + 1
            elif 'calls' in preflop_action:
                calls[key] = calls.get(key, 0) + 1
    
    conn.close()
    
    stats = {}
    for k in totals:
        cnt = totals[k]
        raise_cnt = raises.get(k, 0)
        call_cnt = calls.get(k, 0)
        raise_pct = (raise_cnt/cnt*100) if cnt>0 else 0
        call_pct = (call_cnt/cnt*100) if cnt>0 else 0
        stats[k] = (cnt, raise_cnt, call_cnt, raise_pct, call_pct)
    
    return stats

def normalize_hand(cards_str):
    """Given a 2-card string like 'Ah Kd', return e.g. 'AKo' or '77' or 'A7s' etc."""
    cards = cards_str.split()
    if len(cards)!=2:
        return None
    r1, s1 = cards[0][0], cards[0][1]
    r2, s2 = cards[1][0], cards[1][1]
    if r1 not in RANKS or r2 not in RANKS:
        return None
    # Sort so that e.g. 'Kc Ad' => 'A' 'K'
    if RANKS.index(r1)>RANKS.index(r2):
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    if r1==r2:
        return r1+r1
    else:
        # suited?
        return r1+r2+("s" if s1==s2 else "o")
    
def calculate_profit_stats(position=None, scenario=None):
    """Compute profit statistics by starting hand type for the LeakHelper tab."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Base query to get hero cards and profit
    query = """
        SELECT hero_cards, hero_profit 
        FROM hands 
        WHERE hero_cards IS NOT NULL 
        AND hero_cards != ''
    """
    params = []
    
    # Add position filter if specified
    if position:
        query += " AND hero_position = ?"
        params.append(position)
    
    # Add scenario filter if specified
    if scenario:
        # Map button labels to actual scenario values in the database
        scenario_mapping = {
            'Open': 'open (single raised)',
            'Facing Open': 'call_vs_open (single raised)',
            '3bet': '3bet',
            'Facing 3bet': 'call_vs_3bet',
            '4bet': '4bet',
            'Facing 4bet': 'call_vs_4bet+',
            '5bet+': '5bet+'
        }
        
        if scenario in scenario_mapping:
            query += " AND preflop_scenario = ?"
            params.append(scenario_mapping[scenario])
    
    c.execute(query, params)
    rows = c.fetchall()
    
    # Initialize dictionaries to track stats
    hand_profits = {}  # Total profit for each hand type
    hand_counts = {}   # Number of times each hand was played
    
    for hero_cards, profit in rows:
        key = normalize_hand(hero_cards)
        if not key:
            continue
        
        # Update profit and count for this hand type
        hand_profits[key] = hand_profits.get(key, 0) + profit
        hand_counts[key] = hand_counts.get(key, 0) + 1
    
    conn.close()
    
    # Combine the stats
    stats = {}
    for k in hand_counts:
        count = hand_counts[k]
        total_profit = hand_profits.get(k, 0)
        avg_profit = total_profit / count if count > 0 else 0
        stats[k] = (count, total_profit, avg_profit)
    
    return stats



def refresh_import_tab_no_sort(self):
    """Refresh the import tab without applying any sort."""
    for row in self.tree.get_children():
        self.tree.delete(row)
    
    # Get all hands with default ordering
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Fetch only the required columns
    c.execute("""
        SELECT hand_id, date_time, stake, hero_position, hero_cards, ROUND(hero_profit, 2) as hero_profit
        FROM hands
        ORDER BY rowid DESC
    """)
    
    rows = c.fetchall()
    conn.close()
    
    for r in rows:
        # Format the date to show date and time on a single line
        date_parts = r[1].split() if len(r) > 1 and r[1] else ["", ""]
        formatted_date = f"{date_parts[0]} {date_parts[1] if len(date_parts) > 1 else ''}"
        # Create a new row with the formatted date
        formatted_row = (formatted_date,) + r[0:1] + r[2:5] + r[5:]
        self.tree.insert("", tk.END, values=formatted_row)

