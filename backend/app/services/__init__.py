"""
Service layer — business logic lives here.

Services orchestrate one or more repositories, apply business rules
(anomaly detection, atomic fault transitions, zone counting), and
are the only layer allowed to span multiple repository calls within
a single database transaction.

Controllers (API routers) call services; services call repositories.
Services must not import from app.api.
"""
