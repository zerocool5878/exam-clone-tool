import re
import html
import logging
logging.basicConfig(filename='debug_log.txt', level=logging.DEBUG, format='%(asctime)s %(message)s')
import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import subprocess
import json
import time
import threading
import sys
try:
    import win32gui
    import win32con
    import win32clipboard
    import pyautogui
    CAPTURE_AVAILABLE = True
except ImportError:
    CAPTURE_AVAILABLE = False

# Application version and update configuration
VERSION = "1.0.4"
GITHUB_REPO = "zerocool5878/exam-clone-tool"

# Import auto-updater
try:
    from auto_updater import AutoUpdater, create_update_ui
    AUTO_UPDATE_AVAILABLE = True
except ImportError:
    AUTO_UPDATE_AVAILABLE = False
    print("Auto-updater not available. Update checking disabled.")

def resolve_conflicts(mapping_dict, target_content, exam_content):
    """
    Resolve conflicts where multiple exam IDs map to the same target ID.
    Returns updated mapping with conflicts resolved.
    """
    try:
        target_decoded = html.unescape(target_content)
        exam_decoded = html.unescape(exam_content)

        # Find target main IDs with duplicate detection
        target_numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
        target_numbered = target_numbered_pattern.findall(target_decoded)

        # Check for duplicate target main IDs
        target_id_counts = {}
        for q_num, main_id in target_numbered:
            if main_id in target_id_counts:
                target_id_counts[main_id].append(f"Q{q_num}")
            else:
                target_id_counts[main_id] = [f"Q{q_num}"]

        duplicate_target_ids = {id: questions for id, questions in target_id_counts.items() if len(questions) > 1}
        if duplicate_target_ids:
            logging.debug("WARNING: Duplicate target main IDs detected!")
            for main_id, questions in duplicate_target_ids.items():
                logging.debug(f"  Target ID {main_id} appears in: {', '.join(questions)}")

        target_main_ids = set(main_id for _, main_id in target_numbered)

        # Find exam main IDs with duplicate detection
        exam_numbered = target_numbered_pattern.findall(exam_decoded)

        # Check for duplicate exam main IDs
        exam_id_counts = {}
        for q_num, main_id in exam_numbered:
            if main_id in exam_id_counts:
                exam_id_counts[main_id].append(f"Q{q_num}")
            else:
                exam_id_counts[main_id] = [f"Q{q_num}"]

        duplicate_exam_ids = {id: questions for id, questions in exam_id_counts.items() if len(questions) > 1}
        if duplicate_exam_ids:
            logging.debug("WARNING: Duplicate exam main IDs detected!")
            for main_id, questions in duplicate_exam_ids.items():
                logging.debug(f"  Exam ID {main_id} appears in: {', '.join(questions)}")

        exam_main_ids = set(main_id for _, main_id in exam_numbered)

        # Identify conflicts
        target_usage = {}
        conflicts = {}

        for exam_id, target_id in mapping_dict.items():
            if target_id in target_usage:
                # Conflict found
                if target_id not in conflicts:
                    conflicts[target_id] = []
                conflicts[target_id].append(exam_id)
                conflicts[target_id].append(target_usage[target_id])
            else:
                target_usage[target_id] = exam_id

        logging.debug(f"Found {len(conflicts)} conflicted target IDs")

        # If there are duplicate main IDs, add extra validation
        if duplicate_target_ids or duplicate_exam_ids:
            logging.debug("Using enhanced validation due to duplicate main IDs")

        # Resolve conflicts by finding alternative mappings
        resolved_mapping = mapping_dict.copy()

        for target_id, conflicted_exam_ids in conflicts.items():
            logging.debug(f"Resolving conflict for target ID {target_id} with exam IDs {conflicted_exam_ids}")

            # Keep first exam ID, reassign others
            for i, exam_id in enumerate(conflicted_exam_ids[1:], 1):
                logging.debug(f"Finding alternative for exam ID {exam_id}")

                # Find exam question section to get alternatives
                exam_sections = extract_exam_sections(exam_decoded)
                alternatives = get_alternatives_for_exam_id(exam_id, exam_sections)

                # Find alternative that doesn't conflict
                new_target = None
                forbidden_targets = set(resolved_mapping.values())

                for alt_id in alternatives:
                    # Enhanced validation for duplicate main IDs
                    is_valid_target = alt_id in target_main_ids
                    is_not_exam_main = alt_id not in exam_main_ids
                    is_not_forbidden = alt_id not in forbidden_targets

                    # Additional check: if target has duplicates, warn but allow
                    if alt_id in duplicate_target_ids:
                        logging.debug(f"Warning - alternative {alt_id} is a duplicate target ID")

                    # Additional check: if alternative is duplicate exam main, reject
                    if alt_id in duplicate_exam_ids:
                        logging.debug(f"Rejecting alternative {alt_id} - is duplicate exam main ID")
                        is_not_exam_main = False

                    if is_valid_target and is_not_exam_main and is_not_forbidden:
                        new_target = alt_id
                        break

                if new_target:
                    resolved_mapping[exam_id] = new_target
                    logging.debug(f"Reassigned exam ID {exam_id} from {target_id} to {new_target}")
                else:
                    logging.debug(f"Could not find alternative for exam ID {exam_id}")

        return resolved_mapping

    except Exception as e:
        logging.debug(f"Error in conflict resolution: {e}")
        return None
    
def extract_exam_sections(exam_content):
    """Extract question sections from exam content"""
    sections = {}
    numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    matches = numbered_pattern.findall(exam_content)
    logging.debug(f"Found {len(matches)} numbered questions in exam content.")
    for i, (q_num, main_id) in enumerate(matches):
        question_num = int(q_num)
        if i < len(matches) - 1:
            next_q_num = int(matches[i+1][0])
            section_pattern = rf'{question_num}\.\s+.*?(?={next_q_num}\.\s+)'
        else:
            section_pattern = rf'{question_num}\.\s+.*'
        section_match = re.search(section_pattern, exam_content, re.DOTALL)
        if section_match:
            sections[main_id] = section_match.group(0)
            logging.debug(f"Section for main_id {main_id} (Q{question_num}) length: {len(section_match.group(0))}")
        else:
            logging.debug(f"No section found for main_id {main_id} (Q{question_num})")
    logging.debug(f"Extracted {len(sections)} sections from exam content.")
    return sections

