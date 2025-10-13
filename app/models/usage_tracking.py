"""
Usage tracking models for API cost monitoring.
Tracks API calls, tokens, and costs.
"""

from datetime import datetime
from mongoengine import Document, StringField, IntField, FloatField, DateTimeField, DictField


class APIUsage(Document):
    """Track API usage and costs."""
    
    # Metadata
    user_id = StringField(required=False)
    thread_id = StringField(required=True)
    session_id = StringField(required=False)
    
    # API details
    model = StringField(required=True)  # gpt-4, claude-3, etc.
    provider = StringField(required=True)  # openai, anthropic, google
    
    # Token usage
    input_tokens = IntField(default=0)
    output_tokens = IntField(default=0)
    total_tokens = IntField(default=0)
    
    # Cost tracking
    input_cost = FloatField(default=0.0)  # Cost in USD
    output_cost = FloatField(default=0.0)
    total_cost = FloatField(default=0.0)
    
    # Request details
    request_type = StringField(default='chat')  # chat, completion, embedding, etc.
    duration_ms = IntField(default=0)  # Request duration in milliseconds
    
    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    
    # Additional metadata
    metadata = DictField(default={})
    
    meta = {
        'collection': 'api_usage',
        'indexes': [
            'user_id',
            'thread_id',
            'created_at',
            'model',
            'provider'
        ]
    }
    
    @classmethod
    def log_usage(cls, thread_id: str, model: str, provider: str, 
                   input_tokens: int, output_tokens: int,
                   user_id: str = None, **kwargs):
        """Log API usage with automatic cost calculation."""
        
        # Calculate costs based on model
        pricing = cls._get_pricing(model, provider)
        input_cost = (input_tokens / 1000) * pricing['input']
        output_cost = (output_tokens / 1000) * pricing['output']
        total_cost = input_cost + output_cost
        
        usage = cls(
            user_id=user_id,
            thread_id=thread_id,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            **kwargs
        )
        usage.save()
        return usage
    
    @staticmethod
    def _get_pricing(model: str, provider: str) -> dict:
        """Get pricing per 1K tokens for different models."""
        
        # Prices as of 2024 (update as needed)
        pricing_table = {
            'openai': {
                'gpt-4o': {'input': 0.0025, 'output': 0.010},
                'gpt-4': {'input': 0.03, 'output': 0.06},
                'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
                'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
            },
            'anthropic': {
                'claude-3-opus': {'input': 0.015, 'output': 0.075},
                'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
                'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            },
            'google_genai': {
                'gemini-pro': {'input': 0.00025, 'output': 0.0005},
                'gemini-1.5-pro': {'input': 0.00125, 'output': 0.005},
            }
        }
        
        # Extract model name (remove provider prefix)
        model_clean = model.replace('openai:', '').replace('anthropic:', '').replace('google:', '')
        
        # Get pricing or default
        if provider in pricing_table and model_clean in pricing_table[provider]:
            return pricing_table[provider][model_clean]
        else:
            # Default fallback pricing
            return {'input': 0.001, 'output': 0.002}
    
    @classmethod
    def get_total_cost(cls, user_id: str = None, start_date: datetime = None, 
                       end_date: datetime = None) -> float:
        """Get total cost for a user or time period."""
        query = cls.objects
        
        if user_id:
            query = query.filter(user_id=user_id)
        if start_date:
            query = query.filter(created_at__gte=start_date)
        if end_date:
            query = query.filter(created_at__lte=end_date)
        
        # Sum up all costs
        total = sum(usage.total_cost for usage in query)
        return round(total, 4)
    
    @classmethod
    def get_usage_stats(cls, user_id: str = None, days: int = 30) -> dict:
        """Get usage statistics."""
        from datetime import timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        query = cls.objects.filter(created_at__gte=start_date)
        
        if user_id:
            query = query.filter(user_id=user_id)
        
        usages = list(query)
        
        if not usages:
            return {
                'total_requests': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
                'avg_cost_per_request': 0.0,
                'by_model': {},
                'by_provider': {}
            }
        
        # Calculate stats
        total_cost = sum(u.total_cost for u in usages)
        total_tokens = sum(u.total_tokens for u in usages)
        
        # Group by model
        by_model = {}
        for usage in usages:
            if usage.model not in by_model:
                by_model[usage.model] = {'requests': 0, 'tokens': 0, 'cost': 0.0}
            by_model[usage.model]['requests'] += 1
            by_model[usage.model]['tokens'] += usage.total_tokens
            by_model[usage.model]['cost'] += usage.total_cost
        
        # Group by provider
        by_provider = {}
        for usage in usages:
            if usage.provider not in by_provider:
                by_provider[usage.provider] = {'requests': 0, 'tokens': 0, 'cost': 0.0}
            by_provider[usage.provider]['requests'] += 1
            by_provider[usage.provider]['tokens'] += usage.total_tokens
            by_provider[usage.provider]['cost'] += usage.total_cost
        
        return {
            'total_requests': len(usages),
            'total_tokens': total_tokens,
            'total_cost': round(total_cost, 4),
            'avg_cost_per_request': round(total_cost / len(usages), 4),
            'by_model': by_model,
            'by_provider': by_provider,
            'period_days': days
        }

