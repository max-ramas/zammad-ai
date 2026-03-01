"""Parse prompt files with optional YAML frontmatter."""

from logging import Logger
from pathlib import Path
from typing import Any

from yaml import safe_load

from app.utils.logging import getLogger

logger: Logger = getLogger("zammad-ai.utils.prompts")


def extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and remaining content from markdown text.

    Frontmatter must be delimited by `---` at the start of the file.
    If no frontmatter is present, returns empty dict and the full content.

    Args:
        content: The full content string (potentially with frontmatter)

    Returns:
        Tuple of (frontmatter_dict, remaining_prompt_text).
        If no frontmatter found, frontmatter_dict will be empty.

    Examples:
        >>> text = "---\\nversion: 1\\n---\\nPrompt content"
        >>> metadata, prompt = extract_frontmatter(text)
        >>> metadata
        {'version': 1}
        >>> prompt
        'Prompt content'

        >>> text = "Just prompt text"
        >>> metadata, prompt = extract_frontmatter(text)
        >>> metadata
        {}
        >>> prompt
        'Just prompt text'
    """
    content = content.lstrip()

    # Check if content starts with frontmatter delimiter
    if not content.startswith("---"):
        return {}, content

    # Find the end of frontmatter (second `---`)
    remaining = content[3:].lstrip("\n")
    lines = remaining.split("\n")

    end_index = None
    for i, line in enumerate(lines):
        if line.strip() == "---":
            end_index = i
            break

    if end_index is None:
        # No closing delimiter found, treat entire content as prompt
        return {}, content

    # Extract frontmatter and remaining content
    frontmatter_text = "\n".join(lines[:end_index]).strip()
    prompt_text = "\n".join(lines[end_index + 1 :]).lstrip("\n")

    # Parse YAML frontmatter
    metadata = {}
    if frontmatter_text:
        try:
            metadata = safe_load(frontmatter_text) or {}
        except Exception:
            logger.warning("Failed to parse YAML frontmatter.", exc_info=True)
            # Return empty metadata but still return the detected content boundary
            prompt_text = "\n".join(lines).lstrip("\n")

    return metadata, prompt_text


def load_prompt(file_path: Path | str) -> str:
    """Load a prompt file and return content without frontmatter.

    Reads a markdown or text file, extracts and removes any YAML frontmatter,
    and returns only the prompt text.

    Args:
        file_path: Path to the prompt file (str or Path object)

    Returns:
        The prompt text without frontmatter

    Raises:
        FileNotFoundError: If the file does not exist
        IOError: If the file cannot be read

    Examples:
        >>> prompt = load_prompt("prompts/my_prompt.md")
        >>> print(prompt)  # doctest: +SKIP
        Your prompt content...
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    content = path.read_text(encoding="utf-8")
    _, prompt_text = extract_frontmatter(content)

    return prompt_text.strip()
