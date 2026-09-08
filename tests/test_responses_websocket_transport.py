from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.providers.responses_websocket import (
    ResponsesWebSocketError,
    ResponsesWebSocketTransport,
    websocket_responses_endpoint,
)


class FakeSocket:
    def __init__(self, events):
        self.events=list(events); self.sent=[]; self.closed=False; self.timeouts=[]
    def settimeout(self, value): self.timeouts.append(value)
    def send(self, value): self.sent.append(json.loads(value))
    def recv(self):
        if not self.events: raise RuntimeError('no event')
        item=self.events.pop(0)
        if isinstance(item, BaseException): raise item
        return json.dumps(item)
    def close(self): self.closed=True


def completed(response_id='resp-1', call_id='call-1'):
    return {'type':'response.completed','response':{
        'id':response_id,'status':'completed','usage':None,'reasoning':{'context':'all_turns'},
        'output':[{'id':'fc-1','type':'function_call','status':'completed','call_id':call_id,'name':'read_file','arguments':'{"arguments":{"path":"/tmp/x"}}'}],
        'error':None,'incomplete_details':None,
    }}


def test_endpoint_uses_azure_v1_responses_socket():
    assert websocket_responses_endpoint('https://example.openai.azure.com/openai/v1/') == 'wss://example.openai.azure.com/openai/v1/responses'


def test_transport_preserves_request_and_strips_only_background():
    sock=FakeSocket([completed()])
    calls=[]
    def factory(*args,**kwargs): calls.append((args,kwargs)); return sock
    t=ResponsesWebSocketTransport(endpoint='https://example.test',api_key='secret',connection_factory=factory)
    req={'model':'luna','input':[{'role':'user','content':'x'}],'background':False,'store':True,'previous_response_id':'resp-0','tools':[{'type':'function','name':'read_file'}]}
    response=t.call(req)
    assert response.id=='resp-1' and response.output[0].call_id=='call-1'
    [sent]=sock.sent
    assert sent['type']=='response.create'
    assert 'background' not in sent
    assert sent['model']==req['model'] and sent['input']==req['input'] and sent['store'] is True
    assert sent['previous_response_id']=='resp-0' and sent['tools']==req['tools']
    assert calls[0][0][0]=='wss://example.test/openai/v1/responses'
    assert calls[0][1]['header']==['Authorization: Bearer secret']


def test_transport_reconnects_only_after_completed_turn_boundary():
    first=FakeSocket([completed('resp-1','call-1')])
    second=FakeSocket([completed('resp-2','call-2')])
    sockets=[first,second]; count=0
    def factory(*_a,**_k):
        nonlocal count
        item=sockets[count]; count+=1; return item
    t=ResponsesWebSocketTransport(endpoint='https://example.test',api_key='k',connection_factory=factory)
    assert t.call({'model':'luna','input':'a'}).id=='resp-1'
    assert first.closed
    assert t.call({'model':'luna','input':'b','previous_response_id':'resp-1'}).id=='resp-2'
    assert second.closed and count==2
    assert second.sent[0]['previous_response_id']=='resp-1'


def test_terminal_failure_closes_without_replaying_inflight_request():
    sock=FakeSocket([{'type':'error','error':{'message':'boom'}}])
    count=0
    def factory(*_a,**_k):
        nonlocal count; count+=1; return sock
    t=ResponsesWebSocketTransport(endpoint='https://example.test',api_key='k',connection_factory=factory)
    with pytest.raises(ResponsesWebSocketError,match='terminal failure'):
        t.call({'model':'luna','input':'a'})
    assert sock.closed and count==1
    # A failed in-flight turn is not replayed. A later caller may open a fresh
    # socket only as a new provider attempt under the outer zero-retry law.
    assert count==1



def test_terminal_server_error_is_explicitly_retry_safe():
    sock=FakeSocket([{'type':'error','error':{'type':'server_error','code':'server_error','message':'boom'}}])
    t=ResponsesWebSocketTransport(endpoint='https://example.test',api_key='k',connection_factory=lambda *_a,**_k:sock)
    with pytest.raises(ResponsesWebSocketError) as caught:
        t.call({'model':'luna','input':'a'})
    exc=caught.value
    assert exc.terminal is True
    assert exc.retry_safe is True
    assert exc.provider_error_code=='server_error'
    assert sock.closed


def test_ambiguous_receive_failure_is_not_retry_safe():
    sock=FakeSocket([RuntimeError('connection lost')])
    t=ResponsesWebSocketTransport(endpoint='https://example.test',api_key='k',connection_factory=lambda *_a,**_k:sock)
    with pytest.raises(ResponsesWebSocketError) as caught:
        t.call({'model':'luna','input':'a'})
    exc=caught.value
    assert exc.terminal is False
    assert exc.retry_safe is False
    assert exc.provider_error_code is None
    assert sock.closed

def test_cancellation_check_closes_after_dispatch_without_replay():
    class TickTimeout(Exception): pass
    sock=FakeSocket([TickTimeout('tick')])
    calls=0
    def check():
        nonlocal calls; calls+=1
        if calls>=3: raise RuntimeError('cancelled')
    t=ResponsesWebSocketTransport(endpoint='https://example.test',api_key='k',connection_factory=lambda *_a,**_k:sock)
    # Unknown timeout exception is transport-fatal; use the canonical class name dynamically.
    TickTimeout.__name__='WebSocketTimeoutException'
    with pytest.raises(RuntimeError,match='cancelled'):
        t.call({'model':'luna','input':'a'},cancellation_check=check)
    assert len(sock.sent)==1 and sock.closed


def test_callable_rejects_background_and_websocket_together():
    from aether.providers.azure_model import AzureModelCallable
    fake_client=SimpleNamespace(responses=SimpleNamespace())
    fake_ws=SimpleNamespace(close=lambda:None)
    with pytest.raises(ValueError,match='mutually exclusive'):
        AzureModelCallable(
            client=fake_client, websocket_transport=fake_ws,
            deployment='unit-test-luna', effort='low', role='solver',
            responses_background=True, responses_websocket=True,
            poll_interval_s=1.0,poll_timeout_s=30.0,max_retries=0,prompt_cache_mode='off',
        )


def test_transport_records_event_liveness_without_event_content():
    sock=FakeSocket([
        {'type':'response.created','response':{'id':'resp-1'}},
        {'type':'response.output_item.added','output_index':0,'item':{'type':'reasoning','secret':'must-not-persist'}},
        completed(),
    ])
    t=ResponsesWebSocketTransport(endpoint='https://example.test',api_key='k',connection_factory=lambda *_a,**_k:sock)
    assert t.call({'model':'luna','input':'a'}).id=='resp-1'
    obs=t.last_call_observability()
    assert obs['provider_websocket_event_count']==3
    assert obs['provider_websocket_event_type_counts']=={
        'response.completed':1,'response.created':1,'response.output_item.added':1,
    }
    assert obs['provider_websocket_first_event_elapsed_s'] is not None
    assert obs['provider_websocket_last_event_elapsed_s'] is not None
    assert 'secret' not in json.dumps(obs)
