# Exam Clone Tool v1.0.5 Release Notes

## Release Date: January 25, 2026

### 🚀 Major Improvements

#### Smart Matching Algorithm with Backtracking
- **NEW**: Implemented Maximum Bipartite Matching algorithm for optimal question assignment
- **NEW**: Added recursive backtracking solver with Most Constrained Variable (MRV) heuristic
- **IMPROVED**: Now handles complex multi-way conflicts where multiple questions share the same alternative pools

### 🔧 Technical Changes

#### New Functions Added:
- `find_maximum_bipartite_matching()` - Augmenting path algorithm (Hopcroft-Karp style) for optimal assignments
- `solve_exam_matching_with_backtracking()` - Recursive backtracking with constraint propagation

#### Algorithm Improvements:
- Questions with shared alternative pools (e.g., Q1, Q8, Q22 all sharing 17 alternatives) are now resolved correctly
- Falls back through multiple strategies: Backtracking → Bipartite Matching → Greedy
- Handles tests with heavily overlapping question banks (tested with 40-question exam with 16 conflict groups)

### 📋 Test Results
- Successfully matched 40/40 questions on complex test case
- Resolved 31 required remappings with 16 multi-way conflicts
- 100% match rate on previously failing test scenarios

### 📦 Dependencies
- No new required dependencies
- Optional: pywin32, pyautogui (for browser capture feature)
