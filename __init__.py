"""
Chronicle: A custom component to store Home Assistant history in TimescaleDB.
Inspired by LTSS.
"""
import logging
import threading
import time
import json
import psycopg2
from psycopg2.extras import execute_values
import voluptuous as vol

from homeassistant.const import (
    EVENT_STATE_CHANGED,
    EVENT_HOMEASSISTANT_STOP,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DB_NAME,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    CONF_ENTITIES,
    CONF_DOMAINS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.entityfilter import generate_filter

_LOGGER = logging.getLogger(__name__)

DOMAIN = "chronicle"

CONF_TABLE_NAME = "table_name"
DEFAULT_TABLE_NAME = "chronicle_events"
BATCH_SIZE = 100
FLUSH_INTERVAL = 5  # seconds

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PORT, default=5432): cv.port,
                vol.Optional(CONF_USERNAME, default="homeassistant"): cv.string,
                vol.Optional(CONF_DB_NAME, default="homeassistant"): cv.string,
                vol.Optional(CONF_TABLE_NAME, default=DEFAULT_TABLE_NAME): cv.string,
                vol.Optional(CONF_INCLUDE, default={}): vol.Schema(
                    {
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(CONF_ENTITIES, default=[]): vol.All(
                            cv.ensure_list, [cv.entity_id]
                        ),
                    }
                ),
                vol.Optional(CONF_EXCLUDE, default={}): vol.Schema(
                    {
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(CONF_ENTITIES, default=[]): vol.All(
                            cv.ensure_list, [cv.entity_id]
                        ),
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

def setup(hass: HomeAssistant, config: dict):
    """Set up the Chronicle component."""
    conf = config[DOMAIN]
    
    db_host = conf[CONF_HOST]
    db_port = conf[CONF_PORT]
    db_user = conf[CONF_USERNAME]
    db_pass = conf[CONF_PASSWORD]
    db_name = conf[CONF_DB_NAME]
    table_name = conf[CONF_TABLE_NAME]
    
    # Entity Filter
    include = conf.get(CONF_INCLUDE, {})
    exclude = conf.get(CONF_EXCLUDE, {})
    entity_filter = generate_filter(
        include.get(CONF_DOMAINS, []),
        include.get(CONF_ENTITIES, []),
        exclude.get(CONF_DOMAINS, []),
        exclude.get(CONF_ENTITIES, []),
    )

    # Initialize Data Handler
    handler = ChronicleHandler(
        hass, db_host, db_port, db_user, db_pass, db_name, table_name, entity_filter
    )
    
    # Start the handler
    handler.start()

    # Listen for state changes
    hass.bus.listen(EVENT_STATE_CHANGED, handler.event_listener)
    
    # Listen for HA stop to flush buffer
    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, handler.shutdown)

    return True

class ChronicleHandler(threading.Thread):
    """Handle database connections and writing."""

    def __init__(self, hass, host, port, user, password, dbname, table_name, entity_filter):
        """Initialize the handler."""
        threading.Thread.__init__(self)
        self.hass = hass
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.dbname = dbname
        self.table_name = table_name
        self.entity_filter = entity_filter
        
        self.queue = []
        self.lock = threading.Lock()
        self.running = True
        self.daemon = True # Daemon thread exits when main thread exits
        
        self._conn = None
        self._cursor = None

    def run(self):
        """Thread main loop."""
        self._connect()
        self._init_db()
        
        while self.running:
            time.sleep(FLUSH_INTERVAL)
            self._flush()

    def event_listener(self, event: Event):
        """Listen for new state change events."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if new_state is None:
            return

        if not self.entity_filter(entity_id):
            return

        # Prepare data
        try:
            state_val = float(new_state.state)
        except (ValueError, TypeError):
            # If state is not numeric, we can store it as NULL or skip it if we only want metrics
            # For Chronicle, let's store everything, but have a separate 'value' column for numbers
            state_val = None

        data = {
            "time": new_state.last_updated,
            "entity_id": entity_id,
            "state": new_state.state,
            "attributes": json.dumps(dict(new_state.attributes), default=str),
            "value": state_val,
        }

        with self.lock:
            self.queue.append(data)
            
        if len(self.queue) >= BATCH_SIZE:
            self._flush()

    def _connect(self):
        """Connect to the database."""
        try:
            self._conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                dbname=self.dbname
            )
            self._conn.autocommit = True
            self._cursor = self._conn.cursor()
            _LOGGER.info("Connected to TimescaleDB")
        except Exception as e:
            _LOGGER.error(f"Error connecting to database: {e}")

    def _init_db(self):
        """Initialize database table and hypertable."""
        if not self._cursor:
            return

        try:
            # Create Table
            self._cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    time TIMESTAMPTZ NOT NULL,
                    entity_id TEXT NOT NULL,
                    state TEXT,
                    attributes JSONB,
                    value DOUBLE PRECISION
                );
            """)
            
            # Convert to Hypertable (ignore if already exists)
            try:
                self._cursor.execute(f"SELECT create_hypertable('{self.table_name}', 'time', if_not_exists => TRUE);")
            except Exception:
                pass # Already a hypertable or error
                
            # Create Index on entity_id and time
            self._cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {self.table_name}_entity_time_idx 
                ON {self.table_name} (entity_id, time DESC);
            """)
            
        except Exception as e:
            _LOGGER.error(f"Error initializing database: {e}")

    def _flush(self):
        """Flush the queue to the database."""
        with self.lock:
            if not self.queue:
                return
            batch = list(self.queue)
            self.queue = []

        if not self._cursor:
            self._connect()
            if not self._cursor:
                # Still no connection, drop batch (or could retry/buffer more)
                _LOGGER.error("Database not connected, dropping batch")
                return

        try:
            sql = f"""
                INSERT INTO {self.table_name} (time, entity_id, state, attributes, value)
                VALUES %s
            """
            values = [
                (x['time'], x['entity_id'], x['state'], x['attributes'], x['value'])
                for x in batch
            ]
            
            execute_values(self._cursor, sql, values)
            
        except Exception as e:
            _LOGGER.error(f"Error inserting batch: {e}")
            # Try to reconnect
            self._connect()

    def shutdown(self, event):
        """Shutdown the handler."""
        self.running = False
        self._flush()
        if self._conn:
            self._conn.close()
