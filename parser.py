import os
import re
import json
import zipfile
import tempfile
import datetime
import sqlite3
from constants import DB_FILE


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

def parse_hero_starting_stack(text):
    """Parse hero's starting stack from the hand history text."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Seat") and "Hero" in line:
            # Match the pattern: "Seat X: Hero ($XX.XX in chips)"
            match = re.search(r"Hero\s+\(\$(\d+\.?\d*)\s+in\s+chips\)", line)
            if match:
                return float(match.group(1))
    return 0.0

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
        "hero_contribution": 0.0,
        "paid_rake": 0.0,
        "hero_starting_stack": 0.0  # Add new field
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
    hero_collect_pattern = r"Hero(?:: | )(?:collected \$|Receives Cashout \(?)\$?(\d+(?:\.\d+)?)\)?"
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
                # Set paid rake as proportional share
                data["paid_rake"] = round((rake_amount + jackpot_amount) / num_winners, 2)
            else:
                # Normal case for single winner - add back full rake and jackpot
                data["hero_profit_with_rake"] = round(data["hero_profit"] + rake_amount + jackpot_amount, 2)
                # Set paid rake as full amount
                data["paid_rake"] = round(rake_amount + jackpot_amount, 2)
        else:
            # Only apply special logic for multiple showdowns
            # Count how many showdowns Hero won
            hero_won_showdowns = len(hero_collect_matches)
            
            if hero_won_showdowns > 0:
                # Calculate the proportion of showdowns Hero won
                proportion = hero_won_showdowns / total_showdowns
                # Add back proportional rake and jackpot
                data["hero_profit_with_rake"] = round(data["hero_profit"] + proportion * (rake_amount + jackpot_amount), 2)
                # Set paid rake as proportional amount
                data["paid_rake"] = round(proportion * (rake_amount + jackpot_amount), 2)
            else:
                # If Hero didn't win any showdowns, profit with rake is the same as regular profit
                data["hero_profit_with_rake"] = data["hero_profit"]
                data["paid_rake"] = 0.0
    else:
        # If hero didn't win, they lost their contribution
        data["hero_profit"] = round(-contribution, 2)
        # For losses, the profit with rake is the same as regular profit
        data["hero_profit_with_rake"] = data["hero_profit"]
        # No rake paid when losing
        data["paid_rake"] = 0.0

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

    # Parse hero's starting stack
    data["hero_starting_stack"] = parse_hero_starting_stack(block)

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
                if 'receives cashout' in line:
                    contribution += 0
                else:
                    contribution += amount
    
    return contribution

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
        
        # Parse hero's starting stack
        starting_stack = parse_hero_starting_stack(all_text)
        
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
                adjusted_profit = ?,
                hero_starting_stack = ?
            WHERE hand_id = ?
        """, (contribution, adjusted_profit, starting_stack, hand_id))
        
        updated_count += 1
    
    conn.commit()
    conn.close()
    
    return updated_count

def insert_hand_details(hand_info_list):
    """Insert each hand dict into the DB, ensuring all columns of data."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now_str = datetime.datetime.now().isoformat()
    
    # Check if hero_starting_stack column exists, add it if it doesn't
    c.execute("PRAGMA table_info(hands)")
    columns = [col[1] for col in c.fetchall()]
    if "hero_starting_stack" not in columns:
        try:
            c.execute("ALTER TABLE hands ADD COLUMN hero_starting_stack REAL DEFAULT 0.0")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column might have been added by another process
    
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
        "adjusted_profit", "paid_rake", "hero_starting_stack"
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

    