from prometheus_client import Counter, Gauge

payments_submit_retries_total = Counter(
    "payments_submit_retries_total",
    "Total number of payment submit retries",
    ["reason"],
)

payments_submit_attempts_total = Counter(
    "payments_submit_attempts_total",
    "Total number of payment submit attempts",
)

payments_pending_intents = Gauge(
    "payments_pending_intents",
    "Current number of pending submit intents",
)

payments_processing_operations = Gauge(
    "payments_processing_operations",
    "Current number of processing operations",
)

payments_stale_intents_reset_total = Counter(
    "payments_stale_intents_reset_total",
    "Total number of stale intents reset",
)
