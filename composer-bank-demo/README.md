# Composer Bank Demo

Demo IBM WSBCC/Composer project with ten banking operations.

Structure:
- `dse.ini` maps Composer XML tags to Java classes.
- `formats/dseformat.xml` contains reusable request and response `fmtDef` entries.
- `contexts/dsecontext.xml` contains one operation context per operation.
- `operations/*.xml` contains one `CCDSEServerOperation` per file.
- `opSteps/*.xml` mirrors each operation's step definitions as reusable snippets.
- `src/main/java` contains Java classes in packages matching `implClass` and `dse.ini`.

Operations:
- `LastTransactionsOp`
- `GetCreditCardListOp`
- `GetCreditCardTransactionsOp`
- `ListLoansOp`
- `GetAccountBalanceOp`
- `TransferFundsOp`
- `PayBillOp`
- `GetStandingOrdersOp`
- `CreateLoanQuoteOp`
- `GetCustomerProfileOp`

