from __future__ import annotations

from eval_bank_20260925.worldkit.families import (
    cascade, charge, deice, delivery, elevator, evac, gate, kitchen, line, oath, push, quay,
    repair, signal, tank, trip, ward, yard,
)

FAMILIES = {
    delivery.FAMILY.id: delivery.FAMILY,
    trip.FAMILY.id: trip.FAMILY,
    elevator.FAMILY.id: elevator.FAMILY,
    signal.FAMILY.id: signal.FAMILY,
    deice.FAMILY.id: deice.FAMILY,
    line.FAMILY.id: line.FAMILY,
    gate.FAMILY.id: gate.FAMILY,
    kitchen.FAMILY.id: kitchen.FAMILY,
    charge.FAMILY.id: charge.FAMILY,
    ward.FAMILY.id: ward.FAMILY,
    quay.FAMILY.id: quay.FAMILY,
    evac.FAMILY.id: evac.FAMILY,
    repair.FAMILY.id: repair.FAMILY,
    tank.FAMILY.id: tank.FAMILY,
    push.FAMILY.id: push.FAMILY,
    yard.FAMILY.id: yard.FAMILY,
    oath.FAMILY.id: oath.FAMILY,
    **cascade.FAMILIES,
}


def family_of(world: dict):
    return FAMILIES[world["family"]]
