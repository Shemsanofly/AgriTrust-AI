// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {EvidenceRegistry} from "../src/EvidenceRegistry.sol";
import {WarehouseReceiptRegistry} from "../src/WarehouseReceiptRegistry.sol";

/// forge script script/Deploy.s.sol --rpc-url $RPC_URL --private-key $ANCHOR_SIGNER_KEY --broadcast
contract Deploy is Script {
    function run() external {
        vm.startBroadcast();
        EvidenceRegistry evidence = new EvidenceRegistry(msg.sender);
        WarehouseReceiptRegistry receipts = new WarehouseReceiptRegistry(msg.sender);
        vm.stopBroadcast();
        console2.log("EVIDENCE_REGISTRY_ADDRESS=", address(evidence));
        console2.log("RECEIPT_REGISTRY_ADDRESS=", address(receipts));
    }
}
