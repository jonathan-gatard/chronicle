# Scribe Technical Documentation

## Overview
Scribe is a custom Home Assistant integration designed to offload historical data recording to a high-performance **TimescaleDB** (PostgreSQL) database. It runs alongside the default `recorder` but offers superior performance for long-term data storage and analysis thanks to TimescaleDB's hypertables and compression.

## Architecture

### Core Components
1.  **`__init__.py`**: The entry point.
    *   Sets up the integration.
    *   Initializes the `ScribeWriter` thread.
    *   Registers event listeners (`EVENT_STATE_CHANGED`, `EVENT_HOMEASSISTANT_STOP`).
    *   Handles the `scribe.flush` service.
    *   Forwards setup to `sensor` and `binary_sensor` platforms.
2.  **`writer.py` (`ScribeWriter`)**: The heart of the integration.
    *   Runs as a separate **Daemon Thread** to avoid blocking the main Home Assistant loop.
    *   **Queue System**: Events are added to a thread-safe list (`self._queue`) protected by a `threading.Lock`.
    *   **Batch Processing**: Data is flushed to the database in batches (default: 100 items) or periodically (default: 5 seconds).
    *   **Database Management**: Automatically handles table creation, hypertable conversion, and compression policy application on startup.
3.  **`config_flow.py`**: Handles UI configuration.
    *   Supports standard user flow and import from YAML.
    *   Validates database connections.
    *   **Auto-Creation**: Can automatically create the target database if it doesn't exist (requires `postgres` user privileges).
4.  **`sensor.py` & `binary_sensor.py`**: Monitoring.
    *   Exposes internal metrics: Events written, buffer size, write duration, database size, compression ratio.
    *   `binary_sensor` indicates connection status.

### Data Flow
1.  **Event Fired**: HA fires an event (e.g., `state_changed`).
2.  **Listener**: `handle_event` in `__init__.py` catches it.
3.  **Filtering**: Checks `include/exclude` domains/entities configuration.
4.  **Enqueue**: The event is processed into a dictionary and passed to `writer.enqueue()`.
5.  **Buffering**: The item is added to `self._queue`.
6.  **Flush Trigger**:
    *   **Size-based**: If queue length >= `batch_size`.
    *   **Time-based**: `run()` loop calls `_flush()` every `flush_interval` seconds.
7.  **Writing**:
    *   `_flush()` acquires the lock.
    *   Swaps the queue with an empty list (atomic-like operation).
    *   Opens a SQLAlchemy connection.
    *   Inserts data using `COPY` (via `psycopg2.extras.execute_values`) or batched `INSERT` for maximum speed.
    *   Commits the transaction.

## Database Schema

Scribe uses two main tables, optimized as TimescaleDB **Hypertables**:

### 1. `states`
Stores numeric and string state data.
*   `time` (TIMESTAMPTZ): Primary partitioning key.
*   `entity_id` (TEXT): The entity ID (e.g., `sensor.temperature`).
*   `state` (TEXT): The raw state string.
*   `value` (DOUBLE PRECISION): Parsed numeric value (for graphing).
*   `attributes` (JSONB): Full state attributes.

**Compression**:
*   Segment by: `entity_id`
*   Order by: `time DESC`
*   Policy: Default 60 days.

### 2. `events`
Stores generic Home Assistant events.
*   `time` (TIMESTAMPTZ): Primary partitioning key.
*   `event_type` (TEXT): e.g., `call_service`, `automation_triggered`.
*   `event_data` (JSONB): The event payload.
*   `origin`, `context_id`, etc.: Traceability data.

**Compression**:
*   Segment by: `event_type`
*   Order by: `time DESC`
*   Policy: Default 60 days.

## Configuration

Scribe supports both **YAML** and **UI (Config Flow)** configuration.

*   **YAML**: Best for static settings (Table names, Chunk intervals).
*   **UI**: Best for connection details and filtering options.
*   **Options Flow**: Allows changing filtering and statistics settings without restarting HA.

## Testing & CI

### Unit Tests (`tests/`)
We use `pytest` with `pytest-homeassistant-custom-component`.
*   **`test_config_flow.py`**: Mocks the config flow, verifying inputs and validation logic.
*   **`test_init.py`**: Tests component setup, ensuring the writer starts and stops correctly.
*   **`test_writer.py`**: Tests the `ScribeWriter` class in isolation, mocking the SQLAlchemy engine to verify queueing and flushing logic without a real DB.

### Continuous Integration (GitHub Actions)
Located in `.github/workflows/tests.yaml`.
*   Runs on every `push` and `pull_request`.
*   **Matrix**: Tests against Python 3.12 and 3.13.
*   **Steps**:
    1.  Checkout code.
    2.  Install dependencies (`pytest`, `sqlalchemy`, `psycopg2-binary`).
    3.  **Setup Environment**: Creates the `custom_components/scribe` directory structure required for tests to import the component correctly.
    4.  Run `pytest`.

## Deployment

### `deploy.sh`
A helper script for local development.
1.  **Sync**: Copies source files (`*.py`, `translations/`, `manifest.json`) to the Home Assistant `custom_components` directory.
2.  **Clean**: Removes unnecessary dev files (tests, cache) from the target.
3.  **Restart**: Restarts the Home Assistant container to apply changes.

---
*Generated by Antigravity*
