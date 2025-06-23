import os
import re
import json
import zipfile
import tempfile
import sqlite3
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import mplcursors
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import math

# Global constants
DB_FILE = "poker_data.db"

# Global color constants
DARK_BG = '#1a1a1a'
DARK_MEDIUM_BG = '#2d2d2d'
MEDIUM_BG = '#333333'
LIGHT_BG = '#444444'
ACCENT_COLOR = '#00ace6'
PROFIT_COLOR = '#00ace6'
LOSS_COLOR = '#802020'
DARK_PROFIT_COLOR = '#003380'
DARK_LOSS_COLOR = '#4d0000'
TEXT_COLOR = 'white'
TEXT_SECONDARY_COLOR = '#aaaaaa'
BORDER_COLOR = '#333333'
GRID_COLOR = 'gray'
FOLD_COLOR = "#737382"
RAISE_COLOR = "#00ace6"
CALL_COLOR = "#d571b2"

def init_database():    
    """Create the local SQLite DB with a 'hands' table if not present."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS hands (
            hand_id TEXT PRIMARY KEY,
            stake TEXT,
            date_time TEXT,
            hero_position TEXT,
            hero_cards TEXT,
            preflop_action TEXT,
            preflop_all TEXT,
            flop_action TEXT,
            flop_all TEXT,
            turn_action TEXT,
            turn_all TEXT,
            river_action TEXT,
            river_all TEXT,
            board_flop TEXT,
            board_turn TEXT,
            board_river TEXT,
            total_pot REAL,
            rake REAL,
            jackpot REAL,
            hero_profit REAL,
            hero_profit_with_rake REAL,
            seats_info TEXT,
            imported_on TEXT,
            preflop_scenario TEXT,
            had_rfi_opportunity INTEGER,
            had_3bet_op INTEGER,
            had_4bet_op INTEGER,
            hero_contribution REAL,
            adjusted_profit REAL
        )
    """)
    
    # Check if hero_profit_with_rake column exists, add it if not
    c.execute("PRAGMA table_info(hands)")
    columns = [info[1] for info in c.fetchall()]
    
    if "hero_profit_with_rake" not in columns:
        try:
            c.execute("ALTER TABLE hands ADD COLUMN hero_profit_with_rake REAL")
            
            # Update existing rows with calculated values (including both rake and jackpot)
            c.execute("UPDATE hands SET hero_profit_with_rake = hero_profit + rake + jackpot")
        except sqlite3.OperationalError:
            # Column might have been added in another process
            pass
    
    # Check if hero_contribution column exists, add it if not
    if "hero_contribution" not in columns:
        try:
            c.execute("ALTER TABLE hands ADD COLUMN hero_contribution REAL")
            
            # Initialize with 0 for existing rows
            c.execute("UPDATE hands SET hero_contribution = 0.0")
        except sqlite3.OperationalError:
            # Column might have been added in another process
            pass
    
    # Check if adjusted_profit column exists, add it if not
    if "adjusted_profit" not in columns:
        try:
            c.execute("ALTER TABLE hands ADD COLUMN adjusted_profit REAL")
            
            # Initialize with hero_profit for existing rows
            c.execute("UPDATE hands SET adjusted_profit = hero_profit")
        except sqlite3.OperationalError:
            # Column might have been added in another process
            pass
    
    # Create settings table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def extract_txt_from_zip(zip_path):
    """Extract all .txt files from a ZIP into a temp folder, returning the list of extracted .txt file paths."""
    txt_files = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            temp_dir = tempfile.mkdtemp()
            zf.extractall(temp_dir)
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(".txt"):
                        txt_files.append(os.path.join(root, file))
    except Exception as e:
        print(f"Error extracting {zip_path}: {e}")
    return txt_files

def parse_hand_history_file(file_path):
    """Reads the file content and splits into blocks, returning a list of parsed hand dicts."""
    hands = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        blocks = re.split(r"\n\s*\n", text)
        for block in blocks:
            block = block.strip()
            if block:
                one = parse_one_hand(block)
                if one:
                    hands.append(one)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return hands

def parse_preflop_scenario(preflop_text):
    """Analyze preflop action to determine scenario."""
    lines = preflop_text.split('\n')
    start_idx = -1
    for i, line in enumerate(lines):
        if '*** HOLE CARDS ***' in line:
            start_idx = i
            break
    
    if start_idx < 0:
        return 'none'
        
    # Skip the dealt cards lines
    action_start = start_idx + 1
    while action_start < len(lines) and 'dealt to' in lines[action_start].lower():
        action_start += 1
    
    # Get all action lines
    action_lines = []
    for line in lines[action_start:]:
        line = line.strip().lower()
        if not line:
            continue
            
        if any(marker in line for marker in ['*** flop ***', '*** summary ***', '*** showdown ***']):
            break
            
        # Skip uncalled bet lines
        if 'uncalled bet' in line:
            continue
            
        # Add valid action lines
        if ': ' in line:
            action_lines.append(line)
    
    # Count total raises
    total_raises = sum(1 for line in action_lines if 'raises' in line)
    
    # Find Hero's last action
    hero_actions = [line for line in action_lines if line.startswith('hero:')]
    if not hero_actions:
        return 'none'
    
    hero_last_action = hero_actions[-1]
    
    # Determine scenario based on total raises and Hero's last action
    if 'raises' in hero_last_action:
        if total_raises == 1:
            return 'open (single raised)'
        elif total_raises == 2:
            return '3bet'
        elif total_raises == 3:
            return '4bet'
        elif total_raises >= 4:
            return '5bet+'
    elif 'calls' in hero_last_action:
        if total_raises == 1:
            return 'call_vs_open (single raised)'
        elif total_raises == 2:
            return 'call_vs_3bet'
        elif total_raises >= 3:
            return 'call_vs_4bet+'
    elif 'checks' in hero_last_action:
        return 'check_vs_open' if total_raises > 0 else 'limp'
    elif 'folds' in hero_last_action:
        return 'fold'
    
    return 'none'

def parse_one_hand(block):
    """Parse a single hand history block."""
    # Initialize data dictionary with explicit None values
    data = {
        "hand_id": None,
        "stake": None,
        "date_time": None,
        "hero_position": None,
        "hero_cards": None,
        "preflop_action": "",
        "preflop_all": "",
        "flop_action": "",
        "flop_all": "",
        "turn_action": "",
        "turn_all": "",
        "river_action": "",
        "river_all": "",
        "board_flop": "",
        "board_turn": "",
        "board_river": "",
        "total_pot": 0.0,
        "rake": 0.0,
        "jackpot": 0.0,
        "hero_profit": 0.0,
        "hero_profit_with_rake": 0.0,
        "seats_info": "",
        "imported_on": datetime.datetime.now().isoformat(),
        "preflop_scenario": "none",
        "had_rfi_opportunity": 0,
        "had_3bet_op": 0,
        "had_4bet_op": 0,
        "hero_contribution": 0.0
    }

    # Regex for header
    m = re.search(
        r"Poker\s+Hand\s+#(HD\S+):\s+Hold'em\s+No\s+Limit\s+\((\$[\d\.]+/\$[\d\.]+)\)\s*-\s*(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})",
        block
    )
    if not m:
        # Fallback if date/time is a different format. Let's try a simpler approach:
        m2 = re.search(r"Poker\s+Hand\s+#(HD\S+):\s+Hold'em\s+No\s+Limit\s+\((\$[\d\.]+/\$[\d\.]+)\)\s*-\s*(.+)", block)
        if m2:
            data["hand_id"] = m2.group(1)
            data["stake"]   = m2.group(2)
            data["date_time"] = m2.group(3).strip()
        else:
            return None
    else:
        data["hand_id"] = m.group(1)
        data["stake"]   = m.group(2)
        data["date_time"] = m.group(3)

    # Button seat
    m_btn = re.search(r"Seat\s+#(\d+)\s+is\s+the\s+button", block, re.IGNORECASE)
    button_seat = int(m_btn.group(1)) if m_btn else None

    # Seats
    seats = re.findall(r"Seat\s+(\d+):\s+([^\(]+)\s+\(\$([\d\.]+)\s+in\s+chips\)", block)
    seat_list = []
    hero_seat = None
    for s, name, stack in seats:
        s_int = int(s)
        seat_list.append({"seat": s_int, "player": name.strip(), "stack": stack})
        if name.strip().lower() == "hero":
            hero_seat = s_int
    data["seats_info"] = json.dumps(seat_list)
    if hero_seat and button_seat:
        data["hero_position"] = deduce_position_6max(button_seat, hero_seat)
    else:
        data["hero_position"] = "Unknown"

    # Hero hole cards
    m_cards = re.search(r"Dealt\s+to\s+Hero\s*\[([^\]]+)\]", block, re.IGNORECASE)
    if m_cards:
        data["hero_cards"] = m_cards.group(1).strip()

    # Streets
    preflop, flop, turn, river = split_streets(block)
      
    data["preflop_all"] = preflop
    data["flop_all"] = flop
    data["turn_all"] = turn
    data["river_all"] = river

    data["preflop_action"] = gather_hero_actions(preflop)
    data["flop_action"]    = gather_hero_actions(flop)
    data["turn_action"]    = gather_hero_actions(turn)
    data["river_action"]   = gather_hero_actions(river)

    # Boards
    m_flop = re.search(r"\*\*\*\s+FLOP\s+\*\*\*\s*\[([^\]]+)\]", block)
    if m_flop:
        data["board_flop"] = m_flop.group(1).strip()
    m_turn = re.search(r"\*\*\*\s+TURN\s+\*\*\*\s*(?:\[([^\]]+)\]\s*)?\[([^\]]+)\]", block)
    if m_turn:
        data["board_turn"] = m_turn.group(2).strip()
    m_river = re.search(r"\*\*\*\s+RIVER\s+\*\*\*\s*(?:\[([^\]]+)\]\s*)?\[([^\]]+)\]", block)
    if m_river:
        data["board_river"] = m_river.group(2).strip()

    # Summary
    summary_start = block.find("*** SUMMARY ***")
    if summary_start != -1:
        summary_text = block[summary_start:]
        m_pot = re.search(r"Total\s+pot\s+\$(\d+(?:\.\d+)?)", summary_text)
        if m_pot:
            data["total_pot"] = float(m_pot.group(1))
        m_rake = re.search(r"Rake\s+\$(\d+(?:\.\d+)?)", summary_text)
        if m_rake:
            data["rake"] = float(m_rake.group(1))
        m_jackpot = re.search(r"Jackpot\s+\$(\d+(?:\.\d+)?)", summary_text)
        if m_jackpot:
            data["jackpot"] = float(m_jackpot.group(1))

    # Hero profit calculation
    contribution = parse_hero_contribution(block, data["hero_position"], data["stake"])
    data["hero_contribution"] = round(contribution, 2)
    
    # Initialize hero's winnings
    hero_winnings = 0.0
    
    # Look for all instances where hero collected money
    hero_collect_pattern = r"Hero collected \$(\d+(?:\.\d+)?)"
    hero_collect_matches = re.findall(hero_collect_pattern, block, re.IGNORECASE)
    
    for amount in hero_collect_matches:
        hero_winnings += float(amount)
    
    # If no "collected" entries found, look for "won" in summary
    if not hero_collect_matches:
        # Look for amount won/collected in summary
        hero_win_pattern = r"Seat\s+\d+:\s+Hero.*(?:won|collected)\s+\(\$(\d+(?:\.\d+)?)\)"
        hero_win_matches = re.findall(hero_win_pattern, block, re.IGNORECASE)
        
        for amount in hero_win_matches:
            hero_winnings += float(amount)
    
    # Calculate profit (winnings minus contribution)
    if hero_winnings > 0:
        data["hero_profit"] = round(hero_winnings - contribution, 2)
        
        # Check for multiple showdowns
        showdown_pattern = r"\*\*\* (?:FIRST|SECOND|THIRD|FOURTH|FIFTH) SHOWDOWN \*\*\*"
        showdown_matches = re.findall(showdown_pattern, block)
        total_showdowns = len(showdown_matches)
        
        # Calculate profit with rake and jackpot included
        rake_amount = 0.0
        jackpot_amount = 0.0
        if "rake" in data and data["rake"]:
            rake_amount = data["rake"]
        if "jackpot" in data and data["jackpot"]:
            jackpot_amount = data["jackpot"]
        
        # Check for split pot (multiple winners in the same pot)
        if total_showdowns <= 1:  # Regular pot (not multiple showdowns)
            # Look for all players who collected money in the same pot
            collect_pattern = r"(?:Seat \d+: )?(\w+)(?:.*?) (?:collected|won) (?:\()?\$(\d+(?:\.\d+)?)(?:\))?"
            collect_matches = re.findall(collect_pattern, block, re.IGNORECASE)
            
            # Count unique winners
            winners = set()
            for player, amount in collect_matches:
                if float(amount) > 0:
                    winners.add(player.lower())
            
            num_winners = len(winners)
            
            if num_winners > 1:
                # This is a split pot - divide rake proportionally
                # Add back proportional rake and jackpot
                data["hero_profit_with_rake"] = round(data["hero_profit"] + (rake_amount + jackpot_amount) / num_winners, 2)
            else:
                # Normal case for single winner - add back full rake and jackpot
                data["hero_profit_with_rake"] = round(data["hero_profit"] + rake_amount + jackpot_amount, 2)
        else:
            # Only apply special logic for multiple showdowns
            # Count how many showdowns Hero won
            hero_won_showdowns = len(hero_collect_matches)
            
            if hero_won_showdowns > 0:
                # Calculate the proportion of showdowns Hero won
                proportion = hero_won_showdowns / total_showdowns
                # Add back proportional rake and jackpot
                data["hero_profit_with_rake"] = round(data["hero_profit"] + proportion * (rake_amount + jackpot_amount), 2)
            else:
                # If Hero didn't win any showdowns, profit with rake is the same as regular profit
                data["hero_profit_with_rake"] = data["hero_profit"]
    else:
        # If hero didn't win, they lost their contribution
        data["hero_profit"] = round(-contribution, 2)
        # For losses, the profit with rake is the same as regular profit
        data["hero_profit_with_rake"] = data["hero_profit"]

    # After parsing preflop action
    preflop, flop, turn, river = split_streets(block)
    data["preflop_all"] = preflop
    data["flop_all"] = flop
    data["turn_all"] = turn
    data["river_all"] = river
    
    # Determine preflop scenario
    scenario = parse_preflop_scenario(preflop)
    data["preflop_scenario"] = scenario
    
    # Determine RFI opportunity
    data["had_rfi_opportunity"] = determine_rfi_opportunity(preflop, data["hero_position"])

    # Determine 3-bet opportunity
    data["had_3bet_op"] = determine_3bet_opportunity(preflop)

    # Determine 4-bet opportunity
    data["had_4bet_op"] = determine_4bet_opportunity(preflop)

    return data

