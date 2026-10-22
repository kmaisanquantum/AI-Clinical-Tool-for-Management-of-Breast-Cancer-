"""Seed synthetic demonstration data for local and preview environments (alias for seed_demo_data)."""

from apps.core.management.commands.seed_demo_data import Command as SeedDemoDataCommand


class Command(SeedDemoDataCommand):
    help = "Seed synthetic demonstration data idempotently."
