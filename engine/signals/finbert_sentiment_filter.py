"""
Stub: FinBERT sentiment filter — disabled on VPS (model not available).
Returns neutral pass-through so scan pipeline continues.
"""

def finbert_sentiment_filter(signals, *args, **kwargs):
    """Pass-through stub — returns signals unchanged."""
    return signals

class FinBertSentimentFilter:
    def __init__(self, *args, **kwargs):
        pass
    
    def filter(self, signals, *args, **kwargs):
        return signals
    
    def score(self, text, *args, **kwargs):
        return {"label": "neutral", "score": 0.5}
