from pathlib import Path


def validate_is_prompt(path: Path) -> Path:
    if path.suffix.lower() not in [".txt", ".md"]:
        raise ValueError("Only TXT and MD files are allowed")
    return path
