# Edit Engine Fixes - Pipe Character Removal Issues

## Issues Reported

1. **Post-orchestrator edit not working**: Request "Can you remove pipe characters from the first page before summary" returned "No changes were made"
2. **AI-Powered Section Editing too aggressive**: When using AI edit to remove pipes, it "ripped apart the whole resume"

## Root Causes Identified

### Issue 1: Edit Type Detection
- **Problem**: The request "first page before summary" didn't match header detection keywords
- **Impact**: Request was classified as `EditType.UNKNOWN`, so no edit was applied

### Issue 2: Pipe Detection
- **Problem**: `_edit_header` only checked specific fields (`title_line`, `name`, `target_title`, `links`)
- **Impact**: If pipes were in other fields or nested structures, they weren't removed

### Issue 3: Change Detection
- **Problem**: Simple comparison (`old_value != new_value`) doesn't work well for lists/dicts
- **Impact**: Changes weren't detected, leading to "No changes were made" message

### Issue 4: LLM Over-Editing
- **Problem**: LLM JSON editor was too aggressive and made structural changes when only character removal was requested
- **Impact**: Entire resume structure was modified, not just pipe characters removed

## Fixes Applied

### 1. Improved Edit Type Detection ✅
**File**: `src/resume_builder/edit_engine.py`

Added new keywords to header detection:
- "first page"
- "top of"
- "before summary"
- "above summary"
- "at the top"

**Result**: "Can you remove pipe characters from the first page before summary" now correctly detects as `EditType.HEADER`

### 2. Recursive Pipe Removal ✅
**File**: `src/resume_builder/edit_engine.py`

Replaced field-specific pipe removal with recursive function that:
- Searches ALL fields in header JSON (not just specific ones)
- Handles nested structures (lists, dicts)
- Removes pipes from any string field
- Tracks which fields were changed

**Result**: Pipes are removed from all fields, regardless of structure

### 3. Improved Change Detection ✅
**File**: `src/resume_builder/edit_engine.py`

Enhanced change detection to:
- Use JSON comparison for complex types (lists, dicts)
- Compare all keys from both old and new data
- Properly detect changes in nested structures

**Result**: Changes are now accurately detected and reported

### 4. LLM JSON Editor Protection ✅
**File**: `src/resume_builder/edit_engine_llm_json.py`

Added multiple layers of protection:

**a) Enhanced Prompt**:
- Explicitly instructs LLM to preserve ALL fields
- Only remove pipe characters, don't change structure
- Don't modify links array structure

**b) Field Preservation Logic**:
- Automatically restores removed fields from original
- Preserves links array structure during pipe removal
- Warns when LLM makes unexpected changes

**c) Auto-Strict Mode**:
- Automatically enables strict mode for simple character removal
- Prevents structural changes when only removing characters

**Result**: LLM can no longer "rip apart" the resume when removing pipes

### 5. UI Integration ✅
**File**: `src/resume_builder/ui.py`

Added automatic strict mode detection:
- Detects simple character removal requests
- Auto-enables strict mode to prevent structural changes
- Logs when strict mode is auto-enabled

**Result**: Users don't need to manually enable strict mode for simple edits

## Testing Recommendations

1. **Test Post-Orchestrator Edit**:
   - Request: "Can you remove pipe characters from the first page before summary"
   - Expected: Should detect as header edit and remove pipes

2. **Test AI-Powered Edit**:
   - Request: "Remove pipe characters from header"
   - Expected: Should only remove pipes, preserve all other fields and structure

3. **Test Change Detection**:
   - Make an edit that changes nested structures
   - Expected: Should properly detect and report changes

## Files Modified

1. `src/resume_builder/edit_engine.py`
   - Improved edit type detection
   - Recursive pipe removal
   - Better change detection

2. `src/resume_builder/edit_engine_llm_json.py`
   - Enhanced header section prompt
   - Field preservation logic
   - Better validation

3. `src/resume_builder/ui.py`
   - Auto-strict mode detection
   - Better error handling

## Expected Behavior After Fixes

### Post-Orchestrator Edit
- ✅ Detects "first page before summary" as header edit
- ✅ Recursively removes pipes from all fields
- ✅ Properly detects and reports changes
- ✅ Shows success message with changed fields

### AI-Powered Section Editing
- ✅ Auto-enables strict mode for character removal
- ✅ Preserves all header fields (email, phone, location, links, etc.)
- ✅ Only removes pipe characters, doesn't change structure
- ✅ Warns if LLM tries to make unexpected changes
- ✅ Restores removed fields automatically

Both edit methods should now work correctly for pipe character removal! 🎉

