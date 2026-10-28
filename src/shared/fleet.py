"""Rental fleet management — real inventory, availability, and atomic reservation.

This is the insurer's **own managed loaner/rental fleet** (not a third-party
Enterprise/Hertz live feed, which is partner-gated and cannot be called from this
environment). Everything here is real state against a real datastore:

  * Inventory lives in DynamoDB (``coe-fleet``, partition key ``vehicle_id``).
  * ``reserve`` uses a DynamoDB **conditional update** so a vehicle can only be
    reserved when it is actually ``available`` — two concurrent claims can never
    double-book the same car (the second conditional write fails).
  * The lifecycle is available → reserved → on_rent → returned(available).

When parts are back-ordered the supervisor re-plans by reserving a real vehicle
from this fleet for the claimant. If no vehicle of the requested class is free,
we say so honestly rather than inventing one.

Mirrors ``shared/store.py``: DynamoDB in ``auto``/``dynamodb`` mode with a
per-process in-memory fallback so unit tests and offline runs work with no AWS.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

log = logging.getLogger(__name__)

_BACKEND = os.environ.get("COE_STORE_BACKEND", "auto").lower()
_MEM: dict[str, dict] = {}          # in-process fallback inventory
_ddb_ok: Optional[bool] = None


class VehicleStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    ON_RENT = "on_rent"


def _now() -> int:
    return int(time.time())


@dataclass
class RentalVehicle:
    """One vehicle in the managed rental fleet."""

    vehicle_id: str                 # partition key, e.g. "FLT-0001"
    vehicle_class: str              # economy | intermediate | suv | fullsize
    make: str
    model: str
    year: int
    vin: str
    plate: str
    location: str                   # depot / branch the car sits at
    status: VehicleStatus = VehicleStatus.AVAILABLE
    claim_id: str = ""              # set when reserved/on_rent
    reservation_ref: str = ""
    updated_at: int = field(default_factory=_now)

    def to_item(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "RentalVehicle":
        return cls(
            vehicle_id=item["vehicle_id"],
            vehicle_class=item["vehicle_class"],
            make=item["make"],
            model=item["model"],
            year=int(item["year"]),
            vin=item["vin"],
            plate=item["plate"],
            location=item["location"],
            status=VehicleStatus(item.get("status", VehicleStatus.AVAILABLE.value)),
            claim_id=item.get("claim_id", ""),
            reservation_ref=item.get("reservation_ref", ""),
            updated_at=int(item.get("updated_at", _now())),
        )


class FleetError(Exception):
    """Raised on reservation conflicts or when no vehicle is available."""


# --------------------------------------------------------------------------- #
# Backend selection (mirrors shared.store)
# --------------------------------------------------------------------------- #
def _table():
    import boto3

    ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return ddb.Table(os.environ.get("FLEET_TABLE_NAME", "coe-fleet"))


def _use_ddb() -> bool:
    global _ddb_ok
    if _BACKEND == "memory":
        return False
    if _BACKEND == "dynamodb":
        return True
    if _ddb_ok is None:
        _ddb_ok = True
    return _ddb_ok


# --------------------------------------------------------------------------- #
# Inventory operations
# --------------------------------------------------------------------------- #
def put_vehicle(v: RentalVehicle) -> None:
    """Insert/overwrite a vehicle (used by seeding and status updates)."""
    global _ddb_ok
    if _use_ddb():
        try:
            _table().put_item(Item=v.to_item())
            return
        except Exception as e:  # noqa: BLE001
            if _BACKEND == "dynamodb":
                raise
            log.warning("fleet put failed (%s); using in-process store", e)
            _ddb_ok = False
    _MEM[v.vehicle_id] = v.to_item()


def get_vehicle(vehicle_id: str) -> Optional[RentalVehicle]:
    global _ddb_ok
    if _use_ddb():
        try:
            item = _table().get_item(Key={"vehicle_id": vehicle_id}).get("Item")
            return RentalVehicle.from_item(item) if item else None
        except Exception as e:  # noqa: BLE001
            if _BACKEND == "dynamodb":
                raise
            log.warning("fleet get failed (%s); using in-process store", e)
            _ddb_ok = False
    item = _MEM.get(vehicle_id)
    return RentalVehicle.from_item(item) if item else None


def list_fleet() -> list[RentalVehicle]:
    global _ddb_ok
    if _use_ddb():
        try:
            resp = _table().scan()
            return [RentalVehicle.from_item(i) for i in resp.get("Items", [])]
        except Exception as e:  # noqa: BLE001
            if _BACKEND == "dynamodb":
                raise
            log.warning("fleet scan failed (%s); using in-process store", e)
            _ddb_ok = False
    return [RentalVehicle.from_item(i) for i in _MEM.values()]


def available(vehicle_class: Optional[str] = None) -> list[RentalVehicle]:
    """Vehicles currently AVAILABLE, optionally filtered by class."""
    out = [v for v in list_fleet() if v.status == VehicleStatus.AVAILABLE]
    if vehicle_class:
        out = [v for v in out if v.vehicle_class == vehicle_class.lower()]
    return sorted(out, key=lambda v: v.vehicle_id)


def _reservation_ref(vehicle_id: str) -> str:
    return f"RNT-{vehicle_id.split('-')[-1]}-{_now() % 100000:05d}"


def reserve(claim_id: str, vehicle_class: Optional[str] = None) -> RentalVehicle:
    """Atomically reserve the first AVAILABLE vehicle of the class for a claim.

    Raises :class:`FleetError` if no vehicle is available, or if every candidate
    was taken by a concurrent reservation (the conditional write fails,
    guaranteeing no double-booking).
    """
    candidates = available(vehicle_class)
    if not candidates:
        where = f" in class '{vehicle_class}'" if vehicle_class else ""
        raise FleetError(f"no rental vehicle available{where}")

    for v in candidates:
        ref = _reservation_ref(v.vehicle_id)
        if _reserve_one(v.vehicle_id, claim_id, ref):
            v.status = VehicleStatus.RESERVED
            v.claim_id = claim_id
            v.reservation_ref = ref
            v.updated_at = _now()
            return v
    # Every candidate was taken between read and write — surface honestly.
    raise FleetError("rental vehicles were just taken by another reservation")


def _reserve_one(vehicle_id: str, claim_id: str, ref: str) -> bool:
    """Conditional reserve of a single vehicle. Returns False on conflict."""
    global _ddb_ok
    if _use_ddb():
        try:
            _table().update_item(
                Key={"vehicle_id": vehicle_id},
                UpdateExpression=(
                    "SET #s = :reserved, claim_id = :c, reservation_ref = :r, "
                    "updated_at = :t"
                ),
                ConditionExpression="#s = :available",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":reserved": VehicleStatus.RESERVED.value,
                    ":available": VehicleStatus.AVAILABLE.value,
                    ":c": claim_id,
                    ":r": ref,
                    ":t": _now(),
                },
            )
            return True
        except Exception as e:  # noqa: BLE001
            if e.__class__.__name__ == "ConditionalCheckFailedException":
                return False  # taken concurrently — a conflict, not an error
            if _BACKEND == "dynamodb":
                raise
            log.warning("fleet reserve failed (%s); using in-process store", e)
            _ddb_ok = False
    # In-memory conditional reserve.
    item = _MEM.get(vehicle_id)
    if not item or item.get("status") != VehicleStatus.AVAILABLE.value:
        return False
    item.update(
        status=VehicleStatus.RESERVED.value,
        claim_id=claim_id,
        reservation_ref=ref,
        updated_at=_now(),
    )
    return True


def set_status(vehicle_id: str, status: VehicleStatus) -> Optional[RentalVehicle]:
    """Advance a reserved vehicle to ON_RENT, or release it back to AVAILABLE."""
    v = get_vehicle(vehicle_id)
    if not v:
        return None
    v.status = status
    if status == VehicleStatus.AVAILABLE:
        v.claim_id = ""
        v.reservation_ref = ""
    v.updated_at = _now()
    put_vehicle(v)
    return v


def release(vehicle_id: str) -> Optional[RentalVehicle]:
    """Return a vehicle to the fleet (end of rental)."""
    return set_status(vehicle_id, VehicleStatus.AVAILABLE)
