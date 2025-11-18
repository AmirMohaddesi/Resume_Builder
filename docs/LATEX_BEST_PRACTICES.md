# LaTeX Best Practices for Resume Generation

## Critical Rules (MUST FOLLOW)

### 1. Newlines and Line Breaks
- **NEVER use escaped newlines (`\n`) in LaTeX content**
- Use actual line breaks (press Enter) in the LaTeX file
- LaTeX handles line breaks automatically; escaped `\n` will cause compilation errors

### 2. Special Character Escaping
- **Underscores in plain text**: Use `\_` (e.g., `Python\_script` not `Python_script`)
- **Percent signs**: Use `\%` (e.g., `50\%` not `50%`)
- **Ampersands**: Use `\&` in regular text
- **Dollar signs**: Use `\$` in regular text
- **Hash symbols**: Use `\#` in regular text
- **Tildes**: Use `\~{}` for non-breaking space or `\textasciitilde{}` for actual tilde

### 3. List Environments
- **All `\item` commands MUST be inside list environments** (`\begin{itemize}...\end{itemize}` or `\begin{enumerate}...\end{enumerate}`)
- Never place `\item` outside of a list environment
- Always close list environments with `\end{itemize}` or `\end{enumerate}`

### 4. Braces and Environments
- **Every `\begin{...}` MUST have a matching `\end{...}`**
- Count opening `{` and closing `}` to ensure they match
- Common environments: `document`, `itemize`, `enumerate`, `description`, `tabular`

### 5. Markdown and Code Fences
- **NEVER include markdown code fences** (``` or `````) in LaTeX output
- Remove any markdown formatting before generating LaTeX
- LaTeX is NOT markdown - use LaTeX commands only

### 6. Content Structure
- Use `\section*{Title}` for unnumbered sections
- Use `\subsection*{Title}` for subsections
- Use `\textbf{text}` for bold, `\textit{text}` for italic
- Use `\\` for line breaks within paragraphs (sparingly)

## Common Errors and Fixes

### Error: "Missing $ inserted"
- **Cause**: Special characters (_, %, &, $, #) not escaped in regular text
- **Fix**: Escape all special characters as listed above

### Error: "Undefined control sequence"
- **Cause**: Typo in LaTeX command or missing package
- **Fix**: Check command spelling, ensure required packages are in preamble

### Error: "Runaway argument" or "File ended while scanning"
- **Cause**: Unmatched braces `{` or `}`
- **Fix**: Count and match all braces, ensure all environments are closed

### Error: "There's no line here to end" or "Overfull/Underfull hbox"
- **Cause**: Line break issues or text too long for line
- **Fix**: Use `\\` sparingly, let LaTeX handle line breaks naturally

### Error: "Something's wrong--perhaps a missing \item"
- **Cause**: `\item` used outside of list environment
- **Fix**: Wrap all `\item` commands in `\begin{itemize}...\end{itemize}`

### Error: "LaTeX Error: Something's wrong--perhaps a missing \item"
- **Cause**: Empty list environment or `\item` formatting issue
- **Fix**: Ensure at least one `\item` in each list, check for formatting errors

## Successful Patterns

### Experience Section
```latex
\section*{Experience}
\begin{itemize}
    \item \textbf{Job Title} at Company Name (Duration): Description of role and achievements.
    \item \textbf{Job Title} at Company Name (Duration): Description of role and achievements.
\end{itemize}
```

### Skills Section
```latex
\section*{Skills}
\begin{itemize}
    \item Programming: Python, Java, JavaScript
    \item Frameworks: React, Node.js, Django
    \item Tools: Git, Docker, AWS
\end{itemize}
```

### Education Section
```latex
\section*{Education}
Bachelor's in Computer Science, University Name, Year
```

## What NOT to Do

1. ❌ Using `\n` for newlines (use actual line breaks)
2. ❌ Including markdown code fences (```)
3. ❌ Unescaped special characters in plain text
4. ❌ `\item` outside of list environments
5. ❌ Unmatched braces or unclosed environments
6. ❌ Mixing markdown and LaTeX syntax
7. ❌ Using HTML tags instead of LaTeX commands

## Verification Checklist

Before generating LaTeX, verify:
- [ ] No escaped `\n` characters
- [ ] All special characters properly escaped
- [ ] All `\item` commands inside list environments
- [ ] All `\begin{...}` have matching `\end{...}`
- [ ] No markdown code fences
- [ ] All braces `{` and `}` are matched
- [ ] Content uses LaTeX commands, not markdown

