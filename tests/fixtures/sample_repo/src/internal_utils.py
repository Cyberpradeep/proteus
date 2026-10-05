"""Internal utility functions with no external API dependencies or calls."""


def calculate_tax(subtotal: float, rate: float = 0.08) -> float:
    """Pure local computation without API calls."""
    return round(subtotal * rate, 2)


def format_currency(amount: float) -> str:
    """Format string without external network IO."""
    return f"${amount:,.2f}"