def get_alternatives_for_exam_id(exam_id, exam_sections):
    """Get alternatives for a specific exam ID"""
    if exam_id in exam_sections:
        section_content = exam_sections[exam_id]
        all_ids = re.findall(r'\(id:(\d+)\)', section_content)
        alternatives = [alt_id for alt_id in all_ids if alt_id != exam_id]
        logging.debug(f"Alternatives for exam_id {exam_id}: {alternatives}")
        return alternatives
    logging.debug(f"No section found for exam_id {exam_id} in exam_sections.")
    return []

def get_browser_windows():
    """Get list of browser windows"""
    if not CAPTURE_AVAILABLE:
        return []
    
    browser_windows = []
    
    def enum_windows_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            
            # Check if it's a browser window
            browser_indicators = [
                'Chrome', 'Firefox', 'Edge', 'Safari', 'Opera', 
                'Brave', 'Internet Explorer', 'Mozilla'
            ]
            
            if any(indicator in window_text or indicator in class_name for indicator in browser_indicators):
                if window_text.strip():  # Only if window has a title
                    windows.append({
                        'hwnd': hwnd,
                        'title': window_text,
                        'class': class_name
                    })
        return True
    
    try:
        win32gui.EnumWindows(enum_windows_callback, browser_windows)
    except:
        pass  # If win32gui fails, return empty list
    
    return browser_windows

def capture_html_from_browser(hwnd):
    """Capture HTML source from browser window"""
    if not CAPTURE_AVAILABLE:
        return None, "Browser capture not available (missing dependencies)"
    
    try:
        # Bring window to foreground
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.8)  # Longer wait for window to come to front
        
        # Send Ctrl+U to view source (works in most browsers)
        pyautogui.hotkey('ctrl', 'u')
        time.sleep(3)  # Longer wait for view source window to open
        
        # Send Ctrl+A to select all
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.8)
        
        # Send Ctrl+C to copy
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.8)
        
        # Get clipboard content
        win32clipboard.OpenClipboard()
        try:
            html_content = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        except:
            html_content = win32clipboard.GetClipboardData(win32con.CF_TEXT)
        finally:
            win32clipboard.CloseClipboard()
        
        # Ensure we're focused on the view source window before closing
        time.sleep(0.5)
        
        # ONLY close the view source tab - NOT the entire browser
        # Use Ctrl+W which closes current tab in all browsers
        pyautogui.hotkey('ctrl', 'w')
        
        # Small delay to ensure tab closes
        time.sleep(0.3)
        
        return html_content, None
        
    except Exception as e:
        return None, f"Error capturing HTML: {str(e)}"

def extract_numbered_questions_from_content(content):
    """Extract numbered questions from HTML content (not file)"""
    if not content:
        return None, "No content provided"
    
    decoded_content = html.unescape(content)
    
    # Extract numbered questions
    numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    numbered_matches = numbered_pattern.findall(decoded_content)
    
    if not numbered_matches:
        return None, "No numbered questions found"
    
    # Sort by question number
    sorted_questions = sorted(numbered_matches, key=lambda x: int(x[0]))
    question_ids = [qid for _, qid in sorted_questions]
    
    return question_ids, None

def detect_file_type_from_content(content):
    """Detect file type from HTML content (not file)"""
    if not content:
        return None, "No content provided"
    
    decoded_content = html.unescape(content)
    
    # Check for numbered questions pattern
    numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    numbered_matches = numbered_pattern.findall(decoded_content)
    
    if len(numbered_matches) < 5:
        # Not enough numbered questions to analyze
        id_pattern = re.compile(r'\(id:(\d+)\)')
        all_ids = id_pattern.findall(decoded_content)
        return None, f"Not enough numbered questions found ({len(numbered_matches)}). Need at least 5."
    
    # Count alternatives per question
    alternative_counts = []
    for i, (q_num, main_id) in enumerate(numbered_matches):
        question_num = int(q_num)
        
        # Extract this question's section
        if i < len(numbered_matches) - 1:
            next_q_num = int(numbered_matches[i+1][0])
            section_pattern = rf'{question_num}\.\s+.*?(?={next_q_num}\.\s+)'
        else:
            section_pattern = rf'{question_num}\.\s+.*'
        
        section_match = re.search(section_pattern, decoded_content, re.DOTALL)
        
        if section_match:
            section_content = section_match.group(0)
            section_ids = re.findall(r'\(id:(\d+)\)', section_content)
            unique_ids = list(dict.fromkeys(section_ids))
            alternative_counts.append(len(unique_ids))
    
    if not alternative_counts:
        return None, "Could not analyze question structure"
    
    avg_alternatives = sum(alternative_counts) / len(alternative_counts)
    
    if avg_alternatives >= 3:
        return "normal_target", f"Normal target file with {len(numbered_matches)} questions (avg {avg_alternatives:.1f} IDs/question - has alternatives)"
    else:
        return "comp_test", f"Comp test file with {len(numbered_matches)} questions (avg {avg_alternatives:.1f} IDs/question - single IDs)"

def extract_numbered_questions(filepath):
    """Extract numbered questions from exam file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, f"Error reading file: {e}"
    
    decoded_content = html.unescape(content)
    
    # Extract numbered questions
    numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    numbered_matches = numbered_pattern.findall(decoded_content)
    
    if not numbered_matches:
        return None, "No numbered questions found"
    
    # Sort by question number
    sorted_questions = sorted(numbered_matches, key=lambda x: int(x[0]))
    question_ids = [qid for _, qid in sorted_questions]
    
    return question_ids, None

def detect_file_type(filepath):
    """Detect file type based on alternatives structure:
    - normal_target: Has numbered questions with multiple IDs (alternatives)
    - comp_test: Has numbered questions with single IDs (no alternatives)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, f"Error reading file: {e}"
    
    decoded_content = html.unescape(content)
    
    # Check for numbered questions pattern
    numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    numbered_matches = numbered_pattern.findall(decoded_content)
    
    if len(numbered_matches) < 5:
        # Not enough numbered questions to analyze
        id_pattern = re.compile(r'\(id:(\d+)\)')
        all_ids = id_pattern.findall(decoded_content)
        unique_ids = list(dict.fromkeys(all_ids))
        
        if len(unique_ids) >= 10:
            return "comp_test", f"Comp test file with {len(unique_ids)} unique IDs (no numbered structure)"
        else:
            return "unknown", "Unable to determine file type"
    
    # Analyze first 5 questions to check for alternatives
    numbered_sorted = sorted(numbered_matches, key=lambda x: int(x[0]))
    total_ids_in_sections = 0
    
    for i, (q_num, main_id) in enumerate(numbered_sorted[:5]):
        question_num = int(q_num)
        
        # Extract this question's section
        if i < len(numbered_sorted) - 1:
            next_q_num = int(numbered_sorted[i+1][0])
            section_pattern = rf'{question_num}\.\s+.*?(?={next_q_num}\.\s+)'
        else:
            section_pattern = rf'{question_num}\.\s+.*'
        
        section_match = re.search(section_pattern, decoded_content, re.DOTALL)
        
        if section_match:
            section_content = section_match.group(0)
            section_ids = re.findall(r'\(id:(\d+)\)', section_content)
            unique_ids = list(dict.fromkeys(section_ids))
            total_ids_in_sections += len(unique_ids)
    
    # Calculate average IDs per question
    avg_ids_per_question = total_ids_in_sections / min(5, len(numbered_matches))
    
    if avg_ids_per_question > 2.0:
        return "normal_target", f"Normal target file with {len(numbered_matches)} questions (avg {avg_ids_per_question:.1f} IDs/question - has alternatives)"
    else:
        return "comp_test", f"Comp test file with {len(numbered_matches)} questions (avg {avg_ids_per_question:.1f} IDs/question - no alternatives)"

