# Design Error Memory & Learning System

## Overview

The Design Error Memory system captures and learns from user-reported design/logical errors through the post-orchestration chatbox. Unlike LaTeX compilation errors, these are design issues like "four pipes in header" or formatting problems that don't prevent compilation but create poor user experience.

## Key Features

### 1. **Automatic Error Detection**
- Detects design error reports in user messages
- Extracts issue descriptions from natural language
- Classifies errors by type (HeaderFormatting, Spacing, Length, Layout, Typography)
- Identifies context (header, summary, experience, skills, projects, education)

### 2. **Error Recording**
- Records errors to `output/design_error_memory.json`
- Normalizes issue descriptions for matching
- Tracks error frequency (count) and timestamps
- Stores prevention suggestions for agents

### 3. **Agent Prevention Guidance**
- Injects prevention warnings into task descriptions
- Agents see known design errors before generating content
- Prevents recurring issues automatically
- Only warns for errors that occurred 2+ times (to avoid noise)

### 4. **Learning from Corrections**
- When users report issues via chatbox, they're automatically recorded
- System learns patterns (e.g., "four pipes" → "multiple pipes")
- Prevention guidance improves over time

## How It Works

### User Reports Error via Chatbox

**Example:**
```
User: "There are four pipes on top of the resume"
```

**System Response:**
1. Detects error indicators: "there are", "four pipes"
2. Extracts issue: "four pipes"
3. Identifies context: "header" (from "top of resume")
4. Records error with:
   - Normalized issue: "multiple pipes"
   - Error type: "HeaderFormatting"
   - Context: "header"
   - Prevention: "Header title line should use at most 2-3 pipe separators..."

### Agent Prevention

**Before Content Generation:**
- System checks for known errors in that context
- If error occurred 2+ times, adds warning to task description:
  ```
  ⚠️ Known design issue in header (reported 3 times): 
  Header title line should use at most 2-3 pipe separators (|). 
  Avoid excessive separators...
  ```

**Agent Behavior:**
- Agent sees warning before generating header
- Follows prevention guidance
- Avoids the known design error

## Error Types

| Type | Description | Examples |
|------|-------------|----------|
| **HeaderFormatting** | Issues with header/title line formatting | "four pipes", "excessive separators" |
| **Spacing** | Spacing problems | "too much space", "gap", "margin" |
| **Length** | Content length issues | "too long", "truncated", "cut off" |
| **Layout** | Layout/alignment problems | "alignment", "position", "placement" |
| **Typography** | Font/style issues | "font size", "bold", "typography" |
| **Unknown** | Other design issues | Fallback category |

## Integration Points

### 1. Chatbox Handler (`ui.py`)
- **Location**: `handle_adjustment()` function
- **Action**: Detects and records design errors from user messages
- **Timing**: Before applying edit requests

### 2. Task Configuration (`crew.py`)
- **Location**: `_apply_design_error_prevention()` method
- **Action**: Injects prevention guidance into task descriptions
- **Timing**: When tasks are created (before agent execution)

### 3. Task YAML (`tasks.yaml`)
- **Location**: Task descriptions
- **Action**: Hard-coded rules (e.g., "CRITICAL: Use at most 2-3 pipe separators")
- **Timing**: Always present in task instructions

## Example Flow

### Scenario: "Four Pipes" Issue

1. **User reports**: "There are four pipes on top of the resume"

2. **System detects**:
   ```python
   detected_error = {
       "issue_description": "four pipes",
       "context": "header",
       "normalized_issue": "multiple pipes"
   }
   ```

3. **System records**:
   ```json
   {
     "issue_description": "four pipes",
     "normalized_issue": "multiple pipes",
     "context": "header",
     "error_type": "HeaderFormatting",
     "prevention": "Header title line should use at most 2-3 pipe separators...",
     "count": 1,
     "first_seen": "2025-01-17T10:00:00",
     "last_seen": "2025-01-17T10:00:00"
   }
   ```

4. **Next run - Agent sees warning**:
   ```
   ⚠️ Known design issue in header (reported 1 times): 
   Header title line should use at most 2-3 pipe separators (|). 
   Avoid excessive separators. Use '|' or '•' sparingly for visual clarity.
   
   [Original task description follows...]
   ```

5. **Agent generates header**:
   - Sees warning about pipes
   - Uses at most 2-3 separators
   - Avoids the "four pipes" issue

## Error Detection Patterns

The system detects errors using these patterns:

- **Error indicators**: "there are", "there is", "problem", "issue", "error", "wrong", "too many", "too much", "excessive", "missing", "looks bad", "fix the", "remove the"

- **Issue extraction**:
  - "there are/is [something]" → extracts [something]
  - "[something] is wrong/bad/problem" → extracts [something]
  - "too many/much [something]" → extracts "too many [something]"
  - "remove/get rid of [something]" → extracts "remove [something]"

## Configuration

- **File**: `output/design_error_memory.json`
- **Max cache size**: 500 entries
- **Enable/disable**: `ENABLE_DESIGN_ERROR_MEMORY = True` in `design_error_memory.py`

## Benefits

1. **Proactive Prevention**: Agents avoid known design errors before they occur
2. **Continuous Learning**: System learns from every user report
3. **Reduced Manual Fixes**: Fewer design issues require user intervention
4. **Better UX**: Resumes improve over time as system learns
5. **Transparent**: Users can see what the system has learned

## Example Error Records

```json
{
  "errors": [
    {
      "issue_description": "four pipes on top of the resume",
      "normalized_issue": "multiple pipes header",
      "context": "header",
      "error_type": "HeaderFormatting",
      "prevention": "Header title line should use at most 2-3 pipe separators (|). Avoid excessive separators. Use '|' or '•' sparingly for visual clarity.",
      "first_seen": "2025-01-17T10:00:00",
      "last_seen": "2025-01-17T15:30:00",
      "count": 3,
      "user_message": "There are four pipes on top of the resume"
    }
  ]
}
```

## Future Enhancements

Potential improvements:
- Machine learning to predict likely errors before generation
- Automatic fixes for common design errors
- Integration with LaTeX builder to validate design rules
- User feedback loop to confirm fixes worked

