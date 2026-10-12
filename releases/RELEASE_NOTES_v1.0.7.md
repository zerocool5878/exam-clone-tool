# Exam Clone Tool v1.0.7

## What's fixed

- **Wrong reports on some exams.** Question text containing a decimal followed by a
  sentence break (for example "...multiplier is 3.86. The radius...") was being
  read as question number 86, which hid real questions and produced duplicate or
  "no suitable alternatives" rows. Questions are now located by the LMS markup
  itself, so prose can no longer be mistaken for a question.
- **Matched questions can now move when needed.** If the only way to reach a
  missing target question is through a question that already matches, the tool
  moves it and chains the displaced ID to another question that carries it as an
  alternate. Previously such cases were reported as unsolvable.
- **Alternates that appear under several questions.** The tool now changes the
  question whose current ID is not already a target question, leaving existing
  matches alone.
- **Saved view-source pages are accepted.** Pages saved from Chrome's
  view-source tab work the same as the browser capture.
- **Problems are shown on screen.** Target IDs that cannot be reached, or
  mismatched question counts, are reported in the results instead of only in the
  log file.

## How it reads

- Question order does not matter; the goal is for the test to contain the same
  question IDs as the target.
- "Already correct" means the test question's ID is one of the target's.
- "Change ... -> alternate" tells you which alternate to select for that question.
- "After these changes the test will be identical to the target" confirms the plan
  is complete.

## Installation

1. Download `Exam_Clone_Tool_v1.0.7.exe` below.
2. Run it directly. No installation and no Python required; browser capture and
   auto-update support are built in.
3. The tool checks for updates on startup.

## System requirements

- Windows 10 or later
- Internet connection (for update checks)
