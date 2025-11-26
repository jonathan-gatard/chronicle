"""Test ScribeWriter."""
import time
from unittest.mock import MagicMock, patch
from custom_components.scribe.writer import ScribeWriter

def test_writer_enqueue_flush():
    """Test enqueue and flush logic."""
    hass = MagicMock()
    writer = ScribeWriter(
        hass=hass,
        db_url="postgresql://user:pass@host/db",
        chunk_interval="7 days",
        compress_after="60 days",
        record_states=True,
        record_events=True,
        batch_size=2,
        flush_interval=5,
        max_queue_size=10000,
        buffer_on_failure=True,
        table_name_states="states",
        table_name_events="events"
    )

    # Mock Engine
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    writer._engine = mock_engine

    # Enqueue items
    writer.enqueue({"type": "state", "data": 1})
    assert len(writer._queue) == 1
    
    # Enqueue second item (should trigger flush because batch_size=2)
    writer.enqueue({"type": "event", "data": 2})
    assert len(writer._queue) == 0 # Should be empty after flush

    # Verify DB calls
    assert mock_conn.execute.call_count >= 1
    
    # Verify stats
    assert writer._states_written == 1
    assert writer._events_written == 1

def test_writer_no_buffer_on_failure():
    """Test that events are dropped when buffering is disabled."""
    hass = MagicMock()
    writer = ScribeWriter(
        hass=hass,
        db_url="postgresql://user:pass@host/db",
        chunk_interval="7 days",
        compress_after="60 days",
        record_states=True,
        record_events=True,
        batch_size=1,
        flush_interval=5,
        max_queue_size=10000,
        buffer_on_failure=False,
        table_name_states="states",
        table_name_events="events"
    )

    # Mock Engine to fail
    writer._engine = None # Simulate no connection
    
    # Mock create_engine to fail
    with patch("custom_components.scribe.writer.create_engine", side_effect=Exception("Connection failed")):
        # Enqueue item
        writer.enqueue({"type": "state", "data": 1})
        
        # Should be empty because it tried to flush (batch_size=1), failed, and dropped it
        assert len(writer._queue) == 0
        assert writer._dropped_events == 1
