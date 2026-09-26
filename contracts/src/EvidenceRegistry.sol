// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/// @title EvidenceRegistry
/// @notice Append-only registry of salted record hashes (batches, receipts, storage
///         summaries, sales). Only hashes and pseudonymous IDs are stored: never
///         personal, financial or biometric data. A proof shows a record has not
///         changed since it was anchored; it does not show the data was true.
contract EvidenceRegistry is AccessControl {
    bytes32 public constant ISSUER_PLATFORM = keccak256("ISSUER_PLATFORM");
    bytes32 public constant ISSUER_WAREHOUSE = keccak256("ISSUER_WAREHOUSE");

    struct Proof {
        bytes32 dataHash;
        address issuer;
        uint64 timestamp;
        uint8 recordType;
    }

    mapping(bytes32 recordId => Proof) private proofs;

    event Anchored(bytes32 indexed recordId, uint8 recordType, bytes32 dataHash, address issuer, uint64 timestamp);

    error NotIssuer();
    error AlreadyAnchored(bytes32 recordId);
    error EmptyHash();

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ISSUER_PLATFORM, admin);
    }

    /// @param recordId keccak256("<TYPE>:<public id>"), e.g. keccak256("BATCH:BATCH-7F3A")
    /// @param recordType 1 batch, 2 receipt, 3 storage, 4 sale, 5 receipt status event
    function anchor(bytes32 recordId, uint8 recordType, bytes32 dataHash) external {
        if (!hasRole(ISSUER_PLATFORM, msg.sender) && !hasRole(ISSUER_WAREHOUSE, msg.sender)) revert NotIssuer();
        if (dataHash == bytes32(0)) revert EmptyHash();
        if (proofs[recordId].timestamp != 0) revert AlreadyAnchored(recordId);
        uint64 ts = uint64(block.timestamp);
        proofs[recordId] = Proof(dataHash, msg.sender, ts, recordType);
        emit Anchored(recordId, recordType, dataHash, msg.sender, ts);
    }

    function getProof(bytes32 recordId) external view returns (bytes32 dataHash, address issuer, uint64 timestamp) {
        Proof memory p = proofs[recordId];
        return (p.dataHash, p.issuer, p.timestamp);
    }

    function verify(bytes32 recordId, bytes32 dataHash) external view returns (bool) {
        Proof memory p = proofs[recordId];
        return p.timestamp != 0 && p.dataHash == dataHash;
    }
}
