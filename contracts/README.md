# Contracts

Foundry project with the two MVP contracts (README §9):

- `EvidenceRegistry`: append-only `recordId → (dataHash, issuer, timestamp)`. The API anchors batches, receipts, storage summaries and sales here.
- `WarehouseReceiptRegistry`: receipt lifecycle `ACTIVE → PARTIALLY_RELEASED → RELEASED` (`PLEDGED` reserved), changeable only by the issuing warehouse.

```bash
forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts --no-git
forge build && forge test
anvil &   # local chain
forge script script/Deploy.s.sol --rpc-url $RPC_URL --private-key $ANCHOR_SIGNER_KEY --broadcast
```

Put the printed `EVIDENCE_REGISTRY_ADDRESS` in `.env` and set `RPC_URL` + `ANCHOR_SIGNER_KEY`; the API then anchors on chain (`mode: ONCHAIN`). Without them it uses a local append-only ledger labelled `SIMULATED`.
