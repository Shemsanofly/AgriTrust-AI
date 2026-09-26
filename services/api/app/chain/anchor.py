"""Anchor record hashes on an EVM chain (EvidenceRegistry) or, when no chain is configured,
on a local append-only ledger. The local ledger is labelled SIMULATED everywhere."""

import logging
import time
from dataclasses import dataclass

from sqlmodel import Session, select

from ..config import get_settings
from ..models import BlockchainProof, LedgerEntry
from .hashing import keccak256, record_key

log = logging.getLogger(__name__)

RECORD_TYPES = {"BATCH": 1, "RECEIPT": 2, "STORAGE": 3, "SALE": 4, "RECEIPT_STATUS": 5}
PLATFORM_ISSUER = "ISSUER_PLATFORM"

EVIDENCE_REGISTRY_ABI = [
    {
        "type": "function",
        "name": "anchor",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "recordId", "type": "bytes32"},
            {"name": "recordType", "type": "uint8"},
            {"name": "dataHash", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "type": "function",
        "name": "getProof",
        "stateMutability": "view",
        "inputs": [{"name": "recordId", "type": "bytes32"}],
        "outputs": [
            {"name": "dataHash", "type": "bytes32"},
            {"name": "issuer", "type": "address"},
            {"name": "timestamp", "type": "uint64"},
        ],
    },
]


@dataclass
class OnChainProof:
    data_hash: str
    issuer: str
    timestamp: int


def _web3_contract():
    s = get_settings()
    if not (s.rpc_url and s.evidence_registry_address and s.anchor_signer_key):
        return None
    try:
        from web3 import Web3
    except ImportError:  # pragma: no cover
        return None
    w3 = Web3(Web3.HTTPProvider(s.rpc_url, request_kwargs={"timeout": 10}))
    if not w3.is_connected():
        log.warning("RPC %s unreachable; falling back to the simulated ledger", s.rpc_url)
        return None
    contract = w3.eth.contract(address=Web3.to_checksum_address(s.evidence_registry_address), abi=EVIDENCE_REGISTRY_ABI)
    return w3, contract


def chain_mode() -> str:
    return "ONCHAIN" if _web3_contract() else "SIMULATED"


def anchor(session: Session, entity_type: str, entity_id: str, data_hash: str) -> BlockchainProof:
    key = record_key(entity_type, entity_id)
    existing = session.exec(select(BlockchainProof).where(BlockchainProof.record_key == key)).first()
    if existing:
        return existing
    settings = get_settings()
    web3 = _web3_contract()
    if web3:
        w3, contract = web3
        account = w3.eth.account.from_key(settings.anchor_signer_key)
        tx = contract.functions.anchor(bytes.fromhex(key[2:]), RECORD_TYPES[entity_type], bytes.fromhex(data_hash[2:]))
        built = tx.build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": settings.chain_id,
            }
        )
        signed = account.sign_transaction(built)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        proof = BlockchainProof(
            entity_type=entity_type,
            entity_id=entity_id,
            record_key=key,
            data_hash=data_hash,
            chain_id=settings.chain_id,
            tx_hash=w3.to_hex(receipt.transactionHash),
            block_number=receipt.blockNumber,
            issuer=account.address,
            mode="ONCHAIN",
        )
    else:
        last = session.exec(select(LedgerEntry).order_by(LedgerEntry.id.desc())).first()  # type: ignore[union-attr]
        prev_tx = last.tx_hash if last else "0x" + "00" * 32
        block_number = (last.block_number + 1) if last else 1
        tx_hash = "0x" + keccak256(bytes.fromhex(prev_tx[2:]) + bytes.fromhex(key[2:]) + bytes.fromhex(data_hash[2:])).hex()
        session.add(
            LedgerEntry(
                record_key=key,
                record_type=RECORD_TYPES[entity_type],
                data_hash=data_hash,
                issuer=PLATFORM_ISSUER,
                timestamp=int(time.time()),
                block_number=block_number,
                tx_hash=tx_hash,
                prev_tx_hash=prev_tx,
            )
        )
        proof = BlockchainProof(
            entity_type=entity_type,
            entity_id=entity_id,
            record_key=key,
            data_hash=data_hash,
            chain_id=0,
            tx_hash=tx_hash,
            block_number=block_number,
            issuer=PLATFORM_ISSUER,
            mode="SIMULATED",
        )
    session.add(proof)
    session.flush()
    return proof


def read_proof(session: Session, proof: BlockchainProof) -> OnChainProof | None:
    """Read the hash back from where it was anchored (never from BlockchainProof itself)."""
    if proof.mode == "ONCHAIN":
        web3 = _web3_contract()
        if not web3:
            return None
        _, contract = web3
        data_hash, issuer, ts = contract.functions.getProof(bytes.fromhex(proof.record_key[2:])).call()
        if int(ts) == 0:
            return None
        return OnChainProof("0x" + bytes(data_hash).hex(), issuer, int(ts))
    entry = session.exec(select(LedgerEntry).where(LedgerEntry.record_key == proof.record_key)).first()
    if not entry:
        return None
    return OnChainProof(entry.data_hash, entry.issuer, entry.timestamp)


def verify_ledger_chain(session: Session) -> bool:
    """Check the simulated ledger's hash chain has not been rewritten."""
    prev = "0x" + "00" * 32
    for entry in session.exec(select(LedgerEntry).order_by(LedgerEntry.id)):  # type: ignore[arg-type]
        expected = "0x" + keccak256(
            bytes.fromhex(prev[2:]) + bytes.fromhex(entry.record_key[2:]) + bytes.fromhex(entry.data_hash[2:])
        ).hex()
        if entry.prev_tx_hash != prev or entry.tx_hash != expected:
            return False
        prev = entry.tx_hash
    return True
