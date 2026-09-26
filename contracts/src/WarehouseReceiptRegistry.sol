// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/// @title WarehouseReceiptRegistry
/// @notice Lifecycle of digital warehouse receipts: one receipt per intake, status
///         changes restricted to the issuing warehouse. These are platform records,
///         NOT legal warehouse receipts under the regulated system.
///         ACTIVE -> PARTIALLY_RELEASED -> RELEASED; PLEDGED is reserved for future
///         warehouse-receipt financing.
contract WarehouseReceiptRegistry is AccessControl {
    bytes32 public constant ISSUER_WAREHOUSE = keccak256("ISSUER_WAREHOUSE");

    enum Status {
        NONE,
        ACTIVE,
        PARTIALLY_RELEASED,
        RELEASED,
        PLEDGED
    }

    struct Receipt {
        bytes32 dataHash;
        bytes32 owner; // pseudonymous farmer id hash, never a name
        address issuer;
        Status status;
        uint64 issuedAt;
        uint64 updatedAt;
    }

    mapping(bytes32 receiptId => Receipt) public receipts;

    event ReceiptIssued(bytes32 indexed receiptId, bytes32 dataHash, bytes32 owner, address issuer);
    event StatusChanged(bytes32 indexed receiptId, Status from, Status to, bytes32 eventHash);
    event OwnershipTransferred(bytes32 indexed receiptId, bytes32 from, bytes32 to);

    error NotIssuingWarehouse();
    error AlreadyIssued();
    error UnknownReceipt();
    error InvalidTransition(Status from, Status to);

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    function issue(bytes32 receiptId, bytes32 dataHash, bytes32 owner) external onlyRole(ISSUER_WAREHOUSE) {
        if (receipts[receiptId].status != Status.NONE) revert AlreadyIssued();
        uint64 ts = uint64(block.timestamp);
        receipts[receiptId] = Receipt(dataHash, owner, msg.sender, Status.ACTIVE, ts, ts);
        emit ReceiptIssued(receiptId, dataHash, owner, msg.sender);
    }

    function setStatus(bytes32 receiptId, Status to, bytes32 eventHash) external {
        Receipt storage r = _issuedBySender(receiptId);
        Status from = r.status;
        if (!_allowed(from, to)) revert InvalidTransition(from, to);
        r.status = to;
        r.updatedAt = uint64(block.timestamp);
        emit StatusChanged(receiptId, from, to, eventHash);
    }

    function transferOwnership(bytes32 receiptId, bytes32 newOwner) external {
        Receipt storage r = _issuedBySender(receiptId);
        if (r.status == Status.RELEASED || r.status == Status.PLEDGED) revert InvalidTransition(r.status, r.status);
        emit OwnershipTransferred(receiptId, r.owner, newOwner);
        r.owner = newOwner;
    }

    function _issuedBySender(bytes32 receiptId) private view returns (Receipt storage r) {
        r = receipts[receiptId];
        if (r.status == Status.NONE) revert UnknownReceipt();
        if (r.issuer != msg.sender || !hasRole(ISSUER_WAREHOUSE, msg.sender)) revert NotIssuingWarehouse();
    }

    function _allowed(Status from, Status to) private pure returns (bool) {
        if (from == Status.ACTIVE) return to == Status.PARTIALLY_RELEASED || to == Status.RELEASED || to == Status.PLEDGED;
        if (from == Status.PARTIALLY_RELEASED) return to == Status.PARTIALLY_RELEASED || to == Status.RELEASED;
        if (from == Status.PLEDGED) return to == Status.ACTIVE; // pledge released by the lender (future)
        return false;
    }
}