def deduce_position_6max(button_seat, hero_seat):
    """Return 'BTN','SB','BB','UTG','HJ','CO' based on hero_seat vs button_seat in 6max."""
    positions = ["BTN","SB","BB","UTG","HJ","CO"]
    idx = (hero_seat - button_seat) % 6
    return positions[idx]

def split_streets(block):
    """Split a hand history block into streets."""
    # Find the start of each street section, handling variations like "FIRST FLOP", etc.
    hole_cards_start = block.find("*** HOLE CARDS ***")
    
    # Look for flop markers (including variations like "FIRST FLOP")
    flop_markers = ["*** FLOP ***", "*** FIRST FLOP ***", "*** SECOND FLOP ***"]
    flop_start = -1
    for marker in flop_markers:
        pos = block.find(marker)
        if pos != -1:
            flop_start = pos
            break
    
    # Look for turn markers
    turn_markers = ["*** TURN ***", "*** FIRST TURN ***", "*** SECOND TURN ***"]
    turn_start = -1
    for marker in turn_markers:
        pos = block.find(marker)
        if pos != -1:
            turn_start = pos
            break
    
    # Look for river markers
    river_markers = ["*** RIVER ***", "*** FIRST RIVER ***", "*** SECOND RIVER ***"]
    river_start = -1
    for marker in river_markers:
        pos = block.find(marker)
        if pos != -1:
            river_start = pos
            break
    
    # Look for summary/showdown markers
    summary_markers = ["*** SUMMARY ***", "*** SHOWDOWN ***", "*** FIRST SHOWDOWN ***", "*** SECOND SHOWDOWN ***"]
    end_markers = []
    for marker in summary_markers:
        pos = block.find(marker)
        if pos != -1:
            end_markers.append(pos)
    
    # If no end markers found, use the end of the block
    if not end_markers:
        end_markers.append(len(block))
    
    # Determine the end of each section
    preflop_end = flop_start if flop_start != -1 else min(end_markers)
    flop_end = turn_start if turn_start != -1 else min(end_markers) if flop_start != -1 else -1
    turn_end = river_start if river_start != -1 else min(end_markers) if turn_start != -1 else -1
    river_end = min(end_markers) if river_start != -1 else -1
    
    # Extract each section
    preflop = block[hole_cards_start:preflop_end] if hole_cards_start != -1 else ""
    flop = block[flop_start:flop_end] if flop_start != -1 and flop_end != -1 else ""
    turn = block[turn_start:turn_end] if turn_start != -1 and turn_end != -1 else ""
    river = block[river_start:river_end] if river_start != -1 and river_end != -1 else ""
    
    return preflop, flop, turn, river

def gather_hero_actions(text_block):
    actions = []
    for line in text_block.splitlines():
        line=line.strip()
        if line.lower().startswith("hero:"):
            actions.append(line)
    return " | ".join(actions)

def parse_hero_contribution(text, hero_position=None, stake=None):
    """Sum up all the money hero puts into the pot, including blinds."""
    total = 0.0
    posted_blinds_amount = 0.0
    hero_raised_preflop = False
    
    # Check for posted blinds and straddles before the hole cards
    hole_cards_index = text.find("*** HOLE CARDS ***")
    if hole_cards_index > 0:
        pre_action = text[:hole_cards_index]
        for line in pre_action.splitlines():
            line = line.strip().lower()
            if line.startswith("hero: posts") and "$" in line:
                # Extract the amount posted
                amounts = re.findall(r'\$(\d+(?:\.\d+)?)', line)
                if amounts:
                    posted_amount = float(amounts[0])
                    
                    # Check if this is a straddle
                    if "straddle" in line:
                        posted_blinds_amount += posted_amount
                    # Check if this is a big blind
                    elif "big blind" in line:
                        posted_blinds_amount += posted_amount
                    # Check if this is a small blind
                    elif "small blind" in line:
                        posted_blinds_amount += posted_amount
                    
                    # Check if this is an all-in straddle
                    if "all-in" in line or "and is all-in" in line:
                        # For all-in straddles, we always count the contribution
                        total += posted_amount
                        # Mark that we've already added this amount
                        posted_blinds_amount = 0
    
    # Split the text into streets using the existing function
    preflop, flop, turn, river = split_streets(text)
    streets = [preflop, flop, turn, river]
    street_names = ["PREFLOP", "FLOP", "TURN", "RIVER"]
    
    # Check if hero raised preflop
    for line in preflop.splitlines():
        line = line.strip().lower()
        if line.startswith("hero:") and "raises" in line:
            hero_raised_preflop = True
            break
    
    # Process each street separately
    for i, street_text in enumerate(streets):
        street_contribution = process_street_contribution(street_text)
        total += street_contribution
    
    # Add posted blinds only if hero didn't raise preflop
    if not hero_raised_preflop and posted_blinds_amount > 0:
        total += posted_blinds_amount
    
    # Add regular blind contributions if position and stake are provided
    # and no posted blinds were found in the pre-action
    if hero_position in ["SB", "BB"] and stake and posted_blinds_amount == 0:
        try:
            small_blind, big_blind = stake.replace('$', '').split('/')
            small_blind = float(small_blind)
            big_blind = float(big_blind)
            
            # Only add regular blinds if hero didn't raise preflop
            if not hero_raised_preflop:
                if hero_position == "SB":
                    total += small_blind
                elif hero_position == "BB":
                    total += big_blind

        except (ValueError, TypeError):
            # If stake parsing fails, continue without adding blinds
            pass
    
    return total

def process_street_contribution(street_text):
    """Calculate hero's contribution for a single street."""
    contribution = 0.0
    hero_actions = []
    
    # First pass: collect all hero's actions with amounts
    for line in street_text.splitlines():
        line = line.strip().lower()
        
        if line.startswith('hero:'):
            # Look for dollar amounts in the line
            amounts = re.findall(r'\$(\d+(?:\.\d+)?)', line)
            if amounts:
                amount = float(amounts[-1])
                is_raise = 'raises' in line
                hero_actions.append((line, amount, is_raise))
        
        # Subtract uncalled bets returned
        elif 'uncalled bet' in line and 'returned to hero' in line:
            amounts = re.findall(r'\$(\d+(?:\.\d+)?)', line)
            if amounts:
                uncalled = float(amounts[0])
                contribution -= uncalled
    
    # Second pass: process hero actions
    if hero_actions:
        # Find the last raise if any
        last_raise_index = -1
        for i, (_, _, is_raise) in enumerate(hero_actions):
            if is_raise:
                last_raise_index = i
        
        # If there was a raise, only count from that raise onwards
        if last_raise_index >= 0:
            for i, (_, amount, _) in enumerate(hero_actions):
                if i >= last_raise_index:
                    contribution += amount
        else:
            # No raises, add all actions
            for i, (_, amount, _) in enumerate(hero_actions):
                contribution += amount
    
    return contribution

def insert_hand_details(hand_info_list):
    """Insert each hand dict into the DB, ensuring all columns of data."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now_str = datetime.datetime.now().isoformat()
    
    # Get rakeback percentage from settings
    c.execute("SELECT value FROM settings WHERE key = 'rakeback_percentage'")
    result = c.fetchone()
    rakeback_pct = float(result[0]) / 100.0 if result else 0.0
    
    # Define all expected columns in order
    expected_columns = [
        "hand_id", "stake", "date_time", "hero_position", "hero_cards",
        "preflop_action", "preflop_all", "flop_action", "flop_all",
        "turn_action", "turn_all", "river_action", "river_all",
        "board_flop", "board_turn", "board_river",
        "total_pot", "rake", "jackpot", "hero_profit", "hero_profit_with_rake",
        "seats_info", "imported_on", "preflop_scenario",
        "had_rfi_opportunity", "had_3bet_op", "had_4bet_op", "hero_contribution",
        "adjusted_profit"
    ]
    
    # First, check which hands already exist
    existing_hands = set()
    c.execute("SELECT hand_id FROM hands")
    for (hand_id,) in c.fetchall():
        existing_hands.add(hand_id)
    
    # Filter out hands that already exist
    new_hands = [hand for hand in hand_info_list if hand['hand_id'] not in existing_hands]
    
    for hand_info in new_hands:
        # Ensure all expected fields exist
        for key in expected_columns:
            if key not in hand_info or hand_info[key] is None:
                if key in ["total_pot", "rake", "jackpot", "hero_profit", "hero_profit_with_rake"]:
                    hand_info[key] = 0.0
                elif key in ["had_rfi_opportunity", "had_3bet_op", "had_4bet_op"]:
                    hand_info[key] = 0
                else:
                    hand_info[key] = ""
        
        # Calculate adjusted profit
        if "rake" in hand_info and hand_info["rake"] is not None and "hero_profit" in hand_info and hand_info["hero_profit"] > 0:
            if rakeback_pct == 1.0:  # 100% rakeback
                hand_info["adjusted_profit"] = hand_info.get("hero_profit_with_rake", hand_info["hero_profit"])
            else:
                hand_info["adjusted_profit"] = hand_info["hero_profit"] + (hand_info["rake"] * rakeback_pct)
        else:
            hand_info["adjusted_profit"] = hand_info.get("hero_profit", 0.0)
        
        # Get values in the correct order
        values = [hand_info[col] for col in expected_columns]
        values.append(now_str)  # Add imported_on timestamp
        
        # Create the SQL query with the exact number of columns
        columns_str = ", ".join(expected_columns + ["imported_on"])
        placeholders = ",".join(["?" for _ in range(len(expected_columns) + 1)])
        
        try:
            c.execute(f"""
                INSERT INTO hands ({columns_str})
                VALUES ({placeholders})
            """, tuple(values))
        except sqlite3.IntegrityError:
            pass  # Skip duplicates
    
    conn.commit()
    conn.close()

def get_all_hands(limit=None):
    """Fetch hands from DB, with optional limit."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if limit:
        c.execute("""
            SELECT hand_id, date_time, stake, hero_position, hero_cards,
                   total_pot, rake, jackpot, ROUND(hero_profit, 2) as hero_profit,
                   ROUND(hero_profit_with_rake, 2) as hero_profit_with_rake
            FROM hands
            ORDER BY rowid DESC
            LIMIT ?
        """, (limit,))
    else:
        c.execute("""
            SELECT hand_id, date_time, stake, hero_position, hero_cards,
                   total_pot, rake, jackpot, ROUND(hero_profit, 2) as hero_profit,
                   ROUND(hero_profit_with_rake, 2) as hero_profit_with_rake
            FROM hands
            ORDER BY rowid DESC
        """)
    
    rows = c.fetchall()
    conn.close()
    return rows

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

RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']

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

def build_range_matrix(stats):
    """Build a 13x13 matrix of 3bet percentages from stats."""
    mat = np.full((13,13), np.nan)
    rank_to_idx = {rank:i for i,rank in enumerate(RANKS)}
    for key,(cnt, tb, pct) in stats.items():
        if len(key)==2:
            # pair e.g. 'AA','KK'
            i = rank_to_idx[key[0]]
            mat[i,i] = pct
        elif len(key)==3:
            # e.g. 'AKo','AKs'
            r1 = key[0]
            r2 = key[1]
            suited = (key[2]=='s')
            i = rank_to_idx[r2]
            j = rank_to_idx[r1]
            if r1==r2:
                # already handled by pair
                continue
            if suited:
                if i<j:
                    mat[i,j] = pct
                else:
                    mat[j,i] = pct
            else:
                if i>j:
                    mat[i,j] = pct
                else:
                    mat[j,i] = pct
    return mat

def save_hand_to_db(data):
    """Save a parsed hand to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Calculate had_3bet_op
    had_3bet_op = determine_3bet_opportunity(data['preflop_all'])
    
    # Use the scenario that was already parsed and stored in data
    scenario = data['preflop_scenario']
    
    # Get rakeback percentage from settings
    c.execute("SELECT value FROM settings WHERE key = 'rakeback_percentage'")
    result = c.fetchone()
    rakeback_pct = float(result[0]) / 100.0 if result else 0.0
    
    # Calculate adjusted profit - only add rakeback for hands where hero won (GGPoker model)
    if data['hero_profit'] > 0:
        if rakeback_pct == 1.0:  # 100% rakeback
            adjusted_profit = data['hero_profit_with_rake']
        else:
            adjusted_profit = data['hero_profit'] + (data['rake'] * rakeback_pct)
    else:
        adjusted_profit = data['hero_profit']
    
    try:
        c.execute("""
            INSERT OR REPLACE INTO hands (
                hand_id, stake, date_time, hero_position, hero_cards,
                preflop_action, preflop_all, flop_action, flop_all,
                turn_action, turn_all, river_action, river_all,
                board_flop, board_turn, board_river,
                total_pot, rake, jackpot, hero_profit, hero_profit_with_rake,
                seats_info, imported_on, preflop_scenario,
                had_rfi_opportunity, had_3bet_op, had_4bet_op, hero_contribution,
                adjusted_profit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['hand_id'], data['stake'], data['date_time'],
            data['hero_position'], data['hero_cards'],
            data['preflop_action'], data['preflop_all'],
            data['flop_action'], data['flop_all'],
            data['turn_action'], data['turn_all'],
            data['river_action'], data['river_all'],
            data['board_flop'], data['board_turn'], data['board_river'],
            data['total_pot'], data['rake'], data['jackpot'],
            data['hero_profit'], data['hero_profit_with_rake'],
            data['seats_info'],
            data['imported_on'],
            data['preflop_scenario'],
            data['had_rfi_opportunity'],
            data['had_3bet_op'],
            data['had_4bet_op'],
            data['hero_contribution'],
            data['adjusted_profit']
        ))
        
        conn.commit()
        
    finally:
        conn.close()

def determine_rfi_opportunity(preflop_text, hero_position):
    """
    Determine if hero had the opportunity to raise first in.
    Returns 1 if yes, 0 if no.
    """
    # Skip if we don't have position info
    if not hero_position:
        return 0

    # Check for uncalled bet returned to Hero
    if "Uncalled bet" in preflop_text and "returned to Hero" in preflop_text:
        return 0

    lines = preflop_text.split('\n')
    preflop_start = False
    action_lines = []
    
    for line in lines:
        if "*** HOLE CARDS ***" in line:
            preflop_start = True
            continue
        if "*** FLOP ***" in line or "*** SUMMARY ***" in line:
            break
        if preflop_start and ": " in line and not line.lower().startswith("dealt to"):
            action_lines.append(line.strip().lower())

    # Check if anyone raised before hero's action
    hero_found = False
    for line in action_lines:
        if line.startswith("hero:"):
            hero_found = True
            break
        if "raises" in line:
            return 0  # Someone raised before us

    return 1  # No one raised before us

