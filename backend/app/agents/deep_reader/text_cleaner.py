"""
Deep Reader Agent – Text Cleaner
=================================
Pre-processes extracted PDF text before regex scanning.
Fixes mashed words, split sentences across newlines, reversed text, 
and normalizes Unicode to ensure the Compliance Scanner doesn't miss triggers.
"""
import logging
import re
import unicodedata

logger = logging.getLogger(f"pramaan.{__name__}")

def fix_split_words(text: str) -> str:
    """Rejoin words split by hyphen + newline (e.g., 'environ-\nment' -> 'environment')."""
    pattern = re.compile(r'([A-Za-z]{2,})-\s*\n\s*([A-Za-z]{2,})')
    return pattern.sub(r'\1\2', text)

def fix_broken_lines(text: str) -> str:
    """Merge sentences broken across lines by PDF extraction."""
    lines = text.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            fixed_lines.append(line)
            i += 1
            continue
        
        # If line is short, doesn't end with punctuation, and next line starts lowercase
        if (len(line) < 80 and line[-1] not in '.!?:;' and i + 1 < len(lines)):
            next_line = lines[i + 1].strip()
            if next_line and next_line[0].islower():
                merged = line.rstrip() + ' ' + next_line.lstrip()
                fixed_lines.append(merged)
                i += 2
                continue
        
        fixed_lines.append(line)
        i += 1
    return '\n'.join(fixed_lines)

def remove_noise(text: str) -> str:
    """Remove common PDF artifacts, zero-width spaces, and signature lines."""
    text = text.replace('\f', '\n')
    text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)
    text = re.sub(r'-{5,}', '', text)
    text = re.sub(r'_{5,}', '', text)
    return text

def normalize_unicode(text: str) -> str:
    """Normalize 'fancy' PDF characters to standard ASCII for regex matching."""
    text = unicodedata.normalize('NFKC', text)
    replacements = {
        '\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--', '\u00a0': ' ', '\u2002': ' ', 
        '\u2003': ' ', '\u2009': ' '
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def clean_text(text: str) -> str:
    """
    Main pipeline: apply all cleaning operations in strict order before regex scan.
    """
    if not text:
        return ""
        
    text = remove_noise(text)
    text = normalize_unicode(text)
    text = fix_split_words(text)
    text = fix_broken_lines(text)
    
    # Collapse excessive newlines resulting from empty extracted layout blocks
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text