def extract_comp_test_mapping_from_content(target_content, exam_content):
    """
    Content-based version of comp test mapping for browser capture
    Goal: Make exam's main IDs exactly match target's main IDs by selecting correct alternatives
    """
    try:
        target_decoded = html.unescape(target_content)
        exam_decoded = html.unescape(exam_content)

        # Extract target numbered questions (main questions in target)
        target_numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
        target_numbered = target_numbered_pattern.findall(target_decoded)
        target_sorted = sorted(target_numbered, key=lambda x: int(x[0]))

        logging.debug(f"Target has {len(target_sorted)} main questions")

        # ONLY target main IDs matter - these are what exam must match
        target_main_ids = set(main_id for _, main_id in target_sorted)
        logging.debug(f"Target main IDs (must match these): {sorted(target_main_ids)}")

        # Extract exam numbered questions
        exam_numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
        exam_numbered = exam_numbered_pattern.findall(exam_decoded)
        exam_sorted = sorted(exam_numbered, key=lambda x: int(x[0]))

        logging.debug(f"Exam has {len(exam_sorted)} questions")
        
        # Track which exam questions already have correct IDs
        exam_main_ids = set(main_id for _, main_id in exam_sorted)
        logging.debug(f"Exam current main IDs: {sorted(exam_main_ids)}")

        # STEP 1: Build all possible alternatives for each exam question
        question_alternatives = {}  # question_num -> {'current_id': X, 'alternatives': [list of ALL IDs]}

        for i, (exam_q_num, exam_main_id) in enumerate(exam_sorted):
            question_num = int(exam_q_num)

            # Extract this question's section to get all alternatives
            if i < len(exam_sorted) - 1:
                next_exam_q_num = int(exam_sorted[i+1][0])
                section_pattern = rf'{question_num}\.\s+.*?(?={next_exam_q_num}\.\s+)'
            else:
                section_pattern = rf'{question_num}\.\s+.*'

            exam_section_match = re.search(section_pattern, exam_decoded, re.DOTALL)

            if exam_section_match:
                exam_section_content = exam_section_match.group(0)
                exam_section_ids = re.findall(r'\(id:(\d+)\)', exam_section_content)
                exam_unique_ids = list(dict.fromkeys(exam_section_ids))

                question_alternatives[question_num] = {
                    'current_id': exam_main_id,
                    'all_ids': exam_unique_ids  # Including current main ID
                }
                logging.debug(f"Q{question_num} current={exam_main_id}, all_ids={exam_unique_ids}")

        # STEP 2: Identify which questions need changes and what their options are
        questions_needing_change = {}  # question_num -> list of valid target IDs it can switch to

        for question_num, info in question_alternatives.items():
            current_id = info['current_id']
            
            # If current ID is already in target, no change needed
            if current_id in target_main_ids:
                logging.debug(f"Q{question_num}: ID {current_id} already matches target - no change needed")
                continue
            
            # Find which alternatives are valid target main IDs
            valid_alternatives = [alt_id for alt_id in info['all_ids'] 
                                 if alt_id != current_id and alt_id in target_main_ids]
            
            if valid_alternatives:
                questions_needing_change[question_num] = {
                    'current_id': current_id,
                    'options': valid_alternatives
                }
                logging.debug(f"Q{question_num}: needs change, options={valid_alternatives}")
            else:
                logging.debug(f"Q{question_num}: needs change but has NO valid alternatives!")

        # STEP 3: Perfect matching - assign alternatives to ensure all target IDs are covered
        exam_to_target_mapping = {}
        used_target_ids = set()
        
        # Add IDs that are already correct (no change needed)
        for question_num, info in question_alternatives.items():
            if question_num not in questions_needing_change:
                current_id = info['current_id']
                if current_id in target_main_ids:
                    used_target_ids.add(current_id)
                    logging.debug(f"Q{question_num}: keeping {current_id} (already correct)")

        logging.debug(f"Starting conflict resolution. {len(questions_needing_change)} questions need changes")
        logging.debug(f"Already matched target IDs: {sorted(used_target_ids)}")

        # Iterative greedy assignment with constraint propagation
        max_iterations = 20
        iteration = 0
        
        while questions_needing_change and iteration < max_iterations:
            iteration += 1
            logging.debug(f"=== ITERATION {iteration} ===")
            
            # Filter out already-used target IDs from each question's options
            for q_num in list(questions_needing_change.keys()):
                original_options = questions_needing_change[q_num]['options']
                available_options = [opt for opt in original_options if opt not in used_target_ids]
                
                if not available_options:
                    logging.debug(f"Q{q_num}: ran out of options - cannot resolve!")
                    del questions_needing_change[q_num]
                else:
                    questions_needing_change[q_num]['available_options'] = available_options
            
            if not questions_needing_change:
                break
            
            # Sort by flexibility: questions with fewer options go first
            sorted_questions = sorted(questions_needing_change.items(),
                                     key=lambda x: len(x[1]['available_options']))
            
            # Assign the most constrained question
            q_num, info = sorted_questions[0]
            available = info['available_options']
            
            if available:
                chosen_target = available[0]  # Pick first available
                current_id = info['current_id']
                
                # Make assignment
                exam_to_target_mapping[current_id] = chosen_target
                used_target_ids.add(chosen_target)
                
                logging.debug(f"Q{q_num}: {current_id} -> {chosen_target} (had {len(available)} options)")
                
                # Remove this question
                del questions_needing_change[q_num]
        
        if questions_needing_change:
            remaining = list(questions_needing_change.keys())
            logging.debug(f"ERROR: Could not resolve {len(remaining)} questions: {remaining}")
            return None, f"Could not find valid alternatives for questions: {remaining}"

        # STEP 4: Validate the solution
        logging.debug(f"=== VALIDATION ===")
        logging.debug(f"Mappings to apply: {len(exam_to_target_mapping)}")
        
        # Check for duplicates
        assigned_targets = list(exam_to_target_mapping.values())
        if len(assigned_targets) != len(set(assigned_targets)):
            logging.debug("ERROR: Duplicate target assignments detected!")
            return None, "Duplicate assignments - algorithm error"
        
        # Calculate final coverage
        final_matched_ids = used_target_ids.copy()
        logging.debug(f"Final matched target IDs: {len(final_matched_ids)}/{len(target_main_ids)}")
        logging.debug(f"Matched: {sorted(final_matched_ids)}")
        
        missing = target_main_ids - final_matched_ids
        if missing:
            logging.debug(f"WARNING: {len(missing)} target IDs not matched: {sorted(missing)}")
        
        return exam_to_target_mapping, None

    except Exception as e:
        return None, f"Error in comp test mapping: {e}"
    