def determine_3bet_opportunity(preflop_text):
    """
    Determine if hero had the opportunity to 3-bet.
    Returns 1 if yes, 0 if no.
    """
    # First check if Hero has KK
    has_kk = False
    for line in preflop_text.split('\n'):
        if "Dealt to Hero" in line and "K" in line:
            # Check if both cards are kings
            cards = line[line.find("[")+1:line.find("]")].split()
            if len(cards) == 2 and cards[0][0] == 'K' and cards[1][0] == 'K':
                has_kk = True
                break

    if not preflop_text:
        return 0

    lines = preflop_text.split('\n')
    preflop_start = False
    action_lines = []
    
    # Get all preflop action lines
    for line in lines:
        if "*** HOLE CARDS ***" in line:
            preflop_start = True
            continue
        if "*** FLOP ***" in line or "*** SUMMARY ***" in line:
            break
        if preflop_start and ": " in line and not line.lower().startswith("dealt to"):
            action_lines.append(line.strip().lower())

    # Track number of raises before hero's turn
    raise_count = 0
    for line in action_lines:
        if line.startswith("hero:"):
            break  # Stop when we reach Hero's action
        if "raises" in line:
            raise_count += 1
            if raise_count > 1:
                return 0  # More than one raise, not a 3bet opportunity

    # If we didn't see exactly one raise, it's not a 3bet opportunity
    if raise_count != 1:
        return 0

    return 1

def determine_4bet_opportunity(preflop_text):
    """
    Determine if hero had the opportunity to 4-bet.
    Returns 1 if yes, 0 if no.
    A 4bet opportunity occurs when Hero sees two raises before their turn to act.
    """
    if not preflop_text:
        return 0

    lines = preflop_text.split('\n')
    preflop_start = False
    action_lines = []
    
    # Get all preflop action lines
    for line in lines:
        if "*** HOLE CARDS ***" in line:
            preflop_start = True
            continue
        if "*** FLOP ***" in line or "*** SUMMARY ***" in line:
            break
        if preflop_start and ": " in line and not line.lower().startswith("dealt to"):
            action_lines.append(line.strip().lower())

    # Track raises before hero's turn
    raise_count = 0
    for line in action_lines:
        if line.startswith("hero:"):
            return 1 if raise_count == 2 else 0
        if "raises" in line:
            raise_count += 1
    
    return 0

