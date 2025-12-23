"""Utility functions for output processing."""


def truncate_output(
    output: str,
    max_lines: int = 100,
    max_chars: int = 5000,
    context_lines: int = 10,
) -> tuple[str, bool, int]:
    """
    Truncate output to save tokens while preserving useful context.

    Strategy:
    - Keep first N lines (beginning of output)
    - Keep last N lines (end of output, often contains errors/results)
    - Add clear truncation indicator in the middle

    Args:
        output: The output string to potentially truncate
        max_lines: Maximum number of lines to keep (default: 100)
        max_chars: Maximum number of characters to keep (default: 5000)
        context_lines: Number of lines to keep from start and end (default: 10)

    Returns:
        Tuple of (truncated_output, was_truncated, original_line_count)
    """
    if not output:
        return output, False, 0

    lines = output.split("\n")
    original_line_count = len(lines)
    was_truncated = False

    # Check if truncation by line count is needed
    if len(lines) > max_lines:
        # Keep context from start and end
        start_lines = lines[:context_lines]
        end_lines = lines[-context_lines:]

        truncated_count = len(lines) - (2 * context_lines)
        truncation_marker = f"\n... [{truncated_count} lines truncated for token efficiency] ...\n"

        output = "\n".join(start_lines) + truncation_marker + "\n".join(end_lines)
        was_truncated = True

    # Check if truncation by character count is needed
    if len(output) > max_chars:
        # Keep beginning and show truncation info
        char_count = len(output)
        output = output[:max_chars]
        output += f"\n\n... [truncated at {max_chars} chars, original: {char_count} chars] ..."
        was_truncated = True

    return output, was_truncated, original_line_count