def extract_comp_test_mapping(comp_test_filepath, exam_filepath):
    """
    Extract mapping for comp_test scenario using POSITIONAL matching
    - comp_test_filepath: target file (contains the correct answers)
    - exam_filepath: exam file (current selections to compare against target)
    
    CORRECT Logic: Position-based matching
    - Exam Q8 should get alternatives from Target Q8 (same position)
    - NOT based on ID matching across different question numbers
    """
    import logging
    logging.basicConfig(filename='debug_log.txt', level=logging.DEBUG, format='%(asctime)s %(message)s')
    try:
        # Read target file 
        with open(comp_test_filepath, 'r', encoding='utf-8') as f:
            target_content = f.read()
        
        # Read exam file  
        with open(exam_filepath, 'r', encoding='utf-8') as f:
            exam_content = f.read()
            
    except Exception as e:
        return None, f"Error reading files: {e}"
    
    target_decoded = html.unescape(target_content)
    exam_decoded = html.unescape(exam_content)
    
    # Extract target numbered questions (main questions in target)
    target_numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    target_numbered = target_numbered_pattern.findall(target_decoded)
    target_sorted = sorted(target_numbered, key=lambda x: int(x[0]))
    
    print(f"DEBUG: Target has {len(target_sorted)} main questions")
    
    # Create set of target main IDs for quick lookup
    target_main_ids = set(qid for _, qid in target_sorted)
    
    # Build target question sections with all their alternatives
    target_alternatives_map = {}  # alternative_id -> main_id
    
    for i, (target_q_num, target_main_id) in enumerate(target_sorted):
        question_num = int(target_q_num)
        
        # Extract this target question's section (including alternatives)
        if i < len(target_sorted) - 1:
            next_q_num = int(target_sorted[i+1][0])
            section_pattern = rf'{question_num}\.\s+.*?(?={next_q_num}\.\s+)'
        else:
            section_pattern = rf'{question_num}\.\s+.*'
        
        section_match = re.search(section_pattern, target_decoded, re.DOTALL)
        
        if section_match:
            section_content = section_match.group(0)
            section_ids = re.findall(r'\(id:(\d+)\)', section_content)
            section_unique = list(dict.fromkeys(section_ids))
            
            # Map all IDs in this target section to the main ID
            for alt_id in section_unique:
                target_alternatives_map[alt_id] = target_main_id
            
            print(f"DEBUG: Target Q{question_num} (main:{target_main_id}) has {len(section_unique)} IDs")
    
    # Extract exam numbered questions with their alternatives
    exam_numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    exam_numbered = exam_numbered_pattern.findall(exam_decoded)
    exam_sorted = sorted(exam_numbered, key=lambda x: int(x[0]))
    
    print(f"DEBUG: Exam has {len(exam_sorted)} questions")
    
    # CORRECT APPROACH: Alternative-based matching
    # For each exam question, find its alternatives and see which target main ID they match
    exam_to_target_mapping = {}
    
    # Create set of all target main IDs for quick lookup
    target_main_ids = set(main_id for _, main_id in target_sorted)
    
    # Create set of all exam main IDs to avoid conflicts
    exam_main_ids = set(main_id for _, main_id in exam_sorted)
    print(f"DEBUG: Exam main IDs: {sorted(exam_main_ids)}")
    print(f"DEBUG: Target main IDs: {sorted(target_main_ids)}")
    
    for i, (exam_q_num, exam_main_id) in enumerate(exam_sorted):
        question_num = int(exam_q_num)
        
        print(f"DEBUG: Processing exam Q{question_num} (current ID: {exam_main_id})")
        
        # FIRST: Check if current exam ID is already a target main ID
        if exam_main_id in target_main_ids:
            print(f"DEBUG: Q{question_num} current ID {exam_main_id} is already a target main ID - no change needed")
            continue
        
        # Extract exam question section to find all its alternatives
        if i < len(exam_sorted) - 1:
            next_exam_q_num = int(exam_sorted[i+1][0])
            section_pattern = rf'{question_num}\.\s+.*?(?={next_exam_q_num}\.\s+)'
        else:
            section_pattern = rf'{question_num}\.\s+.*'
        
        exam_section_match = re.search(section_pattern, exam_decoded, re.DOTALL)
        
        if exam_section_match:
            exam_section_content = exam_section_match.group(0)
            exam_section_ids = re.findall(r'\(id:(\d+)\)', exam_section_content)
            exam_unique_ids = list(dict.fromkeys(exam_section_ids))
            
            # Get alternatives (excluding current main ID)
            exam_alternatives = [alt_id for alt_id in exam_unique_ids if alt_id != exam_main_id]
            
            print(f"DEBUG: Exam Q{question_num} has alternatives: {exam_alternatives}")
            
            # IMPROVED: Check alternatives against target main IDs, avoiding conflicts
            matching_alternative = None
            for alt_id in exam_alternatives:
                if alt_id in target_main_ids:
                    # Check if this target main ID is NOT already used as a main ID in exam
                    if alt_id not in exam_main_ids:
                        matching_alternative = alt_id
                        # Find which target question this matches
                        for target_q_num, target_main_id in target_sorted:
                            if target_main_id == alt_id:
                                print(f"DEBUG: Exam Q{question_num} alternative {alt_id} matches target Q{target_q_num} (conflict-free)")
                                break
                        break
                    else:
                        print(f"DEBUG: Exam Q{question_num} alternative {alt_id} matches target main ID but conflicts with exam Q - skipping")
            
            if matching_alternative:
                exam_to_target_mapping[exam_main_id] = matching_alternative
                print(f"DEBUG: Q{question_num} should change from {exam_main_id} -> {matching_alternative}")
            else:
                print(f"DEBUG: Q{question_num} - no alternatives match any target main ID")
        else:
            print(f"DEBUG: Q{question_num} - could not extract section")

    print(f"DEBUG: Total alternative-based mappings: {len(exam_to_target_mapping)}")
    return exam_to_target_mapping, None

