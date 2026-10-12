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
VERSION = "1.0.7"
GITHUB_REPO = "zerocool5878/exam-clone-tool"

# Import auto-updater
try:
    from auto_updater import AutoUpdater, create_update_ui
    AUTO_UPDATE_AVAILABLE = True
except ImportError:
    AUTO_UPDATE_AVAILABLE = False
    print("Auto-updater not available. Update checking disabled.")


# ---------------------------------------------------------------------------
# Source normalisation and question parsing
# ---------------------------------------------------------------------------

# A saved Chrome "view-source:" page keeps each original line in one of these cells,
# with the original tags entity-escaped and wrapped in highlighting <span>s.
VIEW_SOURCE_CELL = re.compile(r'<td class="line-content">(.*?)</td></tr>', re.S)
HTML_TAG = re.compile(r'<[^>]+>')
# A main question exactly as the LMS renders it:
#   7. <span id="question-plaintext136761">(id:126107)...
# Anchoring on the span is what stops prose such as "...multiplier is 3.86. The radius..."
# from being mistaken for question 86.
MAIN_QUESTION = re.compile(r'(\d+)\.\s*<span[^>]*\bid="question-plaintext\d+"[^>]*>\s*\(id:(\d+)\)')
ANY_ID = re.compile(r'\(id:(\d+)\)')


def normalize_source(content):
    """Return the page's real HTML.

    Accepts either the raw page source (what the browser-capture path copies out of
    the view-source tab) or a saved Chrome view-source page.
    """
    if not content:
        return ""
    if 'class="line-content"' in content:
        cells = VIEW_SOURCE_CELL.findall(content)
        if cells:
            return "\n".join(html.unescape(HTML_TAG.sub('', cell)) for cell in cells)
    return content


def parse_questions(content):
    """Parse an exam edit page into its numbered questions.

    Returns (questions, error). Each question is a dict:
        {'num': 7, 'main': '126107', 'alts': ['126108', '132165', ...]}
    where 'alts' are the alternate question IDs offered in that question's
    replacement template (everything from this question up to the next one).
    """
    source = normalize_source(content)
    matches = list(MAIN_QUESTION.finditer(source))
    if not matches:
        return None, 'No numbered questions found (expected: N. <span id="question-plaintext...">(id:...))'

    questions = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        main_id = m.group(2)
        ids = list(dict.fromkeys(ANY_ID.findall(source[m.start():end])))
        questions.append({
            'num': int(m.group(1)),
            'main': main_id,
            'alts': [x for x in ids if x != main_id],
        })

    questions.sort(key=lambda q: q['num'])
    nums = [q['num'] for q in questions]
    if len(set(nums)) != len(nums):
        dupes = sorted({n for n in nums if nums.count(n) > 1})
        return None, f"Duplicate question numbers found: {dupes}"
    logging.debug(f"Parsed {len(questions)} questions: " +
                  ", ".join(f"Q{q['num']}={q['main']}(+{len(q['alts'])} alts)" for q in questions))
    return questions, None


# ---------------------------------------------------------------------------
# Matching: make the test's set of main question IDs identical to the target's
# ---------------------------------------------------------------------------

COST_KEEP = 0           # test question keeps its current main ID
COST_CHANGE = 1         # test question switches to one of its alternates
COST_DUMMY = 10         # padding when the two exams have different question counts
COST_IMPOSSIBLE = 1000  # the target ID is not reachable from this question at all


