"""
AI utility functions for cleaning and parsing AI responses.
"""

from typing import Any


def extract_from_malformed_json(json_str: str) -> dict[str, Any] | None:
    """
    Extracts contract terms from malformed or incomplete JSON strings.
    
    Inputs:
        json_str: A string that should contain JSON but may be malformed or incomplete.
    
    What happens:
        Uses regex patterns to find key-value pairs even if JSON syntax is broken.
        Looks for contract fields: wholesale_price, buyback_price, contract_length, cap_value, etc.
        Converts numeric values to floats.
        Keeps string values (like contract_type) as strings.
        Returns None if no valid terms found.
    
    Output:
        Returns a dictionary with extracted contract terms, or None if extraction fails.
    
    Context:
        Used as a fallback when AI returns JSON that can't be parsed normally.
        Handles cases where AI returns incomplete JSON (e.g., "wholesale_price: 23.0, buyback_price: 11.0, contract_length:").
        Called by generate_chat_response when JSON parsing fails.
    """
    import re
    result = {}
    
    # Try to extract key-value pairs even if JSON is malformed
    patterns = {
        "wholesale_price": r'wholesale_price["\s]*:[\s]*(\d+(?:\.\d+)?)',
        "buyback_price": r'buyback_price["\s]*:[\s]*(\d+(?:\.\d+)?)',
        "contract_length": r'contract_length["\s]*:[\s]*(\d+)',
        "length": r'"length"["\s]*:[\s]*(\d+)',
        "cap_value": r'cap_value["\s]*:[\s]*(\d+(?:\.\d+)?)',
        "cap_type": r'cap_type["\s]*:[\s]*"([^"]+)"',
        "contract_type": r'contract_type["\s]*:[\s]*"([^"]+)"',
        "revenue_share": r'revenue_share["\s]*:[\s]*(\d+(?:\.\d+)?)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, json_str, re.IGNORECASE)
        if match:
            if key in ("cap_type", "contract_type"):
                result[key] = match.group(1)
            else:
                try:
                    result[key] = float(match.group(1))
                except ValueError:
                    pass
    
    return result if result else None


def clean_ai_response(message: str) -> str:
    """
    Cleans AI response text to make it suitable for display to students.
    
    Inputs:
        message: Raw AI response text that may contain markdown, emojis, or technical markers.
    
    What happens:
        Removes NEGOTIATION_COMPLETE markers (technical, not for students).
        Removes CONTRACT_JSON markers and JSON blocks.
        Removes markdown formatting (bold, italic, bullets).
        Removes emojis and special characters.
        Cleans up extra whitespace and newlines.
        If message becomes empty after cleaning, provides a friendly default message.
    
    Output:
        Returns cleaned plain text message suitable for student display.
    
    Context:
        Called before displaying AI messages to students.
        Ensures students only see friendly, readable text without technical details.
        Used in generate_chat_response and evaluate_proposal_with_ai.
    """
    import re
    
    # Remove NEGOTIATION_COMPLETE markers (case insensitive)
    message = re.sub(r'NEGOTIATION_COMPLETE\s*:\s*yes', '', message, flags=re.IGNORECASE)
    message = re.sub(r'negotiation_complete\s*:\s*yes', '', message, flags=re.IGNORECASE)
    
    # Remove any remaining CONTRACT_JSON: text first
    message = re.sub(r'CONTRACT_JSON\s*:?\s*', '', message, flags=re.IGNORECASE)
    # Remove any JSON blocks that might have been missed
    message = re.sub(r'\{[^{}]*"wholesale_price"[^{}]*\}', '', message, flags=re.DOTALL)
    
    # Remove markdown bold (**text**)
    message = re.sub(r'\*\*([^*]+)\*\*', r'\1', message)
    # Remove markdown italic (*text*)
    message = re.sub(r'\*([^*]+)\*', r'\1', message)
    # Remove bullet points and convert to plain text
    message = re.sub(r'^[\s]*[-*•]\s*', '', message, flags=re.MULTILINE)
    # Remove emojis and special characters (but preserve spaces)
    message = re.sub(r'[^\w\s\.,!?;:\-\$\(\)\n]', '', message)
    
    # Fix concatenated words (insert space between lowercase letter and uppercase letter)
    # Example: "word1Word2" -> "word1 Word2"
    message = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', message)
    # Fix concatenated words (insert space between letter and number when appropriate)
    # Example: "word123" -> "word 123" (but be careful not to break prices like "$25")
    message = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', message)
    message = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', message)
    
    # Clean up multiple spaces
    message = re.sub(r' +', ' ', message)
    # Ensure proper newlines (replace multiple newlines with double newline)
    message = re.sub(r'\n{3,}', '\n\n', message)
    # Fix spaces before punctuation (remove extra spaces)
    message = re.sub(r'\s+([\.,!?;:])', r'\1', message)
    
    # If message is empty or only whitespace after cleaning, provide a friendly default
    cleaned = message.strip()
    if not cleaned or cleaned.lower() in ['yes', 'negotiation complete']:
        cleaned = "Great! Let's proceed with these terms."
    
    return cleaned

