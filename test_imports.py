#!/usr/bin/env python3
import sys
import os

root = os.path.dirname(__file__)
sys.path.insert(0, root)

print("Testing imports...")
print(f"Python path: {sys.path[:3]}")

try:
    import ml_service
    print(f"✓ ml_service found at: {ml_service.__file__ if hasattr(ml_service, '__file__') else 'package'}")
except Exception as e:
    print(f"✗ ml_service: {e}")

try:
    from ml_service.config import settings, RABBITMQ_URL, DATABASE_URL
    print("✓ ml_service.config")
    print(f"  RABBITMQ_URL: {RABBITMQ_URL}")
    print(f"  DATABASE_URL: {DATABASE_URL[:30]}...")
except Exception as e:
    print(f"✗ ml_service.config: {e}")

try:
    from ml_service.database import GenerationProgress, get_db_session
    print("✓ ml_service.database")
except Exception as e:
    print(f"✗ ml_service.database: {e}")

try:
    from ml_service.services.rabbitmq_service import get_rabbitmq_service
    print("✓ ml_service.services.rabbitmq_service")
except Exception as e:
    print(f"✗ ml_service.services.rabbitmq_service: {e}")

print("\nBackend service...")

try:
    from backend_service.config import settings, RABBITMQ_URL
    print("✓ backend_service.config")
    print(f"  RABBITMQ_URL: {RABBITMQ_URL}")
except Exception as e:
    print(f"✗ backend_service.config: {e}")

try:
    from backend_service.services.rabbitmq_service import get_rabbitmq_service
    print("✓ backend_service.services.rabbitmq_service")
except Exception as e:
    print(f"✗ backend_service.services.rabbitmq_service: {e}")

print("\nAll imports tested!")