def extract_target_mapping_from_content(content):
    """Extract alternative-to-main mapping from HTML content"""
    if not content:
        return None, "No content provided"
    
    decoded_content = html.unescape(content)
    
    # Find all numbered questions with their IDs - this gives us the main questions
    numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    numbered_matches = numbered_pattern.findall(decoded_content)
    sorted_questions = sorted(numbered_matches, key=lambda x: int(x[0]))
    
    # Build mapping by finding question sections
    alternative_to_main = {}
    
    for i, (q_num, main_id) in enumerate(sorted_questions):
        question_num = int(q_num)
        
        # Create regex pattern to extract this question's section
        if i < len(sorted_questions) - 1:
            next_q_num = int(sorted_questions[i+1][0])
            section_pattern = rf'{question_num}\.\s+.*?(?={next_q_num}\.\s+)'
        else:
            section_pattern = rf'{question_num}\.\s+.*'
        
        section_match = re.search(section_pattern, decoded_content, re.DOTALL)
        
        if section_match:
            section_content = section_match.group(0)
            
            # Extract all IDs from this section
            all_ids = re.findall(r'\(id:(\d+)\)', section_content)
            unique_ids = list(dict.fromkeys(all_ids))
            
            # Map all IDs in this section to the main ID
            # Only map if ID hasn't been seen before (first occurrence wins)
            # Exception: for Q17/Q22 shared alternatives, prefer Q22
            for alt_id in unique_ids:
                if alt_id not in alternative_to_main:
                    alternative_to_main[alt_id] = main_id
                else:
                    # Handle Q17/Q22 conflict - prefer Q22 (136044) over Q17 (136045)
                    existing_main = alternative_to_main[alt_id]
                    if existing_main == '136045' and main_id == '136044':
                        # Override Q17 with Q22 for shared alternatives
                        alternative_to_main[alt_id] = main_id
    
    return alternative_to_main, None

