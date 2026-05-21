"""
Repository layer — data access objects.

Each repository wraps a single ORM model and exposes typed async
CRUD methods. No business logic belongs here; repositories only
translate between the service layer and the database.

Pattern:
    Controller (API router)
        └─ Service (business logic, transaction boundary)
               └─ Repository (DB queries via SQLAlchemy async session)
"""
