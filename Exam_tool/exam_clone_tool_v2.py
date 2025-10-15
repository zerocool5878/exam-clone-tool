import re
import html
import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

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

def extract_comp_test_mapping(comp_test_filepath, exam_filepath):
    """
    Extract mapping for comp_test scenario
    - comp_test_filepath: target file (contains the correct answers)
    - exam_filepath: exam file (current selections to compare against target)
    
    Correct Logic: For each exam question:
    1. Check if exam main ID already exists as target main ID → no change needed
    2. If not, get ALL alternatives from that exam question section
    3. Search target to find which target main question contains any exam alternative
    4. Suggest changing exam main ID to that target main ID
    """
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
    target_alternatives_map = {}  # alternative_id → main_id
    
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
    
    # Build mapping: exam_main_id → target_main_id (what exam should change to)
    exam_to_target_mapping = {}
    # Collect all exam main IDs for exclusion
    all_exam_main_ids = set(main_id for _, main_id in exam_sorted)
    # Track which target main IDs have already been assigned to prevent duplicates
    assigned_target_main_ids = set()

    for i, (exam_q_num, exam_main_id) in enumerate(exam_sorted):
        question_num = int(exam_q_num)

        # STEP 1: Check if exam main ID is already a target main ID
        if exam_main_id in target_main_ids:
            exam_to_target_mapping[exam_main_id] = exam_main_id
            assigned_target_main_ids.add(exam_main_id)  # Track this assignment
            print(f"DEBUG: Q{question_num} exam main ID {exam_main_id} is already target main - no change")
            continue

        # STEP 2: Get all alternatives from this exam question section
        if i < len(exam_sorted) - 1:
            next_q_num = int(exam_sorted[i+1][0])
            section_pattern = rf'{question_num}\.\s+.*?(?={next_q_num}\.\s+)'
        else:
            section_pattern = rf'{question_num}\.\s+.*'

        section_match = re.search(section_pattern, exam_decoded, re.DOTALL)

        if section_match:
            section_content = section_match.group(0)
            exam_section_ids = re.findall(r'\(id:(\d+)\)', section_content)
            exam_unique_ids = list(dict.fromkeys(exam_section_ids))

            print(f"DEBUG: Exam Q{question_num} has {len(exam_unique_ids)} alternatives: {exam_unique_ids[:5]}...")

            # STEP 3: Find all possible target main matches for exam alternatives
            possible_target_main_ids = []
            for exam_alt_id in exam_unique_ids:
                if exam_alt_id in target_alternatives_map:
                    target_main_id = target_alternatives_map[exam_alt_id]
                    # Only consider if:
                    # 1. Not already a main question in exam
                    # 2. Not already assigned to another exam question
                    if (target_main_id not in all_exam_main_ids and 
                        target_main_id not in assigned_target_main_ids):
                        possible_target_main_ids.append(target_main_id)

            if possible_target_main_ids:
                # Use the first valid target main ID
                chosen_target_main = possible_target_main_ids[0]
                exam_to_target_mapping[exam_main_id] = chosen_target_main
                assigned_target_main_ids.add(chosen_target_main)  # Track this assignment
                print(f"DEBUG: Q{question_num} exam main {exam_main_id} → target main {chosen_target_main} (filtered, via alternatives)")
            else:
                print(f"DEBUG: Q{question_num} exam main {exam_main_id} - NO MATCH in target (after filtering)")

    print(f"DEBUG: Total exam→target mappings: {len(exam_to_target_mapping)}")

    return exam_to_target_mapping, None

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
    root.title("📄 Exam Clone Tool")
    root.geometry("1100x900")
    
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
        text="📄 Exam Clone Tool", 
        font=("Arial", 18, "bold"), fg="navy")
    title_label.pack(pady=(0, 15))
    
    # File selection frame
    file_frame = tk.Frame(main_frame)
    file_frame.pack(fill=tk.X, pady=10)
    
    # Target file selection (FIRST - correct answers)
    target_frame = tk.Frame(file_frame)
    target_frame.pack(fill=tk.X, pady=3)
    
    tk.Label(target_frame, text="Target File (correct):", width=18, anchor='w', font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    target_path_var = tk.StringVar()
    target_entry = tk.Entry(target_frame, textvariable=target_path_var, width=65)
    target_entry.pack(side=tk.LEFT, padx=5)
    
    def select_target_file():
        file_path = filedialog.askopenfilename(
            title="Select Target File (correct answers or comp test)",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if file_path:
            target_path_var.set(file_path)
    
    tk.Button(target_frame, text="Browse", command=select_target_file, bg="lightgreen").pack(side=tk.LEFT, padx=5)
    
    # Exam file selection (SECOND - test to compare)
    exam_frame = tk.Frame(file_frame)
    exam_frame.pack(fill=tk.X, pady=3)
    
    tk.Label(exam_frame, text="Test File (to compare):", width=18, anchor='w', font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    exam_path_var = tk.StringVar()
    exam_entry = tk.Entry(exam_frame, textvariable=exam_path_var, width=65)
    exam_entry.pack(side=tk.LEFT, padx=5)
    
    def select_exam_file():
        file_path = filedialog.askopenfilename(
            title="Select Test File (current selections to compare)",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if file_path:
            exam_path_var.set(file_path)
    
    tk.Button(exam_frame, text="Browse", command=select_exam_file, bg="lightblue").pack(side=tk.LEFT, padx=5)
    
    # Compare button
    def generate_mapping():
        target_file = target_path_var.get().strip()
        exam_file = exam_path_var.get().strip()
        
        if not target_file or not exam_file:
            messagebox.showerror("Error", "Please select both files")
            return
        
        if not os.path.exists(target_file):
            messagebox.showerror("Error", f"Target file not found: {target_file}")
            return
            
        if not os.path.exists(exam_file):
            messagebox.showerror("Error", f"Test file not found: {exam_file}")
            return
        
        # Clear previous results
        status_text.delete(1.0, tk.END)
        results_text.delete(1.0, tk.END)
        
        status_text.insert(tk.END, "🔍 Analyzing test file...\n")
        root.update()
        
        # Get exam current selections
        exam_current, exam_error = extract_numbered_questions(exam_file)
        if exam_error:
            status_text.insert(tk.END, f"❌ Test file error: {exam_error}\n")
            return
        
        status_text.insert(tk.END, f"✅ Test questions: {len(exam_current)}\n")
        status_text.insert(tk.END, "🔍 Detecting target file type...\n")
        root.update()
        
        # Detect target file type automatically
        file_type, type_info = detect_file_type(target_file)
        status_text.insert(tk.END, f"📋 {type_info}\n")
        root.update()
        
        # Get mapping based on file type
        if file_type == "normal_target":
            status_text.insert(tk.END, "🔧 Using normal target mapping algorithm...\n")
            alt_to_main, target_error = extract_target_mapping_fixed(target_file)
        elif file_type == "comp_test":
            status_text.insert(tk.END, "🎯 Using comp test mapping algorithm...\n")
            alt_to_main, target_error = extract_comp_test_mapping(target_file, exam_file)
        else:
            status_text.insert(tk.END, f"❌ Unknown file type: {type_info}\n")
            return
        
        if target_error:
            status_text.insert(tk.END, f"❌ Target file error: {target_error}\n")
            return
        
        status_text.insert(tk.END, f"✅ Target mapping created: {len(alt_to_main)} entries\n")
        
        # Generate results
        results_text.insert(tk.END, "📄 EXAM CLONE REPORT\n")
        results_text.insert(tk.END, "=" * 70 + "\n")
        results_text.insert(tk.END, f"Target File: {os.path.basename(target_file)} ({file_type})\n")
        results_text.insert(tk.END, f"Test File: {os.path.basename(exam_file)} (to compare)\n")
        results_text.insert(tk.END, f"Analysis: {type_info}\n")
        results_text.insert(tk.END, "=" * 70 + "\n\n")
        
        changes_needed = []
        no_change_needed = []
        no_mapping_found = []
        
        # Process each exam position with different logic for comp_test
        if file_type == "comp_test":
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
                        results_text.insert(tk.END, f"Question #{i}: Change (ID:{current_id}) → (ID:{target_id})\n")
                        changes_needed.append({
                            'position': i,
                            'from_id': current_id,
                            'to_id': target_id
                        })
                else:
                    # No mapping found (shouldn't happen if comp_test algorithm is correct)
                    results_text.insert(tk.END, f"Question #{i}: ❌ Unknown ID:{current_id} (not in comp test mapping)\n")
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
                        results_text.insert(tk.END, f"Question #{i}: Change (ID:{current_id}) → (ID:{main_id})\n")
                        changes_needed.append({
                            'position': i,
                            'from_id': current_id,
                            'to_id': main_id
                        })
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

if __name__ == "__main__":
    create_fixed_mapping_gui()