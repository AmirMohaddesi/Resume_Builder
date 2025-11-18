# LLM vs Deterministic Edits: Analysis & Recommendations

## Current State

### LLM-Based Edits (2 types)
1. **Summary edits** - All summary modifications use LLM
2. **Cover letter edits** - All cover letter modifications use LLM

**Settings:**
- Model: `gpt-4o-mini` (cost-optimized)
- Temperature: `0` (deterministic)
- Max tokens: `500`
- No validation/confirmation

### Deterministic Edits (5 types)
1. **Skills** - Regex-based add/remove
2. **Experiences** - Position-based remove/swap
3. **Projects** - Position-based remove
4. **Education** - No edits allowed
5. **Header** - No edits allowed
6. **Section removal** - Metadata-based

## LLM Accuracy Concerns

### ✅ What LLMs Do Well
- **Semantic rewrites**: "Make summary more technical", "Emphasize leadership"
- **Tone adjustments**: "Make it more formal", "Add enthusiasm"
- **Content expansion**: "Expand this paragraph", "Add more detail"
- **Natural language understanding**: Complex requests like "Focus on AI/ML experience"

### ❌ What LLMs Struggle With
- **Precision**: May change facts, dates, numbers
- **Hallucination**: May add content not in original
- **Over-editing**: May change more than requested
- **Consistency**: May break formatting or style
- **Schema violations**: May corrupt JSON structure (though we validate)

## Risk Assessment

### High Risk (Current LLM Usage)
1. **Summary edits** - User's professional summary is critical
   - Risk: LLM might change key facts, dates, or achievements
   - Impact: High - summary is first thing recruiters see
   - Current mitigation: None (just returns edited text)

2. **Cover letter edits** - Important for job applications
   - Risk: LLM might change company name, job title, or key points
   - Impact: High - wrong company name = instant rejection
   - Current mitigation: None

### Low Risk (Deterministic)
- Skills add/remove: Safe (exact string matching)
- Experience reordering: Safe (position-based)
- Section removal: Safe (metadata-based)

## Recommendations

### Option 1: Keep LLM but Add Validation (Recommended)
**Hybrid approach with safety checks:**

```python
def _edit_summary_with_validation(self, request, current_data):
    original = current_data.get("summary", "")
    edited = self._llm_edit_text(original, request, "summary")
    
    # Validation checks
    if self._validate_edit_safety(original, edited, request):
        return edited
    else:
        # Fallback: show diff and ask user, or use deterministic fallback
        return self._deterministic_fallback(original, request)
```

**Validation checks:**
1. **Length check**: Edited text shouldn't be >2x or <0.5x original
2. **Key facts preserved**: Extract dates, numbers, company names - ensure they match
3. **No hallucination**: Check if edited text adds facts not in original
4. **Request compliance**: Verify edit actually addresses the request

### Option 2: Make LLM Edits Optional/Confirmable
**Let users choose:**

```python
# In UI
enable_llm_edits = gr.Checkbox(
    label="Use AI for text rewrites (may change wording)",
    value=False  # Default to safe mode
)
```

**Benefits:**
- Users who want precision can disable LLM
- Users who want flexibility can enable it
- Default to safe (deterministic) mode

### Option 3: Deterministic Fallbacks for Common Requests
**Expand deterministic coverage:**

```python
def _edit_summary(self, request, current_data):
    request_lower = request.lower()
    
    # Deterministic for common, safe operations
    if "shorter" in request_lower or "condense" in request_lower:
        return self._make_shorter_deterministic(current_data.get("summary", ""))
    elif "longer" in request_lower or "expand" in request_lower:
        return self._make_longer_deterministic(current_data.get("summary", ""))
    elif "remove" in request_lower and "sentence" in request_lower:
        return self._remove_sentence_deterministic(current_data.get("summary", ""))
    else:
        # Use LLM for complex semantic edits
        return self._llm_edit_text(...)
```

### Option 4: Show Diff Before Applying
**Always show what changed:**

```python
def apply_edit_with_preview(request):
    result = apply_edit_request(request)
    
    if result["ok"] and used_llm:
        # Show diff to user
        diff = generate_diff(original, edited)
        return {
            "preview": diff,
            "confirm_required": True,
            "original": original,
            "edited": edited
        }
```

## Recommended Implementation

**Hybrid approach with validation:**

1. **Keep LLM for complex semantic edits** (tone, style, emphasis)
2. **Add deterministic fallbacks** for simple operations (shorter, longer, remove sentence)
3. **Add validation** to catch obvious errors (fact changes, hallucinations)
4. **Show diff** for LLM edits (optional, can be toggled)
5. **Allow users to disable LLM** if they prefer precision

## Code Changes Needed

1. Add `_validate_edit_safety()` function
2. Add deterministic fallbacks for common operations
3. Add diff generation for LLM edits
4. Add UI toggle for LLM usage
5. Add fact extraction/comparison (dates, numbers, names)

## Conclusion

**Current LLM usage is risky** for critical content like summaries and cover letters. 

**Best approach:** 
- Use LLM for complex semantic edits only
- Add deterministic fallbacks for simple operations
- Add validation to catch errors
- Make LLM optional with user confirmation

This gives flexibility while maintaining safety.