def _hungarian(cost):
    """Minimum-cost assignment on a square matrix. Returns a list: row -> column."""
    n = len(cost)
    INF = float('inf')
    u = [0] * (n + 1)
    v = [0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [0] * n
    for j in range(1, n + 1):
        assignment[p[j] - 1] = j - 1
    return assignment


def plan_changes(target_questions, test_questions):
    """Decide which test questions to switch to an alternate.

    Goal: the test's set of main question IDs becomes identical to the target's
    (question order is irrelevant), with the fewest possible changes.

    Every test question is free to move. A question that already matches a target
    ID is only moved when that is the sole way to reach a missing target ID, and
    then the ID it gives up is picked back up by another question that carries it
    as an alternate (a chain). A target ID is "unreachable" only if no test
    question can be switched to it under those rules.

    Returns (plan, unreachable, extra):
        plan        list of (test_question_num, current_id, new_id), sorted by question
        unreachable target IDs that no assignment can bring into the test
        extra       test question numbers left without a target ID (counts differ)
    """
    target_ids = [q['main'] for q in target_questions]
    n = max(len(target_ids), len(test_questions))

    cost = []
    for r in range(n):
        row = []
        for c in range(n):
            if r >= len(test_questions) or c >= len(target_ids):
                row.append(COST_DUMMY)
                continue
            q, tid = test_questions[r], target_ids[c]
            if tid == q['main']:
                row.append(COST_KEEP)
            elif tid in q['alts']:
                row.append(COST_CHANGE)
            else:
                row.append(COST_IMPOSSIBLE)
        cost.append(row)

    assignment = _hungarian(cost)

    plan, unreachable, extra = [], [], []
    for r, c in enumerate(assignment):
        if r >= len(test_questions):
            if c < len(target_ids):
                unreachable.append(target_ids[c])
            continue
        q = test_questions[r]
        if c >= len(target_ids):
            extra.append(q['num'])
            continue
        tid = target_ids[c]
        if cost[r][c] >= COST_IMPOSSIBLE:
            unreachable.append(tid)
            extra.append(q['num'])
        elif tid != q['main']:
            plan.append((q['num'], q['main'], tid))

    plan.sort()
    logging.debug(f"Plan: {plan} | unreachable: {unreachable} | extra: {extra}")
    return plan, sorted(unreachable), sorted(extra)


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
        if not target_content['content'] or not exam_content['content']:
            messagebox.showerror("Error", "Please load both target and exam content (via file or browser capture)")
            return

        status_text.delete(1.0, tk.END)
        results_text.delete(1.0, tk.END)

        status_text.insert(tk.END, "🔍 Reading target...\n")
        root.update()
        target_qs, err = parse_questions(target_content['content'])
        if err:
            status_text.insert(tk.END, f"❌ Target error: {err}\n")
            return
        status_text.insert(tk.END, f"✅ Target questions: {len(target_qs)}\n")

        status_text.insert(tk.END, "🔍 Reading test...\n")
        root.update()
        test_qs, err = parse_questions(exam_content['content'])
        if err:
            status_text.insert(tk.END, f"❌ Test error: {err}\n")
            return
        status_text.insert(tk.END, f"✅ Test questions: {len(test_qs)}\n")

        if len(target_qs) != len(test_qs):
            status_text.insert(tk.END,
                f"⚠️  Question counts differ ({len(target_qs)} vs {len(test_qs)}); the tests cannot be made identical.\n")

        status_text.insert(tk.END, "🎯 Matching test questions to target question IDs...\n")
        root.update()
        plan, unreachable, extra = plan_changes(target_qs, test_qs)

        target_ids = {q['main'] for q in target_qs}
        new_by_num = {num: new for num, _, new in plan}
        picked_up_by = {new: num for num, _, new in plan}   # new ID -> question that will carry it

        results_text.insert(tk.END, "📄 EXAM CLONE REPORT\n")
        results_text.insert(tk.END, "=" * 70 + "\n")
        results_text.insert(tk.END, f"Target: {target_content['source']}\n")
        results_text.insert(tk.END, f"Test:   {exam_content['source']}\n")
        results_text.insert(tk.END, "Goal:   test has the same question IDs as target (order does not matter)\n")
        results_text.insert(tk.END, "=" * 70 + "\n\n")

        already_correct = 0
        for q in test_qs:
            num, cur = q['num'], q['main']
            if num in new_by_num:
                new = new_by_num[num]
                line = f"Question #{num}: Change (ID:{cur}) -> alternate (ID:{new})"
                if cur in target_ids and cur in picked_up_by:
                    line += f"   [ID:{cur} is picked up by question #{picked_up_by[cur]}]"
                results_text.insert(tk.END, line + "\n")
            elif num in extra:
                results_text.insert(tk.END, f"Question #{num}: ❌ ID:{cur} is not in the target and no alternate reaches a missing target ID\n")
            else:
                already_correct += 1
                results_text.insert(tk.END, f"Question #{num}: ✅ Already correct (ID:{cur})\n")

        results_text.insert(tk.END, "\n" + "=" * 30 + " SUMMARY " + "=" * 30 + "\n")
        results_text.insert(tk.END, f"✅ Already correct: {already_correct}\n")
        results_text.insert(tk.END, f"🔄 Changes needed: {len(plan)}\n")
        if unreachable:
            results_text.insert(tk.END, f"❌ Target IDs no test question can reach: {', '.join(unreachable)}\n")
        if extra:
            results_text.insert(tk.END, f"❌ Test questions left without a target ID: {', '.join('#' + str(n) for n in extra)}\n")
        results_text.insert(tk.END, f"📊 Total test questions: {len(test_qs)}\n")

        identical = not unreachable and not extra and len(target_qs) == len(test_qs)
        if identical:
            results_text.insert(tk.END, "🎉 After these changes the test will be identical to the target.\n")
            status_text.insert(tk.END, f"🎯 Report complete! {len(plan)} change(s) make the tests identical.\n")
        else:
            results_text.insert(tk.END, "⚠️  The tests cannot be made identical with the alternates available.\n")
            status_text.insert(tk.END, "⚠️  Report complete, but the tests cannot be made identical. See results.\n")
        results_text.insert(tk.END, "--- END REPORT ---\n")
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