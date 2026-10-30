# Build brief: Crate Ledger

A small example brief to try the factory on. Copy it to
`docs/build-brief.md`, then run `/factory init` and `/factory plan`.

## 1. Problem

A beverage wholesaler delivers crates to kiosks and small shops and collects
empty crates and bottles on the next visit. Today drivers note returns on
paper, and nobody knows which customer is holding how many empties until the
year-end count. Deposit money goes missing.

## 2. Users

- **Driver**: records deliveries and returned empties at the customer, on a
  phone, often with poor signal.
- **Office**: sees each customer's balance and chases large ones.

## 3. Requirements

Each requirement has a stable ID. Specs, tests and commits refer to these.

| ID | Requirement |
| --- | --- |
| FR-CUS-01 | Office can create, edit and archive customers (name, address, route). |
| FR-DEL-01 | Driver records a delivery: customer, crate type, quantity full. |
| FR-RET-01 | Driver records returned empties: crate type, quantity. |
| FR-BAL-01 | Each customer has a live balance of crates out per crate type. |
| FR-BAL-02 | Office sees a list of customers sorted by deposit value outstanding. |
| FR-EXP-01 | Office exports balances as CSV. |
| NFR-OFF-01 | Driver screens keep working offline and sync when back online. |
| NFR-SEC-01 | Drivers see only their own route's customers. |
| NFR-UX-01 | Driver screens are usable with one thumb on a 360 px wide phone. |

## 4. Acceptance scenarios

1. A driver delivers 10 crates to a kiosk and collects 6 empties; the kiosk's
   balance goes up by 4.
2. A driver records a return while offline; it appears in the office view
   within a minute of the phone reconnecting.
3. A driver on route A cannot open a customer on route B.

## 5. Constraints

- Hosting: one small cloud VM or a free tier.
- Deposit values per crate type are set by the office.

## 6. Milestones

- **M0 Foundations**: customers, auth with routes, balances (FR-CUS, FR-BAL-01, NFR-SEC).
- **M1 Driver app**: delivery and return screens, offline sync (FR-DEL, FR-RET, NFR-OFF, NFR-UX).
- **M2 Office**: outstanding list and CSV export (FR-BAL-02, FR-EXP).
