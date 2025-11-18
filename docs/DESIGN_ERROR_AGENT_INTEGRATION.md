# Design Error Memory - Agent Integration

## Overview

The design error memory system is now fully integrated with all content-generating agents. Agents can directly access the design error memory JSON file through the `design_error_checker` tool to learn from past mistakes and prevent recurring design issues.

## Agents That Benefit

### 🎯 **Primary Beneficiaries** (Content Generation Agents)

These agents directly generate content that can have design issues:

1. **`header_writer`** ⭐ **CRITICAL**
   - **Why**: Creates headers with title lines - this is where "four pipes" issue occurs
   - **Tool**: `design_error_checker(context="header")`
   - **Backstory**: Explicitly instructed to check for known errors before writing
   - **Task**: `write_header_task` - FIRST action is to call design_error_checker

2. **`summary_writer`**
   - **Why**: Creates summary text - can have length/formatting issues
   - **Tool**: `design_error_checker(context="summary")`
   - **Backstory**: Instructed to check for known errors before writing
   - **Task**: `write_summary_task` - FIRST action is to call design_error_checker

3. **`experience_selector`**
   - **Why**: Selects and formats experiences - can have bullet/formatting issues
   - **Tool**: `design_error_checker(context="experience")`
   - **Backstory**: Instructed to check for known errors before selecting
   - **Task**: `select_experiences_task` - FIRST action is to call design_error_checker

4. **`project_selector`**
   - **Why**: Selects and formats projects - can have bullet/formatting issues
   - **Tool**: `design_error_checker(context="projects")`
   - **Backstory**: Instructed to check for known errors before selecting
   - **Task**: `select_projects_task` - FIRST action is to call design_error_checker

5. **`skill_selector`**
   - **Why**: Creates skills list - can have formatting/length issues
   - **Tool**: `design_error_checker(context="skills")`
   - **Backstory**: Instructed to check for known errors before selecting
   - **Task**: `select_skills_task` - FIRST action is to call design_error_checker

6. **`education_writer`**
   - **Why**: Creates education section - can have formatting issues
   - **Tool**: `design_error_checker(context="education")`
   - **Backstory**: Instructed to check for known errors before writing
   - **Task**: `write_education_section_task` - FIRST action is to call design_error_checker

### 📋 **Secondary Beneficiaries** (Quality/Validation Agents)

These agents don't generate content but could benefit from awareness:

- **`ats_checker`**: Could check for design errors that affect ATS parsing
- **`privacy_guard`**: Could check for design errors related to privacy/formatting

## How Agents Use It

### 1. **Tool Access**

All content-generating agents have access to the `design_error_checker` tool:

```python
@tool
def design_error_checker(self):
    """Check for known design errors before generating content"""
    return DesignErrorCheckerTool()
```

### 2. **Agent Backstories**

Each agent's backstory explicitly instructs them to use the tool:

**Example (header_writer):**
```
CRITICAL: Before writing the header, use design_error_checker tool with context="header" 
to check for known design errors that users have reported. Common issues include excessive 
pipe separators (|) in title lines. Follow the prevention guidance to avoid repeating 
design mistakes that users have complained about.
```

### 3. **Task Descriptions**

Task descriptions make it the FIRST action:

**Example (write_header_task):**
```
Actions:
  - FIRST: Call design_error_checker(context="header") to check for known design errors that users have reported.
  - Review the prevention guidance from design_error_checker and follow it carefully.
  - [rest of actions...]
```

### 4. **Tool Response Format**

When agents call the tool, they receive:

```json
{
  "status": "success",
  "message": "Found 1 known design error(s) for context: header",
  "errors": [
    {
      "issue": "four pipes on top of the resume",
      "error_type": "HeaderFormatting",
      "count": 3,
      "prevention": "Header title line should use at most 2-3 pipe separators (|)..."
    }
  ],
  "prevention_guidance": {
    "warning": "Known design issue reported 3 times",
    "error_type": "HeaderFormatting",
    "issue": "four pipes on top of the resume",
    "prevention": "Header title line should use at most 2-3 pipe separators..."
  },
  "recommendation": "⚠️ IMPORTANT: Before generating header content, review the prevention guidance above..."
}
```

## Example Agent Workflow

### Header Writer Agent

1. **Task starts**: `write_header_task` begins
2. **First action**: Agent calls `design_error_checker(context="header")`
3. **Tool response**: Returns known errors (e.g., "four pipes" issue reported 3 times)
4. **Agent reads**: Prevention guidance: "Use at most 2-3 pipe separators"
5. **Agent generates**: Header with max 2-3 pipes, avoiding the known issue
6. **Result**: Design error prevented before it occurs

## Integration Points

### 1. **Tool Registration** (`crew.py`)
- `design_error_checker` tool registered and available to all agents

### 2. **Agent Configuration** (`agents.yaml`)
- All 6 content-generating agents have:
  - `design_error_checker` in their tools list
  - Explicit backstory instructions to use it
  - Context-specific guidance

### 3. **Task Configuration** (`tasks.yaml`)
- All 6 content-generating tasks have:
  - "FIRST: Call design_error_checker(...)" as the first action
  - Explicit instruction to review and follow prevention guidance

### 4. **Automatic Prevention** (`crew.py`)
- `_apply_design_error_prevention()` method injects warnings into task descriptions
- Provides additional layer of prevention beyond tool access

## Benefits

1. **Proactive Prevention**: Agents check for errors BEFORE generating content
2. **Direct Access**: Agents can query the memory directly via tool
3. **Explicit Instructions**: Both backstories and task descriptions emphasize using the tool
4. **Context-Aware**: Each agent checks errors relevant to their context
5. **Learning Loop**: User reports → Memory → Agent awareness → Prevention

## Priority Ranking

Based on likelihood of design errors:

1. **⭐ CRITICAL**: `header_writer` - Most common design issues (pipes, formatting)
2. **HIGH**: `summary_writer`, `experience_selector` - Length/formatting issues
3. **MEDIUM**: `project_selector`, `skill_selector` - Formatting issues
4. **LOW**: `education_writer` - Less common issues

## Example: "Four Pipes" Issue Prevention

### User Reports Error
```
User: "There are four pipes on top of the resume"
```

### System Records
- Issue: "four pipes"
- Context: "header"
- Count: 1

### Next Run - Header Writer Agent

1. **Agent starts** `write_header_task`
2. **Calls tool**: `design_error_checker(context="header")`
3. **Receives warning**:
   ```
   ⚠️ Known design issue reported 1 times
   Issue: four pipes on top of the resume
   Prevention: Header title line should use at most 2-3 pipe separators...
   ```
4. **Agent follows guidance**: Uses max 2-3 pipes
5. **Result**: Issue prevented ✅

### After 2 More Reports

- Count: 3
- Agent sees: "⚠️ Known design issue reported 3 times"
- Agent is even more careful to follow prevention guidance

## Summary

**All 6 content-generating agents** now have:
- ✅ Direct access to design error memory via `design_error_checker` tool
- ✅ Explicit instructions in backstories to use the tool
- ✅ Task descriptions that make it the FIRST action
- ✅ Context-specific error checking
- ✅ Prevention guidance integration

The system ensures agents learn from user feedback and prevent recurring design issues automatically.

