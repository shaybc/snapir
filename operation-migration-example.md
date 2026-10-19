# Operation migration order — example

Calls means calls to another operation. Formats, Java classes, and other technical dependencies are excluded.

## Relationship index

| Operation | Calls directly | Called by directly | Implementation wave |
|---|---|---|---|
| GetCustomer | None | ValidateTransfer, GetAccountSummary | 1 |
| ValidateTransfer | GetCustomer | TransferFunds | 2 |
| GetAccountSummary | GetCustomer | None | 2 |
| TransferFunds | ValidateTransfer | None | 3 |

## Wave 1 — Implement first

### GetCustomer

- **Calls:** None
- **Called by:** ValidateTransfer, GetAccountSummary
- **Required indirectly by:** TransferFunds
- **Ready to implement:** Yes.
- **Remove from Composer when:** Both Composer callers no longer need it and any direct incoming traffic has moved.

## Wave 2 — Implement after GetCustomer

These operations can be implemented in either order.

### ValidateTransfer

- **Calls:** GetCustomer
- **Called by:** TransferFunds
- **Ready to implement when:** Native GetCustomer is available.
- **Native behavior:** Calls native GetCustomer.
- **Remove from Composer when:** Composer's TransferFunds no longer needs it and any direct incoming traffic has moved.

### GetAccountSummary

- **Calls:** GetCustomer
- **Called by:** None
- **Ready to implement when:** Native GetCustomer is available.
- **Native behavior:** Calls native GetCustomer.
- **Remove from Composer when:** Its incoming traffic has moved.

## Wave 3 — Implement after ValidateTransfer

### TransferFunds

- **Calls:** ValidateTransfer
- **Indirectly requires:** GetCustomer
- **Called by:** None
- **Ready to implement when:** Native ValidateTransfer is available.
- **Native behavior:** Calls native ValidateTransfer, which calls native GetCustomer.
- **Remove from Composer when:** Its incoming traffic has moved.

## Implementation and retirement

Implement dependencies first: GetCustomer, then ValidateTransfer and GetAccountSummary, then TransferFunds.

Keep the old Composer implementations while they are needed. After moving TransferFunds traffic, Composer's TransferFunds and ValidateTransfer can retire if they have no other entry points. Composer's GetCustomer must stay until Composer's GetAccountSummary has also retired and no other entry points need it.

Implementation waves describe ordering, not microservice boundaries.