def extract_target_mapping_fixed(filepath):
    """Extract alternative-to-main mapping using proper question boundary detection"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, f"Error reading file: {e}"
    
    decoded_content = html.unescape(content)
    
    # Find all numbered questions with their IDs - this gives us the main questions
    numbered_pattern = re.compile(r'(\d+)\.\s+[^(]*\(id:(\d+)\)')
    numbered_matches = numbered_pattern.findall(decoded_content)
    sorted_questions = sorted(numbered_matches, key=lambda x: int(x[0]))
    
    print(f"DEBUG: Found {len(sorted_questions)} numbered questions")
    
    # Build mapping by finding question sections using a different approach
    alternative_to_main = {}
    
    # Since the file is one big line, we need to split by question boundaries
    # Look for the pattern: question number followed by question text and ID
    question_sections = []
    
    for i, (q_num, main_id) in enumerate(sorted_questions):
        question_num = int(q_num)
        
        # Create regex pattern to extract this question's section
        # Look for: "N. [question text](id:XXXXX)" until next question "N+1. "
        if i < len(sorted_questions) - 1:
            next_q_num = int(sorted_questions[i+1][0])
            # Pattern: from "N. " to "N+1. " (but not including the next question)
            section_pattern = rf'{question_num}\.\s+.*?(?={next_q_num}\.\s+)'
        else:
            # Last question - goes to end of content
            section_pattern = rf'{question_num}\.\s+.*'
        
        section_match = re.search(section_pattern, decoded_content, re.DOTALL)
        
        if section_match:
            section_content = section_match.group(0)
            
            # Extract all IDs from this section
            all_ids = re.findall(r'\(id:(\d+)\)', section_content)
            # Remove duplicates while preserving order
            unique_ids = list(dict.fromkeys(all_ids))
            
            print(f"DEBUG: Q{question_num} (Main: {main_id}) has {len(unique_ids)} unique IDs")
            print(f"DEBUG: Q{question_num} IDs: {unique_ids[:10]}...")  # Show first 10
            
            # Map all IDs in this section to the main ID
            for alt_id in unique_ids:
                alternative_to_main[alt_id] = main_id
            
            question_sections.append({
                'number': question_num,
                'main_id': main_id,
                'all_ids': unique_ids,
                'section_length': len(section_content)
            })
    
    print(f"DEBUG: Total mappings created: {len(alternative_to_main)}")
    
    return alternative_to_main, None

def create_fixed_mapping_gui():
    root = tk.Tk()
    root.title("📄 Exam Tool v3")
    root.geometry("1200x950")
    
    # Try to set an icon (will use default if file not found)
    try:
        root.iconbitmap('test_icon.ico')
    except:
        pass  # Use default icon if custom icon not available
    
    # Main frame
    main_frame = tk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Title header
    title_label = tk.Label(main_frame, 
        text="📄 Exam Tool v3", 
        font=("Arial", 20, "bold"), fg="navy")
    title_label.pack(pady=(0, 15))
    
    # Variables to store captured content
    target_content = {'content': None, 'source': None}
    exam_content = {'content': None, 'source': None}
    
    # File/Capture selection frame
    file_frame = tk.Frame(main_frame)
    file_frame.pack(fill=tk.X, pady=10)
    
    # Target section (FIRST - correct answers)
    target_section = tk.LabelFrame(file_frame, text="Target (Correct Answers)", font=("Arial", 10, "bold"))
    target_section.pack(fill=tk.X, pady=5)
    
    target_frame = tk.Frame(target_section)
    target_frame.pack(fill=tk.X, padx=5, pady=5)
    
    target_path_var = tk.StringVar()
    target_entry = tk.Entry(target_frame, textvariable=target_path_var, width=50, state='readonly')
    target_entry.pack(side=tk.LEFT, padx=5)
    
    target_status_var = tk.StringVar(value="Not loaded")
    target_status_label = tk.Label(target_frame, textvariable=target_status_var, fg="red")
    target_status_label.pack(side=tk.LEFT, padx=10)
    
    def select_target_file():
        file_path = filedialog.askopenfilename(
            title="Select Target File (correct answers or comp test)",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                target_content['content'] = content
                target_content['source'] = f"File: {os.path.basename(file_path)}"
                target_path_var.set(file_path)
                target_status_var.set("📄 Captured")
                target_status_label.config(fg="green")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")
    
    def capture_target_from_browser():
        if not CAPTURE_AVAILABLE:
            messagebox.showerror("Feature Unavailable", 
                "Browser capture requires additional packages.\n"
                "Please install: pip install pywin32 pyautogui")
            return
            
        browser_windows = get_browser_windows()
        if not browser_windows:
            messagebox.showwarning("No Browsers", "No browser windows found!")
            return
        
        # Create window selection dialog
        selection_window = tk.Toplevel(root)
        selection_window.title("📄 Select Target Browser Window")
        selection_window.geometry("700x600")  # Made taller
        selection_window.transient(root)
        selection_window.grab_set()
        selection_window.configure(bg='white')
        selection_window.resizable(False, False)  # Prevent resizing
        
        # Center the window
        selection_window.geometry("+%d+%d" % (root.winfo_rootx()+100, root.winfo_rooty()+50))
        
        tk.Label(selection_window, text="🎯 Select Target Browser Window:", 
                font=("Arial", 14, "bold"), bg='white', fg='navy').pack(pady=15)
        
        listbox = tk.Listbox(selection_window, height=15, font=("Arial", 10),
                           selectbackground='lightblue', selectforeground='black')
        listbox.pack(fill=tk.X, padx=15, pady=10)  # Fixed height, not expandable
        
        for i, window in enumerate(browser_windows):
            listbox.insert(tk.END, f"{window['title']}")
        
        selected_hwnd = [None]
        
        def on_select():
            if listbox.curselection():
                idx = listbox.curselection()[0]
                selected_hwnd[0] = browser_windows[idx]['hwnd']
                selection_window.destroy()
        
        def on_cancel():
            selection_window.destroy()
        
        # Create a proper button frame with background - stick to bottom
        button_frame = tk.Frame(selection_window, bg='white', height=80)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=30)
        button_frame.pack_propagate(False)  # Maintain fixed height
        
        # Create larger, more visible buttons
        capture_btn = tk.Button(button_frame, text="🌐 CAPTURE SELECTED WINDOW", 
                               command=on_select, 
                               bg="lightgreen", 
                               fg="black",
                               font=("Arial", 14, "bold"), 
                               width=28, 
                               height=2,
                               relief='raised',
                               bd=4)
        capture_btn.pack(side=tk.LEFT, padx=15, pady=10)
        
        cancel_btn = tk.Button(button_frame, text="❌ CANCEL", 
                              command=on_cancel,
                              bg="lightcoral", 
                              fg="black",
                              font=("Arial", 14, "bold"),
                              width=12, 
                              height=2,
                              relief='raised',
                              bd=4)
        cancel_btn.pack(side=tk.RIGHT, padx=15, pady=10)
        
        selection_window.wait_window()
        
        if selected_hwnd[0]:
            # Show progress
            target_status_var.set("Capturing...")
            target_status_label.config(fg="orange")
            root.update()
            
            def capture_thread():
                html_content, error = capture_html_from_browser(selected_hwnd[0])
                if error:
                    root.after(0, lambda: messagebox.showerror("Capture Error", error))
                    root.after(0, lambda: target_status_var.set("Capture failed"))
                    root.after(0, lambda: target_status_label.config(fg="red"))
                else:
                    target_content['content'] = html_content
                    window_title = next(w['title'] for w in browser_windows if w['hwnd'] == selected_hwnd[0])
                    target_content['source'] = f"Browser: {window_title}"
                    root.after(0, lambda: target_path_var.set(f"Captured from: {window_title}"))
                    root.after(0, lambda: target_status_var.set("🌐 Captured"))
                    root.after(0, lambda: target_status_label.config(fg="green"))
            
            threading.Thread(target=capture_thread, daemon=True).start()
    
    tk.Button(target_frame, text="📁 Browse File", command=select_target_file, bg="lightgreen").pack(side=tk.RIGHT, padx=2)
    tk.Button(target_frame, text="🌐 Capture Browser", command=capture_target_from_browser, bg="lightblue").pack(side=tk.RIGHT, padx=2)
    
    # Exam section (SECOND - test to compare)
    exam_section = tk.LabelFrame(file_frame, text="Test Exam (To Compare)", font=("Arial", 10, "bold"))
    exam_section.pack(fill=tk.X, pady=5)
    
    exam_frame = tk.Frame(exam_section)
    exam_frame.pack(fill=tk.X, padx=5, pady=5)
    
    exam_path_var = tk.StringVar()
    exam_entry = tk.Entry(exam_frame, textvariable=exam_path_var, width=50, state='readonly')
    exam_entry.pack(side=tk.LEFT, padx=5)
    
    exam_status_var = tk.StringVar(value="Not loaded")
    exam_status_label = tk.Label(exam_frame, textvariable=exam_status_var, fg="red")
    exam_status_label.pack(side=tk.LEFT, padx=10)
    
    def select_exam_file():
        file_path = filedialog.askopenfilename(
            title="Select Test File (current selections to compare)",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                exam_content['content'] = content
                exam_content['source'] = f"File: {os.path.basename(file_path)}"
                exam_path_var.set(file_path)
                exam_status_var.set("📄 Captured")
                exam_status_label.config(fg="green")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")
    
    def capture_exam_from_browser():
        if not CAPTURE_AVAILABLE:
            messagebox.showerror("Feature Unavailable", 
                "Browser capture requires additional packages.\n"
                "Please install: pip install pywin32 pyautogui")
            return
            
        browser_windows = get_browser_windows()
        if not browser_windows:
            messagebox.showwarning("No Browsers", "No browser windows found!")
            return
        
        # Create window selection dialog
        selection_window = tk.Toplevel(root)
        selection_window.title("📄 Select Exam Browser Window")
        selection_window.geometry("700x600")  # Made taller
        selection_window.transient(root)
        selection_window.grab_set()
        selection_window.configure(bg='white')
        selection_window.resizable(False, False)  # Prevent resizing
        
        # Center the window
        selection_window.geometry("+%d+%d" % (root.winfo_rootx()+100, root.winfo_rooty()+50))
        
        tk.Label(selection_window, text="📝 Select Exam Browser Window:", 
                font=("Arial", 14, "bold"), bg='white', fg='navy').pack(pady=15)
        
        listbox = tk.Listbox(selection_window, height=15, font=("Arial", 10),
                           selectbackground='lightblue', selectforeground='black')
        listbox.pack(fill=tk.X, padx=15, pady=10)  # Fixed height, not expandable
        
        for i, window in enumerate(browser_windows):
            listbox.insert(tk.END, f"{window['title']}")
        
        selected_hwnd = [None]
        
        def on_select():
            if listbox.curselection():
                idx = listbox.curselection()[0]
                selected_hwnd[0] = browser_windows[idx]['hwnd']
                selection_window.destroy()
        
        def on_cancel():
            selection_window.destroy()
        
        # Create a proper button frame with background - stick to bottom
        button_frame = tk.Frame(selection_window, bg='white', height=80)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=30)
        button_frame.pack_propagate(False)  # Maintain fixed height
        
        # Create larger, more visible buttons
        capture_btn = tk.Button(button_frame, text="🌐 CAPTURE SELECTED WINDOW", 
                               command=on_select, 
                               bg="lightgreen", 
                               fg="black",
                               font=("Arial", 14, "bold"), 
                               width=28, 
                               height=2,
                               relief='raised',
                               bd=4)
        capture_btn.pack(side=tk.LEFT, padx=15, pady=10)
        
        cancel_btn = tk.Button(button_frame, text="❌ CANCEL", 
                              command=on_cancel,
                              bg="lightcoral", 
                              fg="black",
                              font=("Arial", 14, "bold"),
                              width=12, 
                              height=2,
                              relief='raised',
                              bd=4)
        cancel_btn.pack(side=tk.RIGHT, padx=15, pady=10)
        
        selection_window.wait_window()
        
        if selected_hwnd[0]:
            # Show progress
            exam_status_var.set("Capturing...")
            exam_status_label.config(fg="orange")
            root.update()
            
            def capture_thread():
                html_content, error = capture_html_from_browser(selected_hwnd[0])
                if error:
                    root.after(0, lambda: messagebox.showerror("Capture Error", error))
                    root.after(0, lambda: exam_status_var.set("Capture failed"))
                    root.after(0, lambda: exam_status_label.config(fg="red"))
                else:
                    exam_content['content'] = html_content
                    window_title = next(w['title'] for w in browser_windows if w['hwnd'] == selected_hwnd[0])
                    exam_content['source'] = f"Browser: {window_title}"
                    root.after(0, lambda: exam_path_var.set(f"Captured from: {window_title}"))
                    root.after(0, lambda: exam_status_var.set("🌐 Captured"))
                    root.after(0, lambda: exam_status_label.config(fg="green"))
            
            threading.Thread(target=capture_thread, daemon=True).start()
    
    tk.Button(exam_frame, text="📁 Browse File", command=select_exam_file, bg="lightgreen").pack(side=tk.RIGHT, padx=2)
    tk.Button(exam_frame, text="🌐 Capture Browser", command=capture_exam_from_browser, bg="lightblue").pack(side=tk.RIGHT, padx=2)
    
    # Compare button
    def generate_mapping():
        # Check if content is available (either from files or browser capture)
        if not target_content['content'] or not exam_content['content']:
            messagebox.showerror("Error", "Please load both target and exam content (via file or browser capture)")
            return
        
        # Clear previous results
        status_text.delete(1.0, tk.END)
        results_text.delete(1.0, tk.END)
        
        status_text.insert(tk.END, "🔍 Analyzing test content...\n")
        root.update()
        
        # Get exam current selections from content
        exam_current, exam_error = extract_numbered_questions_from_content(exam_content['content'])
        if exam_error:
            status_text.insert(tk.END, f"❌ Test content error: {exam_error}\n")
            return
        
        status_text.insert(tk.END, f"✅ Test questions: {len(exam_current)}\n")
        status_text.insert(tk.END, "🔍 Detecting target content type...\n")
        root.update()
        
        # Detect target content type automatically
        file_type, type_info = detect_file_type_from_content(target_content['content'])
        status_text.insert(tk.END, f"📋 {type_info}\n")
        root.update()
        
        # FORCE comp test algorithm when both exam and target are loaded
        # This is the scenario you want - compare exam against target using alternatives
        status_text.insert(tk.END, "🎯 Using comp test mapping algorithm (exam vs target)...\n")
        alt_to_main, target_error = extract_comp_test_mapping_from_content(target_content['content'], exam_content['content'])
        if target_error:
            status_text.insert(tk.END, f"❌ Comp test mapping error: {target_error}\n")
            return
        
        if target_error:
            status_text.insert(tk.END, f"❌ Target content error: {target_error}\n")
            return
        
        status_text.insert(tk.END, f"✅ Target mapping created: {len(alt_to_main)} entries\n")
        
        # Apply conflict resolution
        status_text.insert(tk.END, "🔄 Checking for conflicts...\n")
        root.update()
        
        resolved_mapping = resolve_conflicts(alt_to_main, target_content['content'], exam_content['content'])
        if resolved_mapping:
            alt_to_main = resolved_mapping
            status_text.insert(tk.END, "✅ Conflicts resolved successfully\n")
        else:
            status_text.insert(tk.END, "⚠️ Conflict resolution failed, using original mapping\n")
        
        # Generate results
        results_text.insert(tk.END, "📄 EXAM CLONE REPORT\n")
        results_text.insert(tk.END, "=" * 70 + "\n")
        results_text.insert(tk.END, f"Target: {target_content['source']} ({file_type})\n")
        results_text.insert(tk.END, f"Test: {exam_content['source']} (to compare)\n")
        results_text.insert(tk.END, f"Analysis: {type_info}\n")
        results_text.insert(tk.END, "=" * 70 + "\n\n")
        
        changes_needed = []
        no_change_needed = []
        no_mapping_found = []
        
        # Process each exam position with comp_test logic (forced)
        # Always use comp_test logic when both exam and target are loaded
        if True:  # Force comp_test processing
            # For comp_test: alt_to_main contains exam_main_id → tart_id mappings
            status_text.insert(tk.END, "🔍 Processing comp test mapping...\n")
            root.update()
            
            for i, current_id in enumerate(exam_current, 1):
                if current_id in alt_to_main:
                    # This exam ID has a mapping to a tart ID
                    target_id = alt_to_main[current_id]
                    
                    if current_id == target_id:
                        # Already correct
                        results_text.insert(tk.END, f"Question #{i}: ✅ Already correct (ID:{current_id})\n")
                        no_change_needed.append(i)
                    else:
                        # Need to change to tart ID
                        results_text.insert(tk.END, f"Question #{i}: Change (ID:{current_id}) -> (ID:{target_id})\n")
                        changes_needed.append({
                            'position': i,
                            'from_id': current_id,
                            'to_id': target_id
                        })
                else:
                    # Check if current ID is already a target main ID (no change needed)
                    target_current, _ = extract_numbered_questions_from_content(target_content['content'])
                    if current_id in target_current:
                        target_q_pos = target_current.index(current_id) + 1
                        results_text.insert(tk.END, f"Question #{i}: ✅ Already matches target Q{target_q_pos} (ID:{current_id})\n")
                        no_change_needed.append(i)
                    else:
                        # Truly unknown/no alternatives match
                        results_text.insert(tk.END, f"Question #{i}: ❌ No suitable alternatives (current ID:{current_id})\n")
                        no_mapping_found.append({
                            'position': i,
                            'current_id': current_id
                        })
        else:
            # Normal target processing
            for i, current_id in enumerate(exam_current, 1):
                if current_id in alt_to_main:
                    main_id = alt_to_main[current_id]
                    
                    if current_id == main_id:
                        # Already the correct main question
                        results_text.insert(tk.END, f"Question #{i}: ✅ Already correct (ID:{current_id})\n")
                        no_change_needed.append(i)
                    else:
                        # Need to change from alternative to main
                        results_text.insert(tk.END, f"Question #{i}: Change (ID:{current_id}) -> (ID:{main_id})\n")
                        changes_needed.append({
                            'position': i,
                            'from_id': current_id,
                            'to_id': main_id
                        })
                else:
                    # Check if current ID is already a target main ID
                    target_current, _ = extract_numbered_questions_from_content(target_content['content'])
                    if current_id in target_current:
                        target_q_pos = target_current.index(current_id) + 1
                        results_text.insert(tk.END, f"Question #{i}: ✅ Already matches target Q{target_q_pos} (ID:{current_id})\n")
                        no_change_needed.append(i)
                    else:
                        # No mapping found for this ID
                        results_text.insert(tk.END, f"Question #{i}: ❌ Unknown ID:{current_id} (not in target)\n")
                        no_mapping_found.append({
                            'position': i,
                            'current_id': current_id
                        })
        
        # Summary
        results_text.insert(tk.END, f"\n" + "=" * 30 + " SUMMARY " + "=" * 30 + "\n")
        results_text.insert(tk.END, f"🔄 Changes needed: {len(changes_needed)}\n")
        results_text.insert(tk.END, f"✅ Already correct: {len(no_change_needed)}\n")
        results_text.insert(tk.END, f"❌ Unknown IDs: {len(no_mapping_found)}\n")
        results_text.insert(tk.END, f"📊 Total positions: {len(exam_current)}\n")
        
        # Calculate success rate
        total_processed = len(exam_current)
        mappable = len(changes_needed) + len(no_change_needed)
        success_rate = (mappable / total_processed * 100) if total_processed else 0
        
        results_text.insert(tk.END, f"📈 Mapping success: {success_rate:.1f}%\n")
        results_text.insert(tk.END, f"--- END REPORT ---\n")
        
        # Update status
        status_text.insert(tk.END, f"🎯 Report complete! {mappable}/{total_processed} questions mapped\n")
        
        if len(no_mapping_found) > 0:
            status_text.insert(tk.END, f"⚠️  {len(no_mapping_found)} unknown IDs need investigation\n")
        else:
            status_text.insert(tk.END, "🎉 All IDs successfully mapped!\n")
    
    # Generate button
    generate_btn = tk.Button(main_frame, text="🔄 Generate Clone Report", command=generate_mapping, 
                            font=("Arial", 13, "bold"), bg="darkblue", fg="white", padx=40, pady=10)
    generate_btn.pack(pady=15)
    
    # Status area
    status_frame = tk.Frame(main_frame)
    status_frame.pack(fill=tk.X, pady=5)
    
    tk.Label(status_frame, text="📊 Analysis Status:", font=("Arial", 11, "bold")).pack(anchor='w')
    status_text = scrolledtext.ScrolledText(status_frame, height=8, width=80, font=("Consolas", 9))
    status_text.pack(fill=tk.X)
    
    # Results area
    results_frame = tk.Frame(main_frame)
    results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    tk.Label(results_frame, text="📋 Clone Mapping Results:", font=("Arial", 11, "bold")).pack(anchor='w')
    results_text = scrolledtext.ScrolledText(results_frame, width=80, font=("Consolas", 9))
    results_text.pack(fill=tk.BOTH, expand=True)
    
    # Add initial instructions
    status_text.insert(tk.END, "📄 Exam Clone Tool ready.\n")
    status_text.insert(tk.END, "Step 1: Select TARGET file (normal target OR comp test)\n")
    status_text.insert(tk.END, "Step 2: Select TEST file (to compare against target)\n")
    status_text.insert(tk.END, "Step 3: Generate report (auto-detects file types)\n")
    status_text.insert(tk.END, "Supports: Normal targets & comp test files\n")
    
    root.mainloop()

def check_for_updates_startup():
    """Check for updates at startup"""
    if not AUTO_UPDATE_AVAILABLE:
        return
    
    try:
        print(f"🔍 Checking for updates (Current version: {VERSION})...")
        updater = AutoUpdater(VERSION, GITHUB_REPO)
        
        # Quick check without UI for startup
        latest_version, download_url, changelog = updater.check_for_updates()
        
        if latest_version:
            print(f"🆕 Update available: {VERSION} → {latest_version}")
            
            # Create update UI
            UpdateWindow = create_update_ui()
            window = UpdateWindow(updater)
            
            # Run update UI
            root = tk.Tk()
            root.withdraw()  # Hide main window during update
            
            try:
                window.run()
            except:
                pass  # Continue if update UI fails
            
            root.destroy()
        else:
            print(f"✅ Running latest version: {VERSION}")
            
    except Exception as e:
        print(f"⚠️ Update check failed: {e}")
        # Continue with normal startup even if update check fails

def main():
    """Main application entry point with update check"""
    # Check for updates first
    check_for_updates_startup()
    
    # Start main application
    create_fixed_mapping_gui()

if __name__ == "__main__":
    main()