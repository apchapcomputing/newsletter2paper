"""Test-wide setup.

Several services build a Supabase client when constructed. Point them at an
unroutable local address so no test can reach a real project by accident; tests
that need data must inject fakes.
"""
import os

os.environ["SUPABASE_URL"] = "http://127.0.0.1:9"
os.environ["SUPABASE_KEY"] = "test-key"
os.environ.setdefault("SUPABASE_DATABASE_URL", "sqlite://")