def recalculate_all_contributions():
    """Recalculate hero contributions for all hands in the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get rakeback percentage from settings
    c.execute("SELECT value FROM settings WHERE key = 'rakeback_percentage'")
    result = c.fetchone()
    rakeback_pct = float(result[0]) / 100.0 if result else 0.0
    
    # Get all hand IDs and required data
    c.execute("""
        SELECT hand_id, preflop_all, flop_all, turn_all, river_all, hero_position, stake, hero_profit, rake, hero_profit_with_rake
        FROM hands
    """)
    
    hands_data = c.fetchall()
    total_hands = len(hands_data)
    updated_count = 0
    
    
    for hand_id, preflop_all, flop_all, turn_all, river_all, hero_position, stake, hero_profit, rake, hero_profit_with_rake in hands_data:
        # Combine all streets
        all_text = preflop_all + flop_all + turn_all + river_all
        
        # Calculate the contribution
        contribution = parse_hero_contribution(all_text, hero_position, stake)
        
        # Calculate adjusted profit - only add rakeback for hands where hero won (GGPoker model)
        if hero_profit > 0:
            if rakeback_pct == 1.0:  # 100% rakeback
                adjusted_profit = hero_profit_with_rake
            else:
                adjusted_profit = hero_profit + (rake * rakeback_pct)
        else:
            adjusted_profit = hero_profit
        
        # Update the database
        c.execute("""
            UPDATE hands
            SET hero_contribution = ?,
                adjusted_profit = ?
            WHERE hand_id = ?
        """, (contribution, adjusted_profit, hand_id))
        
        updated_count += 1
    
    conn.commit()
    conn.close()
    
    return updated_count

class PokerTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Poker Tracker")
        self.geometry("1300x800")
        
        # Define theme colors using global constants
        self.colors = {
            'bg_dark': DARK_BG,             # Main background
            'bg_medium': MEDIUM_BG,         # Panel background
            'bg_light': LIGHT_BG,           # Element background
            'accent': ACCENT_COLOR,         # Accent color for selected items
            'text': TEXT_COLOR,             # Main text color
            'text_secondary': TEXT_SECONDARY_COLOR,  # Secondary text color
            'border': BORDER_COLOR,         # Border color
            'positive': PROFIT_COLOR,       # Positive values (green)
            'negative': LOSS_COLOR,         # Negative values (red)
            'grid_line': GRID_COLOR         # Grid lines
        }
        
        # Configure the window
        self.configure(bg=self.colors['bg_dark'])
        
        # Initialize selection variables
        self.selected_stake = None
        self.selected_position = None
        
        # Initialize database first
        init_database()
        
        # Load rakeback percentage from settings
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'rakeback_percentage'")
        result = c.fetchone()
        conn.close()
        
        # Initialize rakeback variable with stored value or default to 0
        self.rakeback_var = tk.StringVar(value=result[0] if result else "0")
        
        # Create a single style instance for the application
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Configure the notebook style
        self.style.configure('TNotebook', background=self.colors['bg_dark'])
        self.style.configure('TNotebook.Tab', background=self.colors['bg_medium'], 
                        foreground=self.colors['text'], padding=[10, 5],
                        font=('Arial', 10, 'bold'))
        self.style.map('TNotebook.Tab', background=[('selected', self.colors['accent'])],
                 foreground=[('selected', self.colors['text'])])
        
        # Configure Treeview style
        self.style.configure("Treeview", 
                        background=self.colors['bg_light'], 
                        foreground=self.colors['text'], 
                        fieldbackground=self.colors['bg_light'],
                        rowheight=25)
        self.style.configure("Treeview.Heading", 
                        background=self.colors['bg_medium'], 
                        foreground=self.colors['text'],
                        font=('Arial', 9, 'bold'))
        self.style.map('Treeview', background=[('selected', self.colors['accent'])])
        
        # Create the notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Import Tab
        self.import_frame = tk.Frame(self.notebook, bg=self.colors['bg_dark'])
        self.notebook.add(self.import_frame, text="Import / Hands")
        self.create_import_tab()

        # Graph Tab
        self.graph_frame = tk.Frame(self.notebook, bg=self.colors['bg_dark'])
        self.notebook.add(self.graph_frame, text="Graph")
        self.create_graph_tab()

        # Range Tab
        self.range_frame = tk.Frame(self.notebook, bg=self.colors['bg_dark'])
        self.notebook.add(self.range_frame, text="Range")
        self.create_range_tab()
        
        # LeakHelper Tab
        self.leak_frame = tk.Frame(self.notebook)
        self.notebook.add(self.leak_frame, text="LeakHelper")
        self.create_leak_tab()

    def create_widgets(self):
        # Create menu bar
        self.menu_bar = tk.Menu(self)
        self.config(menu=self.menu_bar)
        
        # Create Tools menu
        tools_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Tools", menu=tools_menu)
        
        tools_menu.add_command(label="Recalculate All Profits", command=self.recalculate_all_profits)
        tools_menu.add_command(label="Recalculate All Contributions", command=self.recalculate_all_contributions)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Import Tab
        self.import_frame = tk.Frame(self.notebook)
        self.notebook.add(self.import_frame, text="Import / Hands")
        self.create_import_tab()

        # Graph Tab
        self.graph_frame = tk.Frame(self.notebook)
        self.notebook.add(self.graph_frame, text="Graph")
        self.create_graph_tab()

        # Range Tab
        self.range_frame = tk.Frame(self.notebook)
        self.notebook.add(self.range_frame, text="Range")
        self.create_range_tab()
        
        # LeakHelper Tab
        self.leak_frame = tk.Frame(self.notebook)
        self.notebook.add(self.leak_frame, text="LeakHelper")
        self.create_leak_tab()

    ########################
    ###  IMPORT / HANDS  ###
    ########################
    def create_import_tab(self):
        # Set the background color of the import frame
        self.import_frame.configure(bg=DARK_BG)
        
        top_frame = tk.Frame(self.import_frame, bg=DARK_BG)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Add buttons with the new color scheme
        self.import_button = tk.Button(
            top_frame, 
            text="Import Hand Histories", 
            command=self.import_files,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.import_button.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = tk.Button(
            top_frame, 
            text="Refresh", 
            command=self.refresh_import_tab,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = tk.Button(
            top_frame, 
            text="Clear All Hands", 
            command=self.clear_hands,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Add sorting options
        sort_frame = tk.Frame(top_frame, bg='#1a1a1a')
        sort_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(sort_frame, text="Sort by:", bg='#1a1a1a', fg='white').pack(side=tk.LEFT, padx=5)
        
        self.sort_options = ttk.Combobox(sort_frame, values=[
            "None",
            "Date (newest first)", 
            "Date (oldest first)",
            "Profit (highest first)", 
            "Profit (lowest first)",
            "Position",
            "Stake"
        ])
        self.sort_options.current(0)
        self.sort_options.pack(side=tk.LEFT, padx=5)
        
        self.apply_sort_button = tk.Button(
            sort_frame, 
            text="Apply Sort", 
            command=self.apply_sort,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.apply_sort_button.pack(side=tk.LEFT, padx=5)
        
        # Add filter options
        filter_frame = tk.Frame(top_frame, bg=DARK_BG)
        filter_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(filter_frame, text="Filter:", bg=DARK_BG, fg=TEXT_COLOR).pack(side=tk.LEFT, padx=5)
        
        self.filter_options = ttk.Combobox(filter_frame, values=[
            "None",
            "Position",
            "Stake",
            "Date Range",
            "Profit Range"
        ])
        self.filter_options.current(0)
        self.filter_options.pack(side=tk.LEFT, padx=5)
        
        self.filter_value = tk.Entry(filter_frame, width=15)
        self.filter_value.pack(side=tk.LEFT, padx=5)
        
        self.apply_filter_button = tk.Button(
            filter_frame, 
            text="Apply Filter", 
            command=self.apply_hand_filters,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.apply_filter_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_filter_button = tk.Button(
            filter_frame, 
            text="Clear Filters", 
            command=self.clear_hand_filters,
            bg=ACCENT_COLOR,
            fg=TEXT_COLOR
        )
        self.clear_filter_button.pack(side=tk.LEFT, padx=5)
        
        # Create treeview for hands
        self.tree_frame = tk.Frame(self.import_frame, bg=DARK_BG)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure the style for the treeview
        self.style.configure("Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR, 
                        fieldbackground=DARK_MEDIUM_BG,
                        rowheight=25)
        self.style.configure("Treeview.Heading", 
                        background=DARK_BG, 
                        foreground=TEXT_COLOR)
        self.style.map('Treeview', background=[('selected', ACCENT_COLOR)])
        
        # Create scrollbars
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal")
        
        # Create the treeview with updated columns
        self.tree = ttk.Treeview(self.tree_frame, columns=("date", "hand_id", "position", "stake", "cards", "profit"), 
                                 show="headings", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Configure scrollbars
        vsb.configure(command=self.tree.yview)
        hsb.configure(command=self.tree.xview)
        
        # Place scrollbars
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Place treeview
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns
        self.tree.heading("date", text="Date", command=lambda: self.sort_by_column("date"))
        self.tree.heading("hand_id", text="Hand ID", command=lambda: self.sort_by_column("hand_id"))
        self.tree.heading("position", text="Position", command=lambda: self.sort_by_column("position"))
        self.tree.heading("stake", text="Stake", command=lambda: self.sort_by_column("stake"))
        self.tree.heading("cards", text="Cards")
        self.tree.heading("profit", text="Profit", command=lambda: self.sort_by_column("profit"))
        
        self.tree.column("date", width=150, anchor=tk.W)
        self.tree.column("hand_id", width=100, anchor=tk.W)
        self.tree.column("position", width=80, anchor=tk.CENTER)
        self.tree.column("stake", width=80, anchor=tk.CENTER)
        self.tree.column("cards", width=100, anchor=tk.CENTER)
        self.tree.column("profit", width=100, anchor=tk.E)
        
        # Bind double-click event
        self.tree.bind("<Double-1>", self.on_row_double_click)
        
        # Status bar
        self.status_bar = tk.Label(
            self.import_frame, 
            text="Ready", 
            bd=1, 
            relief=tk.SUNKEN, 
            anchor=tk.W,
            bg='#1a1a1a',
            fg='white'
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Populate the treeview
        self.refresh_import_tab()

    def generate_hand_combinations(self):
        """Generate all possible poker hand combinations in a standardized format."""
        RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        hands = []
        
        # Generate pairs
        for rank in RANKS:
            hands.append(f"{rank}{rank}")
        
        # Generate suited and offsuit hands
        for i, rank1 in enumerate(RANKS):
            for rank2 in RANKS[i+1:]:
                hands.append(f"{rank1}{rank2}s")  # suited
                hands.append(f"{rank1}{rank2}o")  # offsuit
        
        return sorted(hands)

    def import_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Select Hand History Files (TXT or ZIP)",
            filetypes=[("Text Files","*.txt"),("ZIP Files","*.zip"),("All Files","*.*")]
        )
        if not file_paths:
            return
        for fp in file_paths:
            if fp.lower().endswith(".zip"):
                txt_files = extract_txt_from_zip(fp)
                for txt in txt_files:
                    hands = parse_hand_history_file(txt)
                    if hands:
                        insert_hand_details(hands)
            elif fp.lower().endswith(".txt"):
                hands = parse_hand_history_file(fp)
                if hands:
                    insert_hand_details(hands)
            else:
                messagebox.showwarning("Unsupported File", f"Skipping {fp}")
        self.refresh_import_tab()
        self.refresh_graph_tab()
        self.update_leak_display()

    def refresh_import_tab(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        # Apply the current sort option if one is selected
        if hasattr(self, 'sort_options') and self.sort_options.get() and self.sort_options.get() != "None":
            self.apply_sort()
        else:
            # Default behavior - show all hands with newest first
            self.refresh_import_tab_no_sort()

    def on_row_double_click(self, event):
        """Handle double-click on a hand history row."""
        # Check if any item is selected
        selection = self.tree.selection()
        if not selection:
            return  # No item selected, do nothing
        
        item = selection[0]
        values = self.tree.item(item, "values")
        hand_id = values[1]  # Hand ID is now in the second column (index 1)
        
        # Fetch full hand details
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Get column names
        c.execute("PRAGMA table_info(hands)")
        column_names = [info[1] for info in c.fetchall()]
        
        # Fetch the hand data
        c.execute("SELECT * FROM hands WHERE hand_id = ?", (hand_id,))
        hand_data_tuple = c.fetchone()
        conn.close()
        
        if not hand_data_tuple:
            return
        
        # Convert to dictionary
        hand_data = dict(zip(column_names, hand_data_tuple))
        
        # Create a new window to display hand details
        hand_window = tk.Toplevel(self)
        hand_window.title(f"Hand Details: {hand_id}")
        hand_window.geometry("800x600")
        hand_window.configure(bg=self.colors['bg_dark'])
        
        # Create a frame for the hand details
        details_frame = self.create_hand_details_frame(hand_window, hand_data)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def clear_hands(self):
        """Clear all hands from the database after confirmation."""
        result = messagebox.askquestion(
            "Clear All Hands",
            "Are you sure you want to delete all hands from the database?\nThis action cannot be undone.",
            icon='warning'
        )
        
        if result == 'yes':
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM hands")
            conn.commit()
            conn.close()
            
            # Refresh all tabs
            self.refresh_import_tab()
            self.refresh_graph_tab()
            self.update_leak_display()
            
            messagebox.showinfo("Success", "All hands have been cleared from the database.")

    ###############
    ###  GRAPH  ###
    ###############
    def create_graph_tab(self):
        # Main container for the graph tab
        self.graph_container = tk.Frame(self.graph_frame, bg='#1a1a1a')  # Change background to match Range tab
        self.graph_container.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        self.graph_container.grid_rowconfigure(0, weight=4)  # Top section gets 80%
        self.graph_container.grid_rowconfigure(1, weight=1)  # Bottom section gets 20%
        self.graph_container.grid_columnconfigure(0, weight=1)  # Left column
        self.graph_container.grid_columnconfigure(1, weight=4)  # Right column (wider)
        
        # Left panel (narrow column)
        left_panel = tk.Frame(self.graph_container, bd=2, relief=tk.GROOVE, bg='#1a1a1a')
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure left panel with two sections
        left_panel.grid_rowconfigure(0, weight=6)  # Stats section 60%
        left_panel.grid_rowconfigure(1, weight=4)  # Stakes section 40%
        left_panel.grid_columnconfigure(0, weight=1)
        
        # Stats section
        self.stats_section = tk.Frame(left_panel, bg='#1a1a1a', bd=2, relief=tk.GROOVE)
        self.stats_section.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create a fixed-width label for stats to prevent resizing
        self.stats_label = tk.Label(
            self.stats_section,
            text="Total Profit: $0.00\nTotal Profit (BB): 0 BB\nBB/100: 0\nRake & Jackpot Paid: $0.00\nTotal Hands: 0",
            bg='#1a1a1a',
            fg='white',
            font=("Arial", 12),
            justify=tk.LEFT,
            width=30,  # Fixed width to prevent resizing
            anchor="nw"
        )
        self.stats_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add a separator
        separator = tk.Frame(self.stats_section, height=1, bg='gray')
        separator.pack(fill=tk.X, padx=5, pady=5)
        
        # Add "Deduct Rake" checkbox at the bottom
        self.deduct_rake_var = tk.BooleanVar(value=False)
        
        # Create a frame to hold the checkbox and rakeback entry
        self.rake_frame = tk.Frame(self.stats_section, bg=DARK_BG)
        self.rake_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.deduct_rake_check = tk.Checkbutton(
            self.rake_frame,
            text="Deduct Rake",
            bg=DARK_BG,
            fg=TEXT_COLOR,
            selectcolor=DARK_BG,
            activebackground=DARK_BG,
            activeforeground=TEXT_COLOR,
            variable=self.deduct_rake_var,
            command=self.refresh_graph_tab
        )
        self.deduct_rake_check.pack(side=tk.LEFT, anchor=tk.W)
        
        # Add Rakeback % label and entry
        tk.Label(self.rake_frame, text="Rakeback %:", bg=DARK_BG, fg=TEXT_COLOR).pack(side=tk.LEFT, padx=(10, 5))
        
        # Create a StringVar for the rakeback percentage with default value of 0
        # self.rakeback_var = tk.StringVar(value="0")  # Now initialized in __init__
        
        # Validate function to ensure only numbers and a single decimal point are entered
        def validate_rakeback(value):
            if value == "":
                return True
            try:
                # Allow for decimal input
                if value.count('.') <= 1:
                    # Check if it's a valid float between 0 and 100
                    val = float(value)
                    return 0 <= val <= 100
                return False
            except ValueError:
                return False
        
        # Register the validation command
        validate_cmd = self.register(validate_rakeback)
        
        # Create the entry widget with validation
        self.rakeback_entry = tk.Entry(
            self.rake_frame, 
            textvariable=self.rakeback_var, 
            width=5,
            validate="key", 
            validatecommand=(validate_cmd, '%P')
        )
        self.rakeback_entry.pack(side=tk.LEFT)
        
        # Add % sign label
        tk.Label(self.rake_frame, text="%", bg=DARK_BG, fg=TEXT_COLOR).pack(side=tk.LEFT)
        
        # Function to save rakeback percentage
        def save_rakeback_percentage(event=None):
            try:
                rakeback_pct = self.rakeback_var.get()
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                         ('rakeback_percentage', rakeback_pct))
                print(f"Rakeback percentage saved: {rakeback_pct}")
                conn.commit()
                conn.close()
                self.refresh_graph_tab()
                self.update_adjusted_profit()
            except Exception as e:
                print(f"Error saving rakeback: {e}")
        
        # Bind the entry to update the graph when Enter is pressed or focus is lost
        self.rakeback_entry.bind("<Return>", save_rakeback_percentage)
        self.rakeback_entry.bind("<FocusOut>", save_rakeback_percentage)
        
        # Stakes section (in its own frame with border)
        self.stakes_section = tk.Frame(left_panel, bg='#1a1a1a', bd=2, relief=tk.GROOVE)
        self.stakes_section.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create stake buttons
        stakes = ['All']  # Will be populated with actual stakes
        self.stake_buttons = {}
        self.selected_stake = None  # Default to All Stakes selected
        
        # Create or update stake buttons
        # First, remove any existing buttons
        for widget in self.stakes_section.winfo_children():
            widget.destroy()
        
        # Create new buttons for each stake
        self.stake_buttons = {}
        for stake in stakes:
            btn = tk.Button(
                self.stakes_section,
                text=stake if stake != 'All' else 'All Stakes',
                bg='#00ace6' if stake == 'All' else '#1c1c1c',  # All Stakes is selected by default
                fg='white',
                font=("Arial", 10),
                command=lambda s=stake: self.filter_by_stake(s)
            )
            btn.pack(fill=tk.X, padx=5, pady=2)
            self.stake_buttons[stake] = btn

        # Graph panel (wide right column)
        self.fig = Figure(figsize=(6,4), dpi=100, facecolor='#1a1a1a')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1a1a1a')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_container)
        self.canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Position panel (bottom spanning both columns)
        self.position_panel = tk.Frame(self.graph_container, bd=2, relief=tk.GROOVE, bg='#1a1a1a')
        self.position_panel.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        
        # Create position buttons in horizontal layout
        positions = ['All', 'BB', 'SB', 'BTN', 'CO', 'HJ', 'UTG']
        self.position_buttons = {}
        self.selected_position = None
        
        # Create a frame for the buttons
        button_frame = tk.Frame(self.position_panel, bg='#1a1a1a')
        button_frame.pack(expand=True, pady=20)
        
        for i, pos in enumerate(positions):
            btn = tk.Button(
                button_frame,
                text=f"{pos}\nWinloss: $0.00\nHands: 0",
                bg='#00ace6' if pos == 'All' else '#1c1c1c',  # Use new color for buttons
                fg='white',
                font=("Arial", 10),
                width=15,
                height=4,
                command=lambda p=pos: self.filter_by_position(p)
            )
            btn.grid(row=0, column=i, padx=5)
            self.position_buttons[pos] = btn
            
        # Initialize the graph with data
        self.refresh_graph_tab()

    def filter_by_position(self, position):
        """Filter graph data by selected position"""
        if position == 'All':
            self.selected_position = None
        else:
            if self.selected_position == position:
                self.selected_position = None  # Deselect if already selected
            else:
                self.selected_position = position
        
        # Update button appearances
        for pos, btn in self.position_buttons.items():
            if (pos == 'All' and self.selected_position is None) or pos == self.selected_position:
                btn.config(bg='#00ace6')  # Use new color for selected buttons
            else:
                btn.config(bg='#1c1c1c')  # Normal
            
        self.refresh_graph_tab()

    def filter_by_stake(self, stake):
        """Filter graph data by selected stake"""
        if stake == 'All':
            self.selected_stake = None
        else:
            if self.selected_stake == stake:
                self.selected_stake = None  # Deselect if already selected
            else:
                self.selected_stake = stake
        
        # Update button appearances
        for s, btn in self.stake_buttons.items():
            if (s == 'All' and self.selected_stake is None) or s == self.selected_stake:
                btn.config(bg='#00ace6')  # Use new color for selected buttons
            else:
                btn.config(bg='#1c1c1c')  # Normal
            
        self.refresh_graph_tab()

    def refresh_graph_tab(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Get all unique stakes from the database
        c.execute("SELECT DISTINCT stake FROM hands ORDER BY stake")
        stakes = ['All'] + [row[0] for row in c.fetchall()]
        
        # Create or update stake buttons
        # First, remove any existing buttons
        for widget in self.stakes_section.winfo_children():
            widget.destroy()
        
        # Create new buttons for each stake
        self.stake_buttons = {}
        for stake in stakes:
            btn = tk.Button(
                self.stakes_section,
                text=stake if stake != 'All' else 'All Stakes',
                bg='#1c1c1c' if stake != self.selected_stake and not (stake == 'All' and self.selected_stake is None) else '#00ace6',
                fg='white',
                font=("Arial", 10),
                command=lambda s=stake: self.filter_by_stake(s)
            )
            btn.pack(fill=tk.X, padx=5, pady=2)
            self.stake_buttons[stake] = btn

        # Determine which profit column to use based on checkbox and rakeback
        if self.deduct_rake_var.get():
            # If deducting rake, use adjusted_profit which includes rakeback
            profit_column = "adjusted_profit"
        else:
            # If not deducting rake, use hero_profit_with_rake
            profit_column = "hero_profit_with_rake"
        
        # Build query
        query = f"""
            SELECT 
                {profit_column} as profit,
                stake,
                hero_position,
                rake,
                jackpot,
                hero_profit
            FROM hands
            ORDER BY date_time
        """
        params = []
        
        # Apply stake filter if selected
        if self.selected_stake:
            query = f"""
                SELECT 
                    {profit_column} as profit,
                    stake,
                    hero_position,
                    rake,
                    jackpot,
                    hero_profit
                FROM hands
                WHERE stake = ?
                ORDER BY date_time
            """
            params = [self.selected_stake]
        
        # Apply position filter if selected
        if self.selected_position:
            if self.selected_stake:
                query = f"""
                    SELECT 
                        {profit_column} as profit,
                        stake,
                        hero_position,
                        rake,
                        jackpot,
                        hero_profit
                    FROM hands
                    WHERE stake = ? AND hero_position = ?
                    ORDER BY date_time
                """
                params = [self.selected_stake, self.selected_position]
            else:
                query = f"""
                    SELECT 
                        {profit_column} as profit,
                        stake,
                        hero_position,
                        rake,
                        jackpot,
                        hero_profit
                    FROM hands
                    WHERE hero_position = ?
                    ORDER BY date_time
                """
                params = [self.selected_position]
        
        c.execute(query, params)
        rows = c.fetchall()

        # Get rakeback percentage (convert from percentage to decimal)
        try:
            rakeback_pct = float(self.rakeback_var.get()) / 100.0
        except ValueError:
            rakeback_pct = 0.0
        
        # Ensure rakeback percentage is between 0 and 1
        rakeback_pct = max(0.0, min(1.0, rakeback_pct))
        
        # Calculate stats - now using the selected profit column directly
        total_profit = sum(row[0] for row in rows) if rows else 0
        total_hands = len(rows)
        
        # Calculate rake and jackpot totals - only for hands where Hero won
        # Always use hero_profit (not profit_with_rake) to determine winning hands
        total_rake = sum(row[3] for row in rows if row[5] > 0) if rows else 0
        total_jackpot = sum(row[4] for row in rows if row[5] > 0) if rows else 0
        total_rake_and_jackpot = total_rake + total_jackpot
        
        # Calculate BB stats
        if rows:
            # Convert stake strings like "$0.1/$0.2" to BB size (the larger number)
            stakes = [float(row[1].split('/')[-1].replace('$', '')) for row in rows]
            bb_profits = [row[0] / stake for row, stake in zip(rows, stakes)]
            total_bb = sum(bb_profits)
            bb_per_100 = (total_bb / total_hands) * 100 if total_hands > 0 else 0
        else:
            total_bb = 0
            bb_per_100 = 0

        # Update stats display in column format
        profit_type = "Profit (rake deducted)" if self.deduct_rake_var.get() else "Profit (with rake)"
        
        # Clear existing stats widgets
        for widget in self.stats_section.winfo_children():
            if widget != self.rake_frame:  # Keep the rake frame
                widget.destroy()
        
        # Create a frame for the stats with a grid layout
        stats_grid = tk.Frame(self.stats_section, bg=DARK_BG)
        stats_grid.pack(fill=tk.X, padx=5, pady=5, before=self.rake_frame)
        
        # Configure the grid columns
        stats_grid.columnconfigure(0, weight=1)  # Labels column
        stats_grid.columnconfigure(1, weight=1)  # Values column
        
        # Add stats rows
        row = 0
        
        # Total Profit
        tk.Label(stats_grid, text=f"Total {profit_type}:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"${total_profit:,.2f}", bg=DARK_BG, fg=PROFIT_COLOR if total_profit >= 0 else LOSS_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Total Profit (BB)
        tk.Label(stats_grid, text="Total Profit (BB):", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"{total_bb:,.2f} BB", bg=DARK_BG, fg=PROFIT_COLOR if total_bb >= 0 else LOSS_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # BB/100
        tk.Label(stats_grid, text="BB/100:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"{bb_per_100:.2f}", bg=DARK_BG, fg=PROFIT_COLOR if bb_per_100 >= 0 else LOSS_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Rake & Jackpot Paid
        tk.Label(stats_grid, text="Rake & Jackpot Paid:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"${total_rake_and_jackpot:,.2f}", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Total Hands
        tk.Label(stats_grid, text="Total Hands:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
        tk.Label(stats_grid, text=f"{total_hands:,}", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
        row += 1
        
        # Calculate additional stats if we have hands
        if total_hands > 0:
            # VPIP (Voluntarily Put $ In Pot) - percentage of hands where hero put money in preflop
            # Exclude hands where hero only contributed 1SB in SB position or 1BB in BB position
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE (
                    (hero_position = 'SB' AND hero_contribution > CAST(SUBSTR(stake, INSTR(stake, '$') + 1, INSTR(stake, '/') - INSTR(stake, '$') - 1) AS REAL))
                    OR (hero_position = 'BB' AND hero_contribution > CAST(SUBSTR(stake, INSTR(stake, '/') + 2) AS REAL))
                    OR (hero_position NOT IN ('SB', 'BB') AND hero_contribution > 0)
                )
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            vpip_hands = c.fetchone()[0]
            vpip_percentage = (vpip_hands / total_hands) * 100 if total_hands > 0 else 0
            
            # PFR (Preflop Raise) - percentage of hands where hero raised preflop
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE preflop_scenario IN ('open (single raised)', '3bet', '4bet', '5bet+')
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            pfr_hands = c.fetchone()[0]
            pfr_percentage = (pfr_hands / total_hands) * 100 if total_hands > 0 else 0
            
            # 3bet% - percentage of hands where hero 3bet when had opportunity
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE preflop_scenario = '3bet'
                AND had_3bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            threebet_hands = c.fetchone()[0]
            
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE had_3bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            threebet_op_hands = c.fetchone()[0]
            threebet_percentage = (threebet_hands / threebet_op_hands) * 100 if threebet_op_hands > 0 else 0
            
            # 4bet% - percentage of hands where hero 4bet when had opportunity
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE preflop_scenario = '4bet'
                AND had_4bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            fourbet_hands = c.fetchone()[0]
            
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE had_4bet_op = 1
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            fourbet_op_hands = c.fetchone()[0]
            fourbet_percentage = (fourbet_hands / fourbet_op_hands) * 100 if fourbet_op_hands > 0 else 0
            
            # WTSD (Went To ShowDown) - percentage of hands that went to showdown
            c.execute("""
                SELECT COUNT(*) FROM hands 
                WHERE river_action IS NOT NULL AND river_action != ''
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            wtsd_hands = c.fetchone()[0]
            wtsd_percentage = (wtsd_hands / total_hands) * 100 if total_hands > 0 else 0
            
            # W$SD (Won money at ShowDown) - percentage of showdowns where hero won money
            c.execute(f"""
                SELECT COUNT(*) FROM hands 
                WHERE river_action IS NOT NULL AND river_action != ''
                AND {profit_column} > 0
                AND (stake = ? OR ? IS NULL)
                AND (hero_position = ? OR ? IS NULL)
            """, (self.selected_stake, self.selected_stake, self.selected_position, self.selected_position))
            won_sd_hands = c.fetchone()[0]
            wsd_percentage = (won_sd_hands / wtsd_hands) * 100 if wtsd_hands > 0 else 0
            
            # Display the new stats
            # VPIP
            tk.Label(stats_grid, text="VPIP:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{vpip_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # PFR
            tk.Label(stats_grid, text="PFR:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{pfr_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # 3bet%
            tk.Label(stats_grid, text="3bet%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{threebet_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # 4bet%
            tk.Label(stats_grid, text="4bet%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{fourbet_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # WTSD%
            tk.Label(stats_grid, text="WTSD%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{wtsd_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
            
            # W$SD%
            tk.Label(stats_grid, text="W$SD%:", bg=DARK_BG, fg=TEXT_COLOR, anchor='w').grid(row=row, column=0, sticky='w', padx=5, pady=2)
            tk.Label(stats_grid, text=f"{wsd_percentage:.1f}%", bg=DARK_BG, fg=TEXT_COLOR, anchor='e').grid(row=row, column=1, sticky='e', padx=5, pady=2)
            row += 1
        
        # Add a separator
        separator = tk.Frame(self.stats_section, height=1, bg='gray')
        separator.pack(fill=tk.X, padx=5, pady=5, before=self.rake_frame)

        if not rows:
            self.ax.clear()
            self.ax.set_title("No Data", color='white')
            self.canvas.draw()
            return

        # Calculate cumulative profit
        cumulative = []
        total = 0.0
        for profit, _, _, _, _, _ in rows:
            total += profit
            cumulative.append(total)

        # Create x-axis values (hand numbers)
        x_vals = list(range(1, len(cumulative) + 1))

        # Clear and redraw with dark theme
        self.ax.clear()
        self.ax.grid(True, color='gray', alpha=0.3)
        
        # Determine line color based on final profit
        line_color = '#00ace6' if cumulative[-1] >= 0 else '#CC0000'  # Blue if positive/zero, Red if negative
        
        line, = self.ax.plot(x_vals, cumulative, linestyle='-', color=line_color, linewidth=2, marker='o', markersize=2)

        # Style the axes
        self.ax.set_xlabel("Hand Number (Chronological)", color='white')
        profit_label = "Cumulative Profit (rake deducted) ($)" if self.deduct_rake_var.get() else "Cumulative Profit (with rake) ($)"
        self.ax.set_ylabel(profit_label, color='white')
        title = "Hero's Cumulative Profit" if not self.selected_position else f"Hero's Cumulative Profit - {self.selected_position}"
        self.ax.set_title(title, color='white')
        self.ax.tick_params(colors='white')
        for spine in self.ax.spines.values():
            spine.set_color('white')
            
        # Move y-axis ticks to the right side
        self.ax.yaxis.tick_right()
        # But keep the y-axis label on the left
        self.ax.yaxis.set_label_position('left')

        # Update position button stats
        for position, btn in self.position_buttons.items():
            if position == 'All':
                c.execute(f"""
                    SELECT 
                        SUM({profit_column}) as winloss,
                        COUNT(*) as total_hands
                    FROM hands
                """)
            else:
                c.execute(f"""
                    SELECT 
                        SUM({profit_column}) as winloss,
                        COUNT(*) as total_hands
                    FROM hands 
                    WHERE hero_position = ?
                """, (position,))
            
            row = c.fetchone()
            if row and row[1] > 0:  # if there are hands for this position
                winloss = row[0] or 0
                total_hands = row[1] or 0
                
                btn.config(text=f"{position}\nWinloss: ${winloss:.2f}\nHands: {total_hands}")
            else:
                btn.config(text=f"{position}\nWinloss: $0.00\nHands: 0")

        conn.close()

        # Store data as class attributes
        self.x_vals = x_vals
        self.cumulative = cumulative

        def motion_hover(event):
            if event.inaxes != self.ax:
                # Remove any existing vertical line
                if hasattr(self, 'v_line') and self.v_line in self.ax.lines:
                    self.v_line.remove()
                # Remove annotations
                for artist in self.ax.texts:
                    if hasattr(artist, 'is_hover_annotation'):
                        artist.remove()
                self.canvas.draw_idle()
                return

            # Get nearest x value
            x_coord = int(round(event.xdata))
            if x_coord < 1 or x_coord > len(self.x_vals):
                return

            # Get corresponding y value
            y_coord = self.cumulative[x_coord - 1]

            # Remove old vertical line if it exists
            if hasattr(self, 'v_line') and self.v_line in self.ax.lines:
                self.v_line.remove()

            # Add new vertical line
            self.v_line = self.ax.axvline(x=x_coord, color='grey', linestyle=':', alpha=0.5)

            # Remove old annotation
            for artist in self.ax.texts:
                if hasattr(artist, 'is_hover_annotation'):
                    artist.remove()

            # Determine if we're close to the right edge of the graph
            # Get the figure width in data coordinates
            x_min, x_max = self.ax.get_xlim()
            # If we're in the right 20% of the graph, place annotation to the left
            x_offset = -60 if event.xdata > (x_max - (x_max - x_min) * 0.2) else 10
            
            # Create new annotation at cursor position
            annotation = self.ax.annotate(
                f'Hand: {x_coord:,}\nProfit: ${y_coord:.2f}',
                xy=(event.xdata, event.ydata),
                xytext=(x_offset, 10),
                textcoords='offset points',
                bbox=dict(
                    boxstyle='round,pad=0.5',
                    fc='black',
                    alpha=0.8,
                    ec='white'
                ),
                color='white'
            )
            annotation.is_hover_annotation = True

            # Use blit for faster rendering - only update the changed parts
            self.canvas.draw_idle()

        # Connect the hover event
        self.canvas.mpl_connect('motion_notify_event', motion_hover)

        # Set figure background
        self.fig.patch.set_facecolor('#1a1a1a')
        
        # Draw with tight layout
        self.fig.tight_layout()
        self.canvas.draw()

    ###############
    ###  RANGE  ###
    ###############
    def create_range_tab(self):
        """Create the range analysis tab with scenario buttons and grid display."""
        DARK_BG = '#1a1a1a'
        DARK_BUTTON = '#2d2d2d'
        DARK_BUTTON_SELECTED = '#3c3c3c'
        TEXT_COLOR = 'white'
        POSITION_SECTION_HEIGHT = 100
        GRID_SIZE = 780
        
        # Configure grid weights for the main frame
        self.range_frame.grid_rowconfigure(0, weight=6)  # Top section gets 80%
        self.range_frame.grid_rowconfigure(1, weight=4)  # Bottom section gets 20%
        self.range_frame.grid_columnconfigure(0, weight=7)  # Left section gets 80%
        self.range_frame.grid_columnconfigure(1, weight=3)  # Right section gets 20%
        self.range_frame.configure(bg=DARK_BG)
        
        # Create the three main sections
        # Top left - Range grid
        range_section = tk.Frame(self.range_frame, bg=DARK_BG, bd=1, relief='solid')
        range_section.grid(row=0, column=0, sticky="nsew")
        
        # Top right - Other buttons
        buttons_section = tk.Frame(self.range_frame, bg=DARK_BG, bd=1, relief='solid')
        buttons_section.grid(row=0, column=1, sticky="nsew")
        
        # Bottom - Position buttons
        position_section = tk.Frame(self.range_frame, bg=DARK_BG, bd=1, relief='solid')
        position_section.grid(row=1, column=0, columnspan=2, sticky="nsew")
        
        # Configure the range grid section
        range_section.grid_rowconfigure(0, weight=1)
        range_section.grid_columnconfigure(0, weight=1)
        
        # Create legend frame to the left of the grid
        legend_frame = tk.Frame(range_section, bg=DARK_BG)
        legend_frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Add legend items
        legend_items = [
            ("Fold", "#737382"),
            ("Raise", "#00ace6"),
            ("Call", "#d571b2")
        ]
        
        for text, color in legend_items:
            item_frame = tk.Frame(legend_frame, bg=DARK_BG)
            item_frame.pack(anchor='w', pady=5)
            
            color_box = tk.Canvas(item_frame, width=20, height=20, bg=color, highlightthickness=0)
            color_box.pack(side=tk.LEFT, padx=5)
            
            label = tk.Label(item_frame, text=text, bg=DARK_BG, fg=TEXT_COLOR, font=("Arial", 10))
            label.pack(side=tk.LEFT)
        
        # Create grid frame with fixed size and centered
        self.range_grid_frame = tk.Frame(range_section, bg=DARK_BG, width=GRID_SIZE, height=GRID_SIZE)
        self.range_grid_frame.pack(expand=False, padx=(150, 0), pady=20)  # Center the grid
        self.range_grid_frame.grid_propagate(False)
        
        # Configure grid weights for centering
        for i in range(13):
            self.range_grid_frame.grid_rowconfigure(i, weight=1)
            self.range_grid_frame.grid_columnconfigure(i, weight=1)
        
        # Create 13x13 grid of canvas widgets
        SQUARE_SIZE = GRID_SIZE // 13  # Calculate square size based on grid size
        self.grid_squares = []
        for i in range(13):
            row = []
            for j in range(13):
                canvas = tk.Canvas(
                    self.range_grid_frame,
                    width=SQUARE_SIZE,
                    height=SQUARE_SIZE,
                    bg=DARK_BG,
                    highlightthickness=1,
                    highlightbackground='white'
                )
                canvas.grid(row=i, column=j, sticky="nsew")
                row.append(canvas)
            self.grid_squares.append(row)
        
        # Configure buttons section
        # Update scenarios and labels
        self.scenarios = ['open', 'faces_open', 'faces_3bet']
        self.scenario_labels = {
            'open': 'Raise First In',
            'faces_open': 'Facing Raise',
            'faces_3bet': 'Facing 3-Bet'
        }
        
        self.selected_scenario = tk.StringVar(value='open')  # Default to 'open'
        
        # Center the buttons vertically in their section
        buttons_section.grid_rowconfigure(0, weight=1)
        buttons_section.grid_columnconfigure(0, weight=1)
        
        # Store this as self.range_buttons_frame instead of button_container
        self.range_buttons_frame = tk.Frame(buttons_section, bg=DARK_BG)
        self.range_buttons_frame.grid(row=0, column=0)
        
        # Create scenario buttons with hand counts
        self.scenario_buttons = {}
        for scenario in self.scenarios:
            button_frame = tk.Frame(self.range_buttons_frame, bg=DARK_BG)
            button_frame.pack(pady=5)
            
            btn = tk.Button(
                button_frame,
                text=self.scenario_labels[scenario],
                bg=DARK_BUTTON,
                fg=TEXT_COLOR,
                width=20,
                height=2,
                font=("Arial", 11),
                command=lambda s=scenario: self.update_range_display(s)
            )
            btn.pack()
            
            # Add hand count label
            count_label = tk.Label(
                button_frame,
                text=self.get_scenario_hand_count(scenario),  # Initialize with actual count
                bg=DARK_BG,
                fg=TEXT_COLOR,
                font=("Arial", 9)
            )
            count_label.pack()
            
            self.scenario_buttons[scenario] = (btn, count_label)
        
        # Configure position section
        position_section.grid_rowconfigure(0, weight=1)
        position_section.grid_columnconfigure(0, weight=1)
        
        position_container = tk.Frame(position_section, bg=DARK_BG)
        position_container.grid(row=0, column=0)
        
        # Add 'All' to positions
        positions = ['All', 'BB', 'SB', 'BTN', 'CO', 'HJ', 'UTG']
        self.range_position_buttons = {}
        self.selected_position = None  # Default to None (All positions)
        
        for i, pos in enumerate(positions):
            btn = tk.Button(
                position_container,
                text=pos,
                bg='#00ace6' if pos == 'All' else DARK_BUTTON,  # All is selected by default
                fg=TEXT_COLOR,
                font=("Arial", 10),
                width=15,
                height=2,
                command=lambda p=pos: self.filter_range_by_position(p)
            )
            btn.grid(row=0, column=i, padx=5)
            self.range_position_buttons[pos] = btn
        
        # Stats label
        self.range_stats_label = tk.Label(
            range_section, 
            text="", 
            font=("Arial", 10),
            bg=DARK_BG,
            fg=TEXT_COLOR
        )
        self.range_stats_label.pack(side=tk.BOTTOM, pady=5)
        
        # Initial display - show all positions with 'open' scenario
        self.update_range_display('open')

    def filter_range_by_position(self, position):
        """Filter range data by selected position"""
        if position == 'All':
            # When All is selected, show data from all positions
            self.selected_position = None
        else:
            if self.selected_position == position:
                self.selected_position = None  # Deselect if already selected
            else:
                self.selected_position = position
        
        # Update button appearances
        for pos, btn in self.range_position_buttons.items():
            if (pos == 'All' and self.selected_position is None) or pos == self.selected_position:
                btn.config(bg='#00ace6')
            else:
                btn.config(bg='#2d2d2d')
        
        # Update hand counts for all scenarios
        for scenario, (_, count_label) in self.scenario_buttons.items():
            count = self.get_scenario_hand_count(scenario)
            count_label.config(text=count)
        
        # Update the range display
        self.update_range_display(self.selected_scenario.get())

    def update_range_display(self, scenario):
        """Update the range grid display for the selected scenario."""
        self.selected_scenario.set(scenario)
        
        # Update button appearances and hand counts
        for s, (btn, count_label) in self.scenario_buttons.items():
            is_selected = (s == scenario)
            btn.config(bg='#00ace6' if is_selected else '#2d2d2d')
            
            # Update hand count for each scenario button
            count = self.get_scenario_hand_count(s)
            count_label.config(text=count)
        
        # Colors for the display
        FOLD_COLOR = "#737382"   # Light gray-purple
        RAISE_COLOR = "#00ace6"  # Light blue
        CALL_COLOR = "#d571b2"   # Pink
        
        # Get stats
        stats = calculate_range_stats(scenario, self.selected_position)
        
        # Initialize counters
        total_hands = 0
        total_raises = 0
        total_calls = 0
        
        # Update each square in the grid
        for i, r1 in enumerate(RANKS):
            for j, r2 in enumerate(RANKS):
                canvas = self.grid_squares[i][j]
                canvas.delete("all")  # Clear existing content
                
                width = canvas.winfo_reqwidth()
                height = canvas.winfo_reqheight()
                
                # Determine the hand type
                if i == j:  # Pair
                    hand = r1 + r1
                elif i < j:  # Suited
                    hand = r1 + r2 + "s"
                else:  # Offsuit
                    hand = r2 + r1 + "o"
                
                # Get stats: (total, raises, calls, raise%, call%)
                count, raises, calls, raise_pct, call_pct = stats.get(hand, (0, 0, 0, 0, 0))
                
                if count > 0:
                    # Calculate widths for each section
                    fold_pct = 100 - raise_pct - call_pct
                    fold_width = width * fold_pct / 100
                    raise_width = width * raise_pct / 100
                    call_width = width * call_pct / 100
                    
                    # Draw sections
                    x = 0
                    if fold_pct > 0:
                        canvas.create_rectangle(x, 0, x + fold_width, height, fill=FOLD_COLOR, outline="")
                        x += fold_width
                    if raise_pct > 0:
                        canvas.create_rectangle(x, 0, x + raise_width, height, fill=RAISE_COLOR, outline="")
                        x += raise_width
                    if call_pct > 0:
                        canvas.create_rectangle(x, 0, x + call_width, height, fill=CALL_COLOR, outline="")
                    
                    # Add text overlay - just hand name and total count
                    text_color = 'white'
                    canvas.create_text(width/2, height/2, 
                                     text=f"{hand}\n({count})", 
                                     fill=text_color, 
                                     font=("Arial", 9, "bold"),
                                     justify='center')
                else:
                    # Draw empty square
                    canvas.create_rectangle(0, 0, width, height, fill='#1a1a1a', outline="")
                    canvas.create_text(width/2, height/2, text=hand, fill='#666666', font=("Arial", 9))
                
                total_hands += count
                total_raises += raises
                total_calls += calls
        
        # Update stats label
        if total_hands > 0:
            total_raise_pct = (total_raises / total_hands) * 100
            total_call_pct = (total_calls / total_hands) * 100
            self.range_stats_label.config(
                text=f"Total hands: {total_hands}, Raise: {total_raise_pct:.1f}%, Call: {total_call_pct:.1f}%"
            )
        else:
            self.range_stats_label.config(text="No data available")

    def get_scenario_hand_count(self, scenario):
        """Get the total number of hands for a given scenario."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        query = "SELECT COUNT(*) FROM hands WHERE "
        params = []
        
        # Add scenario-specific conditions
        if scenario == 'open':
            query += "had_rfi_opportunity = 1"
        elif scenario == 'faces_open':
            query += "had_3bet_op = 1"
        elif scenario == 'faces_3bet':
            query += "had_4bet_op = 1"
        else:
            query += "1=1"  # Default case
        
        # Add position filter if selected
        if self.selected_position and self.selected_position != 'All':
            query += " AND hero_position = ?"
            params.append(self.selected_position)
        
        c.execute(query, params)
        count = c.fetchone()[0]
        conn.close()
        
        return f"{count} hands"

    def apply_hand_filters(self):
        """Apply the selected filters to the hand history display."""
        cards = [self.cards_filter.get(idx) for idx in self.cards_filter.curselection()]
        position = self.position_filter.get()
        opportunity = self.opportunity_filter.get()
        
        # Clear current display
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        # Build query
        query = """
            SELECT hand_id, date_time, stake, hero_position, hero_cards,
                   total_pot, rake, jackpot, ROUND(hero_profit, 2) as hero_profit,
                   ROUND(hero_profit_with_rake, 2) as hero_profit_with_rake
            FROM hands
            WHERE 1=1
        """
        params = []
        
        # Add card filter
        if cards:
            card_conditions = []
            for hand in cards:
                if len(hand) == 2:  # Pair
                    # For pairs like "AA", match any two aces
                    rank = hand[0]
                    # Need to find two of the same rank in the hand
                    card_conditions.append("""
                        (hero_cards LIKE ? AND 
                         (
                            (substr(hero_cards, 1, 1) = ? AND substr(hero_cards, 4, 1) = ?) OR
                            (substr(hero_cards, 1, 1) = ? AND substr(hero_cards, 4, 1) = ?)
                         )
                        )
                    """)
                    params.extend([f"%{rank}%", rank, rank, rank, rank])
                elif len(hand) == 3:  # Suited or offsuit
                    rank1, rank2 = hand[0], hand[1]
                    suited = hand.endswith('s')
                    
                    if suited:
                        # For suited hands like "AKs", both cards must have the same suit
                        card_conditions.append("""
                            (hero_cards LIKE ? AND hero_cards LIKE ? AND 
                             substr(hero_cards, 2, 1) = substr(hero_cards, 5, 1))
                        """)
                        params.extend([f"%{rank1}%", f"%{rank2}%"])
                    else:  # offsuit
                        # For offsuit hands like "AKo", cards must have different suits
                        card_conditions.append("""
                            (hero_cards LIKE ? AND hero_cards LIKE ? AND 
                             substr(hero_cards, 2, 1) != substr(hero_cards, 5, 1))
                        """)
                        params.extend([f"%{rank1}%", f"%{rank2}%"])
            
            if card_conditions:
                query += " AND (" + " OR ".join(card_conditions) + ")"
        
        # Add position filter
        if position != 'All':
            query += " AND hero_position = ?"
            params.append(position)
        
        # Add opportunity filter
        if opportunity != 'All':
            if opportunity == 'RFI':
                query += " AND had_rfi_opportunity = 1"
            elif opportunity == '3-Bet':
                query += " AND had_3bet_op = 1"
            elif opportunity == '4-Bet':
                query += " AND had_4bet_op = 1"
        
        # Execute query and update display
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        
        c.execute("SELECT hand_id, hero_cards FROM hands LIMIT 10")
        sample_cards = c.fetchall()
        
        conn.close()
        
        for row in rows:
            self.tree.insert("", tk.END, values=row)
        
        # Update status
        status_text = f"Showing {len(rows)} hands"
        if cards or position != 'All' or opportunity != 'All':
            status_text += " (filtered)"
        self.range_stats_label.config(text=status_text)

    def clear_hand_filters(self):
        """Clear all hand filters and show all hands."""
        self.cards_filter.selection_clear(0, tk.END)
        self.position_filter.set('All')
        self.opportunity_filter.set('All')
        self.refresh_import_tab()

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

    def sort_by_column(self, column):
        """Sort the treeview by a specific column."""
        # Get all items in the treeview
        items = [(self.tree.set(k, column), k) for k in self.tree.get_children('')]
        
        # Check if we're reversing the sort
        reverse = False
        if self.tree.heading(column, 'text').endswith('↑'):
            reverse = True
        
        # Sort based on column type
        if column == "profit":
            # Convert to float for numeric sorting
            items.sort(key=lambda x: float(x[0]) if x[0] else 0, reverse=reverse)
        else:
            # Regular string sorting
            items.sort(reverse=reverse)
        
        # Rearrange items in sorted positions
        for index, (_, item) in enumerate(items):
            self.tree.move(item, '', index)
        
        # Update the headings to show the sort arrow
        for col in self.tree['columns']:
            if col == column:
                # Get the original heading text without arrows
                heading_text = self.tree.heading(col, 'text')
                if '↑' in heading_text or '↓' in heading_text:
                    heading_text = heading_text.rstrip('↑↓')
                self.tree.heading(col, text=f"{heading_text} {'↓' if reverse else '↑'}")
            else:
                # Reset other column headings
                heading_text = self.tree.heading(col, 'text')
                if '↑' in heading_text or '↓' in heading_text:
                    heading_text = heading_text.rstrip('↑↓')
                self.tree.heading(col, text=heading_text)


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

    def create_hand_details_frame(self, parent, hand_data):
        """Create a frame with detailed information about a hand."""
        # Create a frame with a dark background
        details_frame = tk.Frame(parent, bg='black', padx=10, pady=10)
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a canvas with scrollbar for the content
        canvas = tk.Canvas(details_frame, bg='black', highlightthickness=0)
        scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='black')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Hand ID and Date
        header_frame = tk.Frame(scrollable_frame, bg='black')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        hand_id_label = tk.Label(
            header_frame, 
            text=f"Hand ID: {hand_data['hand_id']}", 
            font=("Arial", 12, "bold"),
            fg='white',
            bg='black'
        )
        hand_id_label.pack(side=tk.LEFT)
        
        date_label = tk.Label(
            header_frame, 
            text=f"Date: {hand_data['date_time']}", 
            font=("Arial", 12),
            fg='white',
            bg='black'
        )
        date_label.pack(side=tk.RIGHT)
        
        # Basic info section
        basic_info_frame = tk.Frame(scrollable_frame, bg='#1c1c1c', padx=10, pady=10)
        basic_info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Row 1: Stake, Position, Cards
        row1 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row1.pack(fill=tk.X, pady=5)
        
        stake_label = tk.Label(
            row1, 
            text=f"Stake: {hand_data['stake']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=20,
            anchor='w'
        )
        stake_label.pack(side=tk.LEFT)
        
        position_label = tk.Label(
            row1, 
            text=f"Position: {hand_data['hero_position']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=20,
            anchor='w'
        )
        position_label.pack(side=tk.LEFT)
        
        cards_label = tk.Label(
            row1, 
            text=f"Cards: {hand_data['hero_cards']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=20,
            anchor='w'
        )
        cards_label.pack(side=tk.LEFT)
        
        # Row 2: Board
        row2 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row2.pack(fill=tk.X, pady=5)
        
        board_text = ""
        if hand_data['board_flop']:
            board_text += f"Flop: {hand_data['board_flop']}"
        if hand_data['board_turn']:
            board_text += f" | Turn: {hand_data['board_turn']}"
        if hand_data['board_river']:
            board_text += f" | River: {hand_data['board_river']}"
        
        board_label = tk.Label(
            row2, 
            text=f"Board: {board_text}" if board_text else "Board: -", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            anchor='w'
        )
        board_label.pack(fill=tk.X)
        
        # Row 3: Pot, Rake, Jackpot, Profit
        row3 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row3.pack(fill=tk.X, pady=5)
        
        pot_label = tk.Label(
            row3, 
            text=f"Total Pot: ${hand_data['total_pot']:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        pot_label.pack(side=tk.LEFT)
        
        rake_label = tk.Label(
            row3, 
            text=f"Rake: ${hand_data['rake']:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        rake_label.pack(side=tk.LEFT)
        
        jackpot_label = tk.Label(
            row3, 
            text=f"Jackpot: ${hand_data['jackpot']:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        jackpot_label.pack(side=tk.LEFT)
        
        profit_color = '#00ace6' if hand_data['hero_profit'] > 0 else 'red' if hand_data['hero_profit'] < 0 else 'white'
        profit_label = tk.Label(
            row3, 
            text=f"Profit: ${hand_data['hero_profit']:.2f}", 
            font=("Arial", 11),
            fg=profit_color,
            bg='#1c1c1c',
            width=15,
            anchor='w'
        )
        profit_label.pack(side=tk.LEFT)
        
        # Row 4: Hero Contribution and Profit with Rake
        row4 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row4.pack(fill=tk.X, pady=5)
        
        # Calculate hero's contribution
        hero_contribution = parse_hero_contribution(hand_data['preflop_all'] + hand_data['flop_all'] + 
                                                   hand_data['turn_all'] + hand_data['river_all'], 
                                                   hand_data['hero_position'], hand_data['stake'])
        
        contribution_label = tk.Label(
            row4, 
            text=f"Hero Contribution: ${hero_contribution:.2f}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        contribution_label.pack(side=tk.LEFT)
        
        profit_with_rake_color = '#00ace6' if hand_data['hero_profit_with_rake'] > 0 else 'red' if hand_data['hero_profit_with_rake'] < 0 else 'white'
        profit_with_rake_label = tk.Label(
            row4, 
            text=f"Profit with Rake: ${hand_data['hero_profit_with_rake']:.2f}", 
            font=("Arial", 11),
            fg=profit_with_rake_color,
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        profit_with_rake_label.pack(side=tk.LEFT)
        
        # Row 5: Preflop Scenario and Opportunities
        row5 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row5.pack(fill=tk.X, pady=5)
        
        scenario_label = tk.Label(
            row5, 
            text=f"Preflop Scenario: {hand_data['preflop_scenario']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        scenario_label.pack(side=tk.LEFT)
        
        opportunities_text = []
        if hand_data['had_rfi_opportunity'] == 1:
            opportunities_text.append("RFI")
        if hand_data['had_3bet_op'] == 1:
            opportunities_text.append("3-Bet")
        if hand_data['had_4bet_op'] == 1:
            opportunities_text.append("4-Bet")
        
        opportunities_label = tk.Label(
            row5, 
            text=f"Opportunities: {', '.join(opportunities_text) if opportunities_text else 'None'}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            width=30,
            anchor='w'
        )
        opportunities_label.pack(side=tk.LEFT)
        
        # Row 6: Import Date and Seats Info
        row6 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row6.pack(fill=tk.X, pady=5)
        
        imported_label = tk.Label(
            row6, 
            text=f"Imported On: {hand_data['imported_on']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            anchor='w'
        )
        imported_label.pack(fill=tk.X)
        
        # Row 7: Seats Info
        row7 = tk.Frame(basic_info_frame, bg='#1c1c1c')
        row7.pack(fill=tk.X, pady=5)
        
        seats_label = tk.Label(
            row7, 
            text=f"Seats Info: {hand_data['seats_info']}", 
            font=("Arial", 11),
            fg='white',
            bg='#1c1c1c',
            anchor='w',
            wraplength=750  # Allow wrapping for long text
        )
        seats_label.pack(fill=tk.X)
        
        # Action sections - Hand History
        self.create_action_section(scrollable_frame, "Preflop", hand_data['preflop_all'])
        
        if hand_data['flop_all']:
            self.create_action_section(scrollable_frame, "Flop", hand_data['flop_all'])
        
        if hand_data['turn_all']:
            self.create_action_section(scrollable_frame, "Turn", hand_data['turn_all'])
        
        if hand_data['river_all']:
            self.create_action_section(scrollable_frame, "River", hand_data['river_all'])
        
        return details_frame
        
    def create_action_section(self, parent, title, text):
        """Create a section for displaying action text."""
        if not text:
            return
            
        frame = tk.Frame(parent, bg='#1c1c1c', padx=10, pady=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = tk.Label(
            frame, 
            text=title, 
            font=("Arial", 12, "bold"),
            fg='white',
            bg='#1c1c1c'
        )
        title_label.pack(anchor='w', pady=(0, 5))
        
        text_widget = tk.Text(
            frame, 
            wrap=tk.WORD, 
            bg='#1c1c1c', 
            fg='white',
            height=min(10, len(text.split('\n'))),
            font=("Courier New", 10)
        )
        text_widget.insert(tk.END, text)
        text_widget.config(state=tk.DISABLED)  # Make read-only
        text_widget.pack(fill=tk.X)

    def recalculate_all_contributions(self):
        """Recalculate hero contributions for all hands in the database."""
        if messagebox.askyesno("Confirm", "This will recalculate contributions for all hands. Continue?"):
            # Show a progress dialog
            progress_window = tk.Toplevel(self)
            progress_window.title("Recalculating Contributions")
            progress_window.geometry("300x100")
            progress_window.transient(self)
            progress_window.grab_set()
            
            # Center the window
            progress_window.update_idletasks()
            width = progress_window.winfo_width()
            height = progress_window.winfo_height()
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            progress_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
            
            # Add a label
            label = tk.Label(progress_window, text="Recalculating contributions and adjusted profits...\nThis may take a moment.")
            label.pack(pady=20)
            
            # Update the UI
            progress_window.update()
            
            # Call the recalculation function
            updated_count = recalculate_all_contributions()
            
            # Update the UI again
            progress_window.destroy()
            
            # Also update the adjusted profit based on current rakeback
            self.update_adjusted_profit()
            
            # Show a completion message
            messagebox.showinfo("Recalculation Complete", f"Updated {updated_count} hands.")
            
            # Refresh the display
            self.refresh_import_tab()
            self.refresh_graph_tab()
            self.update_leak_display()

    ####################
    ###  LEAKHELPER  ###
    ####################


    def create_leak_tab(self):
        """Create the LeakHelper tab with profit/loss grid display."""
        POSITION_SECTION_HEIGHT = 100
        GRID_SIZE = 845 
        
        # Configure grid weights for the main frame
        self.leak_frame.grid_rowconfigure(0, weight=14)  # Top section gets 80%
        self.leak_frame.grid_rowconfigure(1, weight=1)  # Bottom section gets 20%    
        # Adjust column weights to make hand_selection column smaller
        self.leak_frame.grid_columnconfigure(0, weight=2)  # Left section made slightly smaller
        self.leak_frame.grid_columnconfigure(1, weight=10)  # Middle section increased
        self.leak_frame.grid_columnconfigure(2, weight=1)  # Right section unchanged
        self.leak_frame.configure(bg=DARK_BG)
        
        # Create the three main sections (like Range tab)
        # Top left - Hand Data
        hand_selection = tk.Frame(self.leak_frame, bg=DARK_BG, bd=1, relief='solid')
        hand_selection.grid(row=0, column=0, rowspan=2, sticky="nsew")
        
        # Configure hand_selection grid with more elegant spacing
        hand_selection.grid_rowconfigure(0, weight=1)  # Selected hand display
        hand_selection.grid_rowconfigure(1, weight=1)  # Best hands
        hand_selection.grid_rowconfigure(2, weight=6)  # Worst hands
        hand_selection.grid_columnconfigure(0, weight=1)
        
        # Create selected hand display frame at the top with more elegant styling
        selected_hand_frame = tk.Frame(hand_selection, bg=DARK_BG)
        selected_hand_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=(40, 0))
        
        # Create a canvas for the selected hand display with a more elegant border
        self.selected_hand_canvas = tk.Canvas(
            selected_hand_frame,
            width=120,
            height=120,
            bg=DARK_BG,
            highlightthickness=0,
            highlightbackground=LIGHT_BG
        )
        self.selected_hand_canvas.pack(pady=10)
        
        
        # Create best hands frame with more elegant styling
        best_hands_frame = tk.Frame(hand_selection, bg=DARK_BG)
        best_hands_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 0))
        
        # Create worst hands frame with more elegant styling
        worst_hands_frame = tk.Frame(hand_selection, bg=DARK_BG)
        worst_hands_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 20))
        
        
        # Configure the style for the treeviews with more elegant styling
        self.style.configure("Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR, 
                        fieldbackground=DARK_MEDIUM_BG,
                        rowheight=25,
                        font=("Arial", 10))  # Increased font size
        self.style.configure("Treeview.Heading", 
                        background=DARK_BG, 
                        foreground=TEXT_COLOR,
                        font=("Arial", 10, "bold"))
        self.style.map('Treeview', background=[('selected', ACCENT_COLOR)])

        
        

        
        # Create best hands treeview
        best_tree_frame = tk.Frame(best_hands_frame, bg=DARK_BG)
        best_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview without scrollbar since we only show 5 items
        self.best_hands_tree = ttk.Treeview(best_tree_frame, 
                                           columns=("position", "stake", "profit"), 
                                           show="headings",
                                           height=5,
                                           style="Treeview")  # Exactly 5 rows
        self.best_hands_tree.pack(fill=tk.X, expand=False)  # Only expand horizontally
        
        # Configure best hands columns
        self.best_hands_tree.heading("position", text="Position")
        self.best_hands_tree.heading("stake", text="Stake")
        self.best_hands_tree.heading("profit", text="Profit")
        
        self.best_hands_tree.column("position", width=70, anchor=tk.CENTER)
        self.best_hands_tree.column("stake", width=70, anchor=tk.CENTER)
        self.best_hands_tree.column("profit", width=80, anchor=tk.CENTER)
        
        # Configure the header style for best hands
        self.style.map("BestHands.Treeview.Heading",
                  background=[('active', PROFIT_COLOR)],
                  foreground=[('active', TEXT_COLOR)])
        self.style.configure("BestHands.Treeview.Heading", 
                        background=PROFIT_COLOR, 
                        foreground=TEXT_COLOR,
                        font=("Arial", 10, "bold"))
        
        # Apply custom tag for best hands rows
        self.style.configure("BestHands.Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR,
                        fieldbackground=DARK_MEDIUM_BG,
                        font=("Arial", 10))
        self.best_hands_tree.configure(style="BestHands.Treeview")
        
        # Bind double-click event for best hands
        self.best_hands_tree.bind("<Double-1>", self.on_best_hand_double_click)
        
        # Create worst hands treeview
        worst_tree_frame = tk.Frame(worst_hands_frame, bg=DARK_BG)
        worst_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview without scrollbar since we only show 5 items
        self.worst_hands_tree = ttk.Treeview(worst_tree_frame, 
                                            columns=("position", "stake", "profit"), 
                                            show="headings",
                                            height=5)  # Exactly 5 rows
        self.worst_hands_tree.pack(fill=tk.X, expand=False)  # Only expand horizontally
        
        # Configure worst hands columns
        self.worst_hands_tree.heading("position", text="Position")
        self.worst_hands_tree.heading("stake", text="Stake")
        self.worst_hands_tree.heading("profit", text="Profit")
        
        self.worst_hands_tree.column("position", width=70, anchor=tk.CENTER)
        self.worst_hands_tree.column("stake", width=70, anchor=tk.CENTER)
        self.worst_hands_tree.column("profit", width=80, anchor=tk.CENTER)  # Center the profit column
        
        # Configure the header style for worst hands
        self.style.map("WorstHands.Treeview.Heading",
                  background=[('active', LOSS_COLOR)],
                  foreground=[('active', TEXT_COLOR)])
        self.style.configure("WorstHands.Treeview.Heading", 
                        background=LOSS_COLOR, 
                        foreground=TEXT_COLOR,
                        font=("Arial", 10, "bold"))
        
        # Apply custom tag for worst hands rows
        self.style.configure("WorstHands.Treeview", 
                        background=DARK_MEDIUM_BG, 
                        foreground=TEXT_COLOR,
                        fieldbackground=DARK_MEDIUM_BG,
                        font=("Arial", 10))
        self.worst_hands_tree.configure(style="WorstHands.Treeview")
        
        # Bind double-click event for worst hands
        self.worst_hands_tree.bind("<Double-1>", self.on_worst_hand_double_click)
        
        # Center - Profit/Loss grid
        leak_section = tk.Frame(self.leak_frame, bg=DARK_BG, bd=1, relief='solid')
        leak_section.grid(row=0, column=1, rowspan=2, sticky="nsew", pady= (0, 50))
        leak_section.grid_propagate(False)
        
        # Top right - Scenario buttons
        scenario_section = tk.Frame(self.leak_frame, bg=DARK_BG, bd=1, relief='solid')
        scenario_section.grid(row=0, column=2, rowspan=2, sticky="nsew")
        
        # Bottom - Position buttons
        position_section = tk.Frame(self.leak_frame, bg=DARK_BG, bd=1, relief='solid')
        position_section.grid(row=1, column=1, columnspan=1, sticky="nsew")
        position_section.grid_propagate(False)
        
        # Configure the leak grid section
        leak_section.grid_rowconfigure(0, weight=1)
        leak_section.grid_columnconfigure(0, weight=1)
        
        # Create legend frame to the right of the grid
        legend_frame = tk.Frame(leak_section, bg=DARK_BG)
        legend_frame.pack(side=tk.RIGHT, padx=10, pady=10)
        
        # Add legend items
        legend_items = [
            ("Profit", PROFIT_COLOR),  # Light blue for profit
            ("Loss", LOSS_COLOR)     # Red for loss
        ]
        
        for text, color in legend_items:
            item_frame = tk.Frame(legend_frame, bg=DARK_BG)
            item_frame.pack(anchor='w', pady=5)
            
            color_box = tk.Canvas(item_frame, width=20, height=20, bg=color, highlightthickness=0)
            color_box.pack(side=tk.LEFT, padx=5)
            
            label = tk.Label(item_frame, text=text, bg=DARK_BG, fg=TEXT_COLOR, font=("Arial", 10))
            label.pack(side=tk.LEFT)
        
        # Create grid frame with fixed size and centered in the column
        # (ignoring the legend frame for centering purposes)
        self.leak_grid_frame = tk.Frame(leak_section, bg=DARK_BG, width=GRID_SIZE, height=GRID_SIZE)
        self.leak_grid_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)  # Center in the column
        self.leak_grid_frame.grid_propagate(False)
        
        # Configure grid weights for centering
        for i in range(13):
            self.leak_grid_frame.grid_rowconfigure(i, weight=1)
            self.leak_grid_frame.grid_columnconfigure(i, weight=1)
        
        # Create 13x13 grid of canvas widgets
        SQUARE_SIZE = GRID_SIZE // 13  # Calculate square size based on grid size
        self.leak_squares = []
        for i in range(13):
            row = []
            for j in range(13):
                canvas = tk.Canvas(
                    self.leak_grid_frame,
                    width=SQUARE_SIZE,
                    height=SQUARE_SIZE,
                    bg=DARK_BG,
                    highlightthickness=1,
                    highlightbackground=TEXT_COLOR
                )
                canvas.grid(row=i, column=j, sticky="nsew")
                # Add click binding to each canvas
                canvas.bind('<Button-1>', lambda e, i=i, j=j: self.on_leak_square_click(i, j))
                row.append(canvas)
            self.leak_squares.append(row)
        
        # Configure scenario section (right side)
        scenario_section.grid_rowconfigure(0, weight=1)
        scenario_section.grid_columnconfigure(0, weight=1)

        # Configure hand selection section (left side)
        hand_selection.grid_rowconfigure(0, weight=1)
        hand_selection.grid_columnconfigure(0, weight=1)
        
        # Preflop scenario buttons container
        scenario_container = tk.Frame(scenario_section, bg=DARK_BG)
        scenario_container.grid(row=0, column=0)
        
        # Add preflop scenario buttons
        scenarios = ['All', 'Open', 'Facing Open', '3bet', 'Facing 3bet', '4bet', 'Facing 4bet', '5bet+']
        self.leak_scenario_buttons = {}
        self.leak_selected_scenario = None  # Default to None (All scenarios)
        
        for i, scenario in enumerate(scenarios):
            button_frame = tk.Frame(scenario_container, bg=DARK_BG)
            button_frame.pack(pady=5)
            
            btn = tk.Button(
                button_frame,
                text=scenario,
                bg=ACCENT_COLOR if scenario == 'All' else DARK_MEDIUM_BG,  # All is selected by default
                fg=TEXT_COLOR,
                font=("Arial", 11),
                width=20,
                height=2,
                command=lambda s=scenario: self.filter_leak_by_scenario(s)
            )
            btn.pack()
            self.leak_scenario_buttons[scenario] = btn
        
        # Configure position section
        position_section.grid_rowconfigure(0, weight=1)
        position_section.grid_columnconfigure(0, weight=1)
        
        # Position buttons container
        position_container = tk.Frame(position_section, bg=DARK_BG)
        position_container.grid(row=0, column=0)
        
        # Add 'All' to positions
        positions = ['All', 'BB', 'SB', 'BTN', 'CO', 'HJ', 'UTG']
        self.leak_position_buttons = {}
        self.leak_selected_position = None  # Default to None (All positions)
        
        for i, pos in enumerate(positions):
            btn = tk.Button(
                position_container,
                text=pos,
                bg=ACCENT_COLOR if pos == 'All' else DARK_MEDIUM_BG,  # All is selected by default
                fg=TEXT_COLOR,
                font=("Arial", 10),
                width=15,
                height=2,
                command=lambda p=pos: self.filter_leak_by_position(p)
            )
            btn.grid(row=0, column=i, padx=5)
            self.leak_position_buttons[pos] = btn
        
        # Stats label
        self.leak_stats_label = tk.Label(
            leak_section, 
            text="", 
            font=("Arial", 10),
            bg=DARK_BG,
            fg=TEXT_COLOR
        )
        
        # Initialize default selected hand (AA)
        self.hand_filter = "AA"
        
        # Initial display - show all positions
        self.update_leak_display()
        
        # Initialize the selected hand display with AA (index 0,0 for AA)
        self.update_selected_hand_display(0, 0)

    def filter_leak_by_position(self, position):
        """Filter leak data by selected position"""
        if position == 'All':
            # When All is selected, show data from all positions
            self.leak_selected_position = None
        else:
            if self.leak_selected_position == position:
                self.leak_selected_position = None  # Deselect if already selected
            else:
                self.leak_selected_position = position
        
        # Update button appearances
        for pos, btn in self.leak_position_buttons.items():
            if (pos == 'All' and self.leak_selected_position is None) or pos == self.leak_selected_position:
                btn.config(bg=ACCENT_COLOR)
            else:
                btn.config(bg=DARK_MEDIUM_BG)
        
        # Update the leak display
        self.update_leak_display()
        
    def filter_leak_by_scenario(self, scenario):
        """Filter leak data by selected preflop scenario"""
        if scenario == 'All':
            # When All is selected, show data from all scenarios
            self.leak_selected_scenario = None
        else:
            if self.leak_selected_scenario == scenario:
                self.leak_selected_scenario = None  # Deselect if already selected
            else:
                self.leak_selected_scenario = scenario
        
        # Update button appearances
        for s, btn in self.leak_scenario_buttons.items():
            if (s == 'All' and self.leak_selected_scenario is None) or s == self.leak_selected_scenario:
                btn.config(bg=ACCENT_COLOR)
            else:
                btn.config(bg=DARK_MEDIUM_BG)
        
        # Update the leak display
        self.update_leak_display()

    def update_leak_display(self):
        """Update the leak grid display with profit/loss data."""
        # Get profit stats
        stats = calculate_profit_stats(self.leak_selected_position, self.leak_selected_scenario)
        
        # Initialize counters
        total_hands = 0
        total_profit = 0
        profitable_hands = 0
        
        # Update each square in the grid
        for i, r1 in enumerate(RANKS):
            for j, r2 in enumerate(RANKS):
                canvas = self.leak_squares[i][j]
                canvas.delete("all")  # Clear existing content
                
                width = canvas.winfo_reqwidth()
                height = canvas.winfo_reqheight()
                
                # Determine the hand type
                if i == j:  # Pair
                    hand = r1 + r1
                elif i < j:  # Suited
                    hand = r1 + r2 + "s"
                else:  # Offsuit
                    hand = r2 + r1 + "o"
                
                # Get stats: (count, total_profit, avg_profit)
                count, profit, avg_profit = stats.get(hand, (0, 0, 0))
                
                if count > 0:
                    # Determine color based on profit and selection
                    if hand == self.hand_filter:  # If this is the selected hand
                        if profit >= 0:
                            color = DARK_PROFIT_COLOR  # Darker blue for selected profit
                        else:
                            color = DARK_LOSS_COLOR  # Darker red for selected loss
                    else:  # Not selected
                        if profit >= 0:
                            color = PROFIT_COLOR  # Light blue for profit
                        else:
                            color = LOSS_COLOR  # Red for loss
                    
                    # Draw background
                    canvas.create_rectangle(0, 0, width, height, fill=color, outline="")
                    
                    # Format profit for display
                    profit_display = f"${profit:.2f}"
                    
                    # Add text overlay - hand name and profit only (no hand count)
                    canvas.create_text(width/2, height/2, 
                                     text=f"{hand}\n{profit_display}", 
                                     fill=TEXT_COLOR, 
                                     font=("Arial", 9, "bold"),
                                     justify='center')
                    
                    # Update counters
                    total_hands += count
                    total_profit += profit
                    if profit > 0:
                        profitable_hands += 1
                else:
                    # Draw empty square
                    canvas.create_rectangle(0, 0, width, height, fill=DARK_BG, outline="")
                    canvas.create_text(width/2, height/2, text=hand, fill='#666666', font=("Arial", 9))
        
        # Update stats label
        if total_hands > 0:
            profitable_pct = (profitable_hands / len(stats)) * 100 if len(stats) > 0 else 0
            self.leak_stats_label.config(
                text=f"Total hands: {total_hands}, Total profit: ${total_profit:.2f}, Profitable hands: {profitable_pct:.1f}%"
            )
        else:
            self.leak_stats_label.config(text="No data available")
        
        # Find the indices for the current hand_filter
        for i, r1 in enumerate(RANKS):
            for j, r2 in enumerate(RANKS):
                if i == j and r1 + r1 == self.hand_filter:  # Pair
                    self.update_selected_hand_display(i, j)
                    break
                elif i < j and r1 + r2 + "s" == self.hand_filter:  # Suited
                    self.update_selected_hand_display(i, j)
                    break
                elif i > j and r2 + r1 + "o" == self.hand_filter:  # Offsuit
                    self.update_selected_hand_display(i, j)
                    break
            
        # Update best and worst hands treeviews
        self.update_best_worst_hands()

    def update_best_worst_hands(self):
        """Update the best and worst hands treeviews based on current filters."""
        # Clear existing items
        for item in self.best_hands_tree.get_children():
            self.best_hands_tree.delete(item)
        
        for item in self.worst_hands_tree.get_children():
            self.worst_hands_tree.delete(item)
        
        # Get best and worst hands
        best_hands, worst_hands = get_best_worst_hands(
            position=self.leak_selected_position,
            scenario=self.leak_selected_scenario,
            hand=self.hand_filter,
            limit=5
        )
        
        # Populate best hands treeview
        for i, (hand_id, position, stake, cards, profit) in enumerate(best_hands):
            # Format profit as currency
            profit_display = f"${profit:.2f}"
            
            # Store hand_id as a hidden tag for retrieval on double-click
            self.best_hands_tree.insert("", "end", values=(position, stake, profit_display), tags=(hand_id,))
        
        # Populate worst hands treeview
        for i, (hand_id, position, stake, cards, profit) in enumerate(worst_hands):
            # Format profit as currency
            profit_display = f"${profit:.2f}"
            
            # Store hand_id as a hidden tag for retrieval on double-click
            self.worst_hands_tree.insert("", "end", values=(position, stake, profit_display), tags=(hand_id,))
    
    def on_leak_square_click(self, i, j):
        """Handle click on a leak grid square."""
        # Determine the hand type
        if i == j:  # Pair
            hand = RANKS[i] + RANKS[i]
        elif i < j:  # Suited
            hand = RANKS[i] + RANKS[j] + "s"
        else:  # Offsuit
            hand = RANKS[j] + RANKS[i] + "o"
        
        # Update hand_filter
        self.hand_filter = hand
        
        # Update the selected hand display
        self.update_selected_hand_display(i, j)
        
        # Update the display to show the selected square
        self.update_leak_display()
        
    def update_selected_hand_display(self, i, j):
        """Update the selected hand display canvas with the currently selected hand."""
        # Clear the canvas
        self.selected_hand_canvas.delete("all")
        
        width = self.selected_hand_canvas.winfo_width()
        height = self.selected_hand_canvas.winfo_height()
        
        # If width or height is 1, the canvas hasn't been properly sized yet
        # Use the configured size instead
        if width <= 1:
            width = 120
        if height <= 1:
            height = 120
        
        # Determine the hand type
        if i == j:  # Pair
            hand = RANKS[i] + RANKS[i]
        elif i < j:  # Suited
            hand = RANKS[i] + RANKS[j] + "s"
        else:  # Offsuit
            hand = RANKS[j] + RANKS[i] + "o"
        
        # Get stats for this hand
        stats = calculate_profit_stats(self.leak_selected_position, self.leak_selected_scenario)
        count, profit, avg_profit = stats.get(hand, (0, 0, 0))
        
        # Determine color based on profit
        if count > 0:
            if profit >= 0:
                color = DARK_PROFIT_COLOR  # Darker blue for selected profit
                border_color = PROFIT_COLOR  # Light blue border
            else:
                color = DARK_LOSS_COLOR  # Darker red for selected loss
                border_color = LOSS_COLOR  # Light red border
        else:
            color = DARK_BG  # Dark background for no data
            border_color = LIGHT_BG  # Gray border
        
        # Draw background with rounded corners
        self.selected_hand_canvas.create_rectangle(
            2, 2, width-2, height-2, 
            fill=border_color, 
            outline=color,
            width=2
        )
        
        # Format profit for display
        profit_display = f"${profit:.2f}" if count > 0 else "No data"
        
        # Draw hand name in larger font
        self.selected_hand_canvas.create_text(
            width/2, 
            height/2 - 10, 
            text=hand, 
            fill=TEXT_COLOR, 
            font=("Arial", 18, "bold"),
            justify='center'
        )
        
        # Draw profit in smaller font below
        self.selected_hand_canvas.create_text(
            width/2, 
            height/2 + 20, 
            text=profit_display, 
            fill=TEXT_COLOR, 
            font=("Arial", 14),
            justify='center'
        )
    
    def _show_hand_details(self, hand_id):
        """Helper method to show hand details in a new window."""
        # Fetch full hand details
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Get column names
        c.execute("PRAGMA table_info(hands)")
        column_names = [info[1] for info in c.fetchall()]
        
        # Fetch the hand data
        c.execute("SELECT * FROM hands WHERE hand_id = ?", (hand_id,))
        hand_data_tuple = c.fetchone()
        conn.close()
        
        if not hand_data_tuple:
            return
        
        # Convert to dictionary
        hand_data = dict(zip(column_names, hand_data_tuple))
        
        # Create a new window to display hand details
        hand_window = tk.Toplevel(self)
        hand_window.title(f"Hand Details: {hand_id}")
        hand_window.geometry("800x600")
        hand_window.configure(bg=self.colors['bg_dark'])
        
        # Create a frame for the hand details
        details_frame = self.create_hand_details_frame(hand_window, hand_data)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def on_best_hand_double_click(self, event):
        """Handle double-click on a best hand in the treeview."""
        selected = self.best_hands_tree.selection()
        if not selected:
            return
            
        # Get the hand_id from the tag
        hand_id = self.best_hands_tree.item(selected[0], "tags")[0]
        self._show_hand_details(hand_id)

    def on_worst_hand_double_click(self, event):
        """Handle double-click on a worst hand in the treeview."""
        selected = self.worst_hands_tree.selection()
        if not selected:
            return
            
        # Get the hand_id from the tag
        hand_id = self.worst_hands_tree.item(selected[0], "tags")[0]
        self._show_hand_details(hand_id)

    def update_adjusted_profit(self):
        """Update the adjusted_profit column for all hands based on current rakeback percentage."""
        try:
            # Get the rakeback percentage
            rakeback_pct = float(self.rakeback_var.get()) / 100.0
            
            # Ensure rakeback percentage is between 0 and 1
            rakeback_pct = max(0.0, min(1.0, rakeback_pct))
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Update adjusted_profit for all hands
            # For 100% rakeback, use hero_profit_with_rake for winning hands
            if rakeback_pct == 1.0:
                c.execute("""
                    UPDATE hands
                    SET adjusted_profit = hero_profit_with_rake
                    WHERE hero_profit > 0
                """)
            else:
                # Formula: adjusted_profit = hero_profit + (rake * rakeback_percentage) for winning hands only
                c.execute("""
                    UPDATE hands
                    SET adjusted_profit = hero_profit + (rake * ?)
                    WHERE hero_profit > 0
                """, (rakeback_pct,))
            
            # For hands where hero didn't win, adjusted_profit = hero_profit
            c.execute("""
                UPDATE hands
                SET adjusted_profit = hero_profit
                WHERE hero_profit <= 0
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error updating adjusted profit: {e}")

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

def get_best_worst_hands(position=None, scenario=None, hand=None, limit=5):
    """Get the best and worst performing hands based on filters."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Base query - include hand_id for double-click functionality
    query = """
        SELECT hand_id, hero_position, stake, hero_cards, hero_profit
        FROM hands
        WHERE hero_cards IS NOT NULL AND hero_cards != ''
    """
    params = []
    
    # Add filters
    if position:
        query += " AND hero_position = ?"
        params.append(position)
    
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
    
    if hand:
        # Add hand filter based on the selected hand in the grid
        if len(hand) == 2:  # Pair
            rank = hand[0]
            query += " AND hero_cards LIKE ? AND substr(hero_cards, 1, 1) = ? AND substr(hero_cards, 4, 1) = ?"
            params.extend([f"%{rank}%", rank, rank])
        elif len(hand) == 3:  # Suited or offsuit
            rank1, rank2 = hand[0], hand[1]
            suited = hand.endswith('s')
            if suited:
                query += " AND hero_cards LIKE ? AND hero_cards LIKE ? AND substr(hero_cards, 2, 1) = substr(hero_cards, 5, 1)"
                params.extend([f"%{rank1}%", f"%{rank2}%"])
            else:
                query += " AND hero_cards LIKE ? AND hero_cards LIKE ? AND substr(hero_cards, 2, 1) != substr(hero_cards, 5, 1)"
                params.extend([f"%{rank1}%", f"%{rank2}%"])
    
    # Get best hands (only positive profit)
    best_query = query + " AND hero_profit > 0 ORDER BY hero_profit DESC LIMIT ?"
    c.execute(best_query, params + [limit])
    best_hands = c.fetchall()
    
    # Get worst hands (only negative profit)
    worst_query = query + " AND hero_profit < 0 ORDER BY hero_profit ASC LIMIT ?"
    c.execute(worst_query, params + [limit])
    worst_hands = c.fetchall()
    
    conn.close()
    return best_hands, worst_hands

if __name__ == "__main__":
    init_database()
    app = PokerTrackerApp()
    app.mainloop()
        
