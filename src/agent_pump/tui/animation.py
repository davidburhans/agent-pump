from textual.widget import Widget

def shake(widget: Widget, duration: float = 0.05) -> None:
    """
    Shake the widget horizontally to indicate an error or invalid action.
    
    Args:
        widget: The widget to shake.
        duration: Duration of each step in the shake animation.
    """
    # Shake sequence: right, left, right, left, reset
    # Using tuple offsets (x, y)
    offsets = [(2, 0), (-2, 0), (1, 0), (-1, 0), (0, 0)]
    
    def _step(i: int) -> None:
        if i >= len(offsets):
            # Ensure we reset to None/default to respect original CSS
            # Setting to None removes the inline style
            widget.styles.offset = None # type: ignore
            return
            
        widget.styles.offset = offsets[i] # type: ignore
        widget.set_timer(duration, lambda: _step(i + 1))

    _step(0)
