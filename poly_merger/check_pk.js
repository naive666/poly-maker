// check_pk.js
const { ethers } = require("ethers");

// paste the PK you got from "Export Private Key" here:
const pk = "0x4d99cd39ea4feb6b2885e50c6c0d0368017f9f2ff0b6c8660b7a200eca04f4ab";

const wallet = new ethers.Wallet(pk);
console.log("Address from this PK is:", wallet.address);
