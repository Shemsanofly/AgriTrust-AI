// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {EvidenceRegistry} from "../src/EvidenceRegistry.sol";
import {WarehouseReceiptRegistry} from "../src/WarehouseReceiptRegistry.sol";

contract EvidenceRegistryTest is Test {
    EvidenceRegistry registry;
    address platform = address(this);
    address stranger = address(0xBEEF);
    bytes32 constant ID = keccak256("BATCH:BATCH-7F3A");
    bytes32 constant HASH = keccak256("canonical-json||salt");

    function setUp() public {
        registry = new EvidenceRegistry(platform);
    }

    function test_AnchorAndVerify() public {
        registry.anchor(ID, 1, HASH);
        (bytes32 h, address issuer, uint64 ts) = registry.getProof(ID);
        assertEq(h, HASH);
        assertEq(issuer, platform);
        assertGt(ts, 0);
        assertTrue(registry.verify(ID, HASH));
        assertFalse(registry.verify(ID, keccak256("tampered")));
    }

    function test_RecordsAreAppendOnly() public {
        registry.anchor(ID, 1, HASH);
        vm.expectRevert(abi.encodeWithSelector(EvidenceRegistry.AlreadyAnchored.selector, ID));
        registry.anchor(ID, 1, keccak256("new value"));
    }

    function test_OnlyIssuersCanAnchor() public {
        vm.prank(stranger);
        vm.expectRevert(EvidenceRegistry.NotIssuer.selector);
        registry.anchor(ID, 1, HASH);
    }

    function test_UnknownRecordIsNotVerified() public view {
        (, , uint64 ts) = registry.getProof(ID);
        assertEq(ts, 0);
        assertFalse(registry.verify(ID, HASH));
    }
}

contract WarehouseReceiptRegistryTest is Test {
    WarehouseReceiptRegistry registry;
    address warehouse = address(0xA11CE);
    address otherWarehouse = address(0xB0B);
    bytes32 constant RID = keccak256("RECEIPT:WR-2026-000123");

    function setUp() public {
        registry = new WarehouseReceiptRegistry(address(this));
        registry.grantRole(registry.ISSUER_WAREHOUSE(), warehouse);
        registry.grantRole(registry.ISSUER_WAREHOUSE(), otherWarehouse);
        vm.prank(warehouse);
        registry.issue(RID, keccak256("receipt"), keccak256("FMR-0042"));
    }

    function test_Lifecycle() public {
        vm.startPrank(warehouse);
        registry.setStatus(RID, WarehouseReceiptRegistry.Status.PARTIALLY_RELEASED, keccak256("e1"));
        registry.setStatus(RID, WarehouseReceiptRegistry.Status.RELEASED, keccak256("e2"));
        vm.expectRevert();
        registry.setStatus(RID, WarehouseReceiptRegistry.Status.ACTIVE, keccak256("e3"));
        vm.stopPrank();
    }

    function test_OnlyIssuingWarehouseChangesStatus() public {
        vm.prank(otherWarehouse);
        vm.expectRevert(WarehouseReceiptRegistry.NotIssuingWarehouse.selector);
        registry.setStatus(RID, WarehouseReceiptRegistry.Status.RELEASED, bytes32(0));
    }
}
