"""Classify SDK failures without returning their body, URL or credentials."""


def provider_error_code(error):
    text = (type(error).__name__ + ' ' + str(error) + ' ' + str(getattr(error, 'body', ''))).lower()
    status = getattr(error, 'status_code', None)
    if any(term in text for term in ('insufficient_quota', 'credit balance', 'billing_hard_limit', 'quota exceeded',
                                           'credit_balance_exhausted', 'organization_spend_limit_exceeded',
                                           'project_spend_limit_exceeded', 'organization_usage_limit_exceeded')):
        return 'provider_quota_exceeded'
    if status == 429 or 'ratelimit' in text or 'rate_limit' in text:
        return 'provider_rate_limited'
    if status in (401, 403) or 'authentication' in text:
        return 'provider_auth_failed'
    if (isinstance(status, int) and status >= 500) or any(t in text for t in ('connection', 'timeout')):
        return 'provider_unavailable'
    return 'provider_request_rejected'


class ProviderGuard:
    """After one provider failure, subsequent graph retries cannot call it again."""
    def __init__(self, llm):
        self.llm = llm
        self.failure = None

    def __call__(self, *args, **kwargs):
        if self.failure:
            raise RuntimeError('provider_already_failed')
        try:
            return self.llm(*args, **kwargs)
        except Exception as error:
            self.failure = provider_error_code(error)
            raise RuntimeError('provider_call_failed') from None
