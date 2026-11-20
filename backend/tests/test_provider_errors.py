import pytest
from tripbuddy_backend.provider_errors import ProviderGuard,provider_error_code


@pytest.mark.parametrize('name,status,body,expected',[
 ('OpenAIRateLimitError',429,'rate limit','provider_rate_limited'),
 ('OpenAIRateLimitError',429,'credit_balance_exhausted','provider_quota_exceeded'),
 ('OpenAIRateLimitError',429,'organization_spend_limit_exceeded','provider_quota_exceeded'),
 ('OpenAIRateLimitError',429,'project_spend_limit_exceeded','provider_quota_exceeded'),
 ('OpenAIRateLimitError',429,'organization_usage_limit_exceeded','provider_quota_exceeded'),
 ('OpenAIRateLimitError',429,'insufficient_quota','provider_quota_exceeded'),
 ('AnthropicInvalidRequestError',400,'Your credit balance is too low','provider_quota_exceeded'),
 ('AuthenticationError',401,'private-secret','provider_auth_failed'),
 ('APIConnectionError',None,'private-secret','provider_unavailable'),
 ('ServerError',503,'private-secret','provider_unavailable'),
 ('InvalidRequestError',400,'private-secret','provider_request_rejected'),
])
def test_safe_classification(name,status,body,expected):
    error=type(name,(Exception,),{})(body)
    error.status_code=status
    assert provider_error_code(error)==expected
    assert 'private-secret' not in provider_error_code(error)


def test_failure_blocks_further_provider_calls():
    calls=[]
    def limited(*args):
        calls.append(1)
        raise type('OpenAIRateLimitError',(Exception,),{})('private-secret')
    guarded=ProviderGuard(limited)
    for _ in range(3):
        with pytest.raises(RuntimeError):guarded('sample')
    assert len(calls)==1
    assert guarded.failure=='provider_rate_limited'


def test_success_keeps_provider_output():
    guarded=ProviderGuard(lambda: {'ok':True})
    assert guarded()=={'ok':True}
    assert guarded.failure is None
