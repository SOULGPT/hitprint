import re

_YOU = re.compile(r"\b(you|your|you're)\b", re.IGNORECASE)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def title_features(title: str) -> dict:
    return {
        "title_len": len(title),
        "has_you": bool(_YOU.search(title)),
        "is_question": "?" in title,
        "has_number": any(c.isdigit() for c in title),
        "has_emoji": bool(_EMOJI.search(title)),
        "series_prefix": " ".join(title.lower().split()[:3]),
    }
