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

def test_writer_buffer_on_failure():
    """Test that events are buffered when buffering is enabled."""
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
        buffer_on_failure=True,
        table_name_states="states",
        table_name_events="events"
    )

    # Mock Engine to fail
    writer._engine = None # Simulate no connection
    
    with patch("custom_components.scribe.writer.create_engine", side_effect=Exception("Connection failed")):
        # Enqueue item
        writer.enqueue({"type": "state", "data": 1})
        
        # Should NOT be empty because it tried to flush, failed, and put it back
        assert len(writer._queue) == 1
        assert writer._queue[0]["data"] == 1

def test_writer_max_queue_size():
    """Test that events are dropped when queue is full."""
    hass = MagicMock()
    writer = ScribeWriter(
        hass=hass,
        db_url="postgresql://user:pass@host/db",
        chunk_interval="7 days",
        compress_after="60 days",
        record_states=True,
        record_events=True,
        batch_size=100, # Large batch size so it doesn't flush immediately
        flush_interval=5,
        max_queue_size=2, # Small max size
        buffer_on_failure=True,
        table_name_states="states",
        table_name_events="events"
    )

    # Fill queue
    writer.enqueue({"type": "state", "data": 1})
    writer.enqueue({"type": "state", "data": 2})
    assert len(writer._queue) == 2
    
    # Add one more, should be dropped
    writer.enqueue({"type": "state", "data": 3})
    assert len(writer._queue) == 2
    assert writer._dropped_events == 1
