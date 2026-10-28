#!/usr/bin/env python3
"""Seed the managed rental fleet inventory (``coe-fleet``).

The supervisor's rental re-plan (``reserve_rental``) can only hand a claimant a
courtesy car if the fleet has vehicles in it. This script writes a small, varied
inventory so the re-plan works end to end — both offline (in-process store) and
live against DynamoDB.

Backend follows ``COE_STORE_BACKEND`` (``auto`` | ``dynamodb`` | ``memory``),
exactly like ``shared.fleet``:

  # Offline / unit-demo (no AWS): writes to the in-process store.
  COE_STORE_BACKEND=memory python3 scripts/seed_fleet.py

  # Live: writes to the coe-fleet DynamoDB table (requires the CDK stack).
  COE_STORE_BACKEND=dynamodb FLEET_TABLE_NAME=coe-fleet python3 scripts/seed_fleet.py

Idempotent: re-running overwrites the same ``vehicle_id`` records (available),
so it is safe to run repeatedly to reset the demo fleet.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make ``src/`` importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shared import fleet  # noqa: E402
from shared.fleet import RentalVehicle, VehicleStatus  # noqa: E402


# A compact, varied demo fleet. Classes line up with reserve_rental's default
# ("intermediate") plus common alternatives so the agent can always place a car.
SEED_VEHICLES: list[RentalVehicle] = [
    RentalVehicle("FLT-0001", "economy", "Toyota", "Corolla", 2024,
                  "1NXBR32E24Z000001", "RNT-001", "Downtown Depot"),
    RentalVehicle("FLT-0002", "economy", "Honda", "Civic", 2024,
                  "2HGFC2F50MH000002", "RNT-002", "Downtown Depot"),
    RentalVehicle("FLT-0003", "intermediate", "Toyota", "Camry", 2025,
                  "4T1BF1FK5CU000003", "RNT-003", "Airport Branch"),
    RentalVehicle("FLT-0004", "intermediate", "Hyundai", "Sonata", 2025,
                  "5NPE34AF4FH000004", "RNT-004", "Airport Branch"),
    RentalVehicle("FLT-0005", "intermediate", "Nissan", "Altima", 2024,
                  "1N4AL3AP7JC000005", "RNT-005", "Westside Lot"),
    RentalVehicle("FLT-0006", "suv", "Toyota", "RAV4", 2025,
                  "JTMRFREV7JD000006", "RNT-006", "Westside Lot"),
    RentalVehicle("FLT-0007", "suv", "Honda", "CR-V", 2024,
                  "7FARW2H53KE000007", "RNT-007", "Downtown Depot"),
    RentalVehicle("FLT-0008", "fullsize", "Chevrolet", "Impala", 2023,
                  "2G1WB5E37E1000008", "RNT-008", "Airport Branch"),
]


def main() -> int:
    backend = os.environ.get("COE_STORE_BACKEND", "auto")
    table = os.environ.get("FLEET_TABLE_NAME", "coe-fleet")
    print(f"==> Seeding fleet (backend={backend}, table={table})")

    for v in SEED_VEHICLES:
        # Reset to available so re-running restores a clean demo fleet.
        v.status = VehicleStatus.AVAILABLE
        v.claim_id = ""
        v.reservation_ref = ""
        fleet.put_vehicle(v)
        print(f"    {v.vehicle_id}  {v.year} {v.make} {v.model:10s} "
              f"[{v.vehicle_class}]  @ {v.location}")

    total = len(fleet.list_fleet())
    avail = len(fleet.available())
    print(f"==> Done. {len(SEED_VEHICLES)} vehicles seeded; "
          f"fleet now reports {total} total, {avail} available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
