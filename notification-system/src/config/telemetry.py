from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from prometheus_client import start_http_server
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_telemetry(app, service_name="notification-system"):
    """Initialize OpenTelemetry with traces and metrics"""
    
    # Create resource
    resource = Resource.create({"service.name": service_name})
    
    # Configure tracing
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    # OTLP exporter for traces
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4317",  # OTLP gRPC endpoint
    )
    
    # Add the OTLP exporter to the tracer provider
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # Configure metrics
    prometheus_reader = PrometheusMetricReader()
    metric_readers = [prometheus_reader]
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)
    
    # Start Prometheus HTTP server on a separate port
    # prometheus is scraping metrics from the otel collector a
    start_http_server(port=8001)  # Metrics endpoint
    
    # Main FastAPI app continues running on port 8000
    
    # Get meter and create metrics
    meter = metrics.get_meter(__name__)
    
    # Define metrics
    notification_counter = meter.create_counter(
        "notification_count",
        description="Number of notifications sent",
        unit="1"
    )
    
    notification_duration = meter.create_histogram(
        "notification_duration",
        description="Time taken to process notifications",
        unit="ms"
    )
    
    queue_depth = meter.create_up_down_counter(
        "queue_depth",
        description="Current depth of notification queues",
        unit="1"
    )
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    return {
        "notification_counter": notification_counter,
        "notification_duration": notification_duration,
        "queue_depth": queue_depth
    } 

# Add a new function for non-FastAPI services
def setup_service_telemetry(service_name: str):
    """Initialize OpenTelemetry for non-FastAPI services"""
    
    # Create resource
    resource = Resource.create({"service.name": service_name})
    
    # Configure tracing
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    # Configure metrics
    prometheus_reader = PrometheusMetricReader()
    metric_readers = [prometheus_reader]
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)
    
    # Get meter and create metrics
    meter = metrics.get_meter(__name__)
    
    # Define service-specific metrics
    return {
        "queue_depth": meter.create_up_down_counter(
            "queue_depth",
            description="Current depth of notification queues",
            unit="1"
        ),
        "message_processing_duration": meter.create_histogram(
            "message_processing_duration",
            description="Time taken to process messages",
            unit="ms"
        ),
        "processed_messages": meter.create_counter(
            "processed_messages",
            description="Number of messages processed",
            unit="1"
        ),
        "failed_messages": meter.create_counter(
            "failed_messages",
            description="Number of failed messages",
            unit="1"
        )
    } 