

def test_empty_history_query_is_a_deterministic_recent_receipt_index() -> None:
    from aether.history_query import query_history
    from aether.ledger import Receipt
    rows=[
        Receipt(receipt_id='r1',step=1,kind='read_file',success=True,summary='older'),
        Receipt(receipt_id='r2',step=2,kind='run_command',success=True,summary='newer'),
    ]
    result=query_history(rows,'')
    assert result['empty_query_lists_recent_receipts'] is True
    assert result['semantic_ranking'] is False
    assert [row['receipt_id'] for row in result['results']] == ['r2','r1']
