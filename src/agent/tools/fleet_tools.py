"""Agent tools for the managed rental fleet.

These wrap :mod:`shared.fleet` so the supervisor can, as a real re-plan action
when parts are back-ordered, reserve an actual vehicle from the insurer's managed
fleet for the claimant — then attach it to the claim as a ``RENTAL_PROVIDER``
party and proactively message the claimant with the real vehicle details.

Honest by design: if no vehicle is available, ``reserve_rental`` returns a
``reserved: false`` result with a reason instead of fabricating a car.
"""

from __future__ import annotations

from typing import Any, Optional

from shared.models import Channel, Party, PartyRole, PartyStatus
from shared import store
from shared import fleet
from channels.router import route_message


def _require(claim_id: str):
    claim = store.load(claim_id)
    if claim is None:
        raise KeyError(f"claim {claim_id} not found")
    return claim


def fleet_availability(vehicle_class: Optional[str] = None) -> dict[str, Any]:
    """List how many fleet vehicles are currently available (optionally by class)."""
    avail = fleet.available(vehicle_class)
    return {
        "vehicle_class": vehicle_class or "any",
        "available_count": len(avail),
        "vehicles": [
            {"vehicle_id": v.vehicle_id, "class": v.vehicle_class,
             "label": f"{v.year} {v.make} {v.model}", "location": v.location}
            for v in avail
        ],
    }


def reserve_rental(claim_id: str, vehicle_class: str = "intermediate",
                   claimant_contact: str = "", channel: str = "whatsapp") -> dict[str, Any]:
    """Reserve a REAL vehicle from the managed fleet for the claimant's claim.

    This is the concrete re-plan when the claimant is without a car (e.g. parts
    back-ordered). It atomically reserves an available vehicle of ``vehicle_class``
    (no double-booking), records it on the claim as a committed RENTAL_PROVIDER
    party, and messages the claimant the real vehicle + reservation reference.

    Returns ``reserved: false`` with a reason when the fleet has nothing free —
    the supervisor should then open a ticket / inform the claimant honestly,
    not invent a rental.
    """
    claim = _require(claim_id)

    try:
        vehicle = fleet.reserve(claim_id, vehicle_class)
    except fleet.FleetError as e:
        claim.log(f"rental re-plan: {e}")
        store.save(claim)
        return {"claim_id": claim_id, "reserved": False, "reason": str(e),
                "vehicle_class": vehicle_class}

    # Mark the vehicle on_rent now that it's assigned to the claimant.
    fleet.set_status(vehicle.vehicle_id, fleet.VehicleStatus.ON_RENT)

    label = f"{vehicle.year} {vehicle.make} {vehicle.model}"
    # Record the rental as a committed party on the claim.
    contact = claimant_contact or _claimant_contact(claim)
    ch = Channel(channel)
    claim.add_party(
        Party(
            role=PartyRole.RENTAL_PROVIDER,
            contact=contact or "fleet@insurer.example",
            preferred_channel=ch,
            required_for_commit=False,
            status=PartyStatus.COMMITTED,
            last_message=f"{label} · {vehicle.reservation_ref}",
        )
    )
    claim.facts["rental"] = {
        "vehicle_id": vehicle.vehicle_id,
        "label": label,
        "class": vehicle.vehicle_class,
        "vin": vehicle.vin,
        "plate": vehicle.plate,
        "location": vehicle.location,
        "ref": vehicle.reservation_ref,
        "source": "managed_fleet",
    }
    claim.log(f"rental reserved from managed fleet: {label} "
              f"({vehicle.vehicle_id}) ref {vehicle.reservation_ref}")
    store.save(claim)

    # Proactively inform the claimant with the real vehicle details.
    if contact:
        route_message(
            ch, contact,
            f"Good news — while your repair is underway we've reserved a courtesy "
            f"vehicle for you: {label} (class {vehicle.vehicle_class}), pickup at "
            f"{vehicle.location}. Reservation {vehicle.reservation_ref}. It's "
            f"covered under your policy.",
        )

    return {
        "claim_id": claim_id,
        "reserved": True,
        "vehicle_id": vehicle.vehicle_id,
        "vehicle": label,
        "vehicle_class": vehicle.vehicle_class,
        "plate": vehicle.plate,
        "location": vehicle.location,
        "reservation_ref": vehicle.reservation_ref,
    }


def return_rental(claim_id: str, vehicle_id: str) -> dict[str, Any]:
    """Return a rented vehicle to the fleet (end of rental) — frees it for reuse."""
    v = fleet.release(vehicle_id)
    if v is None:
        return {"claim_id": claim_id, "returned": False,
                "reason": f"vehicle {vehicle_id} not found"}
    claim = store.load(claim_id)
    if claim is not None:
        claim.log(f"rental returned to fleet: {vehicle_id}")
        store.save(claim)
    return {"claim_id": claim_id, "returned": True, "vehicle_id": vehicle_id,
            "status": v.status.value}


def _claimant_contact(claim) -> str:
    party = claim.parties.get(PartyRole.CLAIMANT.value)
    return party.contact if party else ""
