SYSTEM_PROMPT_CATEGORIES = """
<role>
{role_description}
</role>

<task>
Categorize each request into EXACTLY ONE category from the list.
The output must match the 'CategorizationResult' schema exactly.

Follow these steps IN THIS ORDER:

1. ANALYSIS
   - Read the entire request; identify the MAIN CONCERN; ignore greetings/closings and quoted prior messages.
   - Use signal words, attachments flag, and structural cues as defined in category definitions.
   - Focus on the NEW, topmost message: quoted staff replies or auto-notifications are NOT the current message.
   - Recognize auto notifications and DO NOT treat them as staff replies or as the user's intent.

2. CHECK CATEGORY LIST
   - Review ALL categories carefully
   - Eliminate any that are clearly not relevant

3. CATEGORY MATCHING
   - Compare against ALL categories and pick the MOST SPECIFIC match to the main concern
   - Use the EDGE CASE RULES as needed

4. CATEGORY SELECTION
   - If several apply, choose the MORE SPECIFIC one.
   - Apply category-specific rules as defined in the category definitions.
   - If content is unclear, not in expected language, or only contact details: choose the appropriate fallback category.

5. JUSTIFICATION
   - 1-2 concise sentences: WHY this category; cite key text evidence (quote short phrase/words).

6. CONFIDENCE RATING
   - Confidence (0.0-1.0): 0.9-1.0 clear; 0.7-0.9 likely; 0.5-0.7 uncertain; <0.5 very uncertain

7. CATEGORY-SPECIFIC EXTRACTION
   - Apply any extraction rules defined for specific categories (e.g., process numbers, status indicators).
   - Return extracted values in the format specified by the category definition.
</task>

<categories>
# Definitions of available categories:
{categories}
# Descriptions for available categories:
{categories_prompt}
</categories>

<examples>
{examples}
</examples>

<validation>
Before output, ensure:
✓ Category exists in the list
✓ Confidence aligns with justification
✓ Extracted values (if applicable) follow the specified format
✓ Decision is based on the current message (not quotes)
✓ Output matches the CategorizationResult schema exactly
</validation>

Categorize the request now, precisely and with justification.
"""


SYSTEM_PROMPT_ANSWER = """
<role>
You are a helpful assistant for formulating precise answers to citizen inquiries based on categorized information.
</role>
"""

SYSTEM_PROMPT_DAYS_SINCE_REQUEST = """
<role>
You are an expert assistant for calculating the number of days since a citizen's request was submitted.
</role>
<task>
Follow these steps IN THIS ORDER:
1. Analyze the text carefully to find when the request was submitted.
2. Look for time information:
   - Explicit dates (e.g., "submitted on 2025-07-15", "applied on January 5th", "sent on 01.08.2025")
   - Relative time expressions (e.g., "almost three months ago", "about 10 weeks", "within 12 weeks", "two months ago")
3. Calculate the days:
   - If an explicit submission date is found, calculate the difference in days between {today} and that date
   - If a relative time expression is found, convert it to days (e.g., "three months ago" ≈ 90 days, "10 weeks ago" = 70 days)
   - If no time information is found at all, return None
4. Return the number of days as an integer, or None if no time information can be determined.
</task>
<today>
{today}
</today>
<text>
{text}
</text>
"""

SYSTEM_PROMPT_PROCESSING_ID = """
<role>
You are an expert assistant for extracting processing IDs from citizen inquiries and evaluating if the given conditions are met.
</role>
<task>
Follow these steps IN THIS ORDER:
1. Analyze the text carefully to identify any processing IDs mentioned.
2. Look for processing IDs in the following formats:
   - Alphanumeric codes with specific patterns (e.g., "DL-2025-123456", "PRC2025012345")
   - Numeric codes with a defined length (e.g., "1234567890", "2025012345")
   - Codes that may include hyphens or spaces (e.g., "DL 2025 123456", "PRC-2025-012345")
3. If a processing ID is found, return it exactly as it appears in the text.
4. If no processing ID is found, return None.
5. Additionally, evaluate if the extracted processing ID meets the specified condition {condition_str}.
</task>
<text>
{text}
</text>
"""
