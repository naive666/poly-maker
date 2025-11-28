// check_balances.js
const { ethers } = require("ethers");

// Polygon RPC
const provider = new ethers.providers.JsonRpcProvider("https://polygon-rpc.com");

// Your bot wallet – no need for PK, we only read
const WALLET = "0x8A348F2dE4f98382498De7b997924f3afbC45Be7";

// Contracts
const CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045";
const USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174";

// Minimal ABI for what we need
const ctfAbi = [
  "function getCollectionId(bytes32 parentCollectionId, bytes32 conditionId, uint256 indexSet) public pure returns (bytes32)",
  "function getPositionId(address collateralToken, bytes32 collectionId) public pure returns (uint256)",
  "function balanceOfBatch(address[] calldata accounts, uint256[] calldata ids) external view returns (uint256[] memory)"
];

const conditionId = "0x06c971ba7d236bef9eb8ece484f1bd47b0801520f3c7e15520edf5654273a8da";

async function main() {
  const ctf = new ethers.Contract(CTF, ctfAbi, provider);

  const parent = ethers.constants.HashZero;
  const idxYes = 1; // 0b01
  const idxNo  = 2; // 0b10

  const collYes = await ctf.getCollectionId(parent, conditionId, idxYes);
  const collNo  = await ctf.getCollectionId(parent, conditionId, idxNo);

  const posYes  = await ctf.getPositionId(USDC, collYes);
  const posNo   = await ctf.getPositionId(USDC, collNo);

  console.log("positionId YES:", posYes.toString());
  console.log("positionId NO :", posNo.toString());

  const [balYes, balNo] = await ctf.balanceOfBatch(
    [WALLET, WALLET],
    [posYes, posNo]
  );

  console.log("on-chain YES balance:", balYes.toString());
  console.log("on-chain NO  balance:", balNo.toString());

  const fullSets = balYes.lt(balNo) ? balYes : balNo;
  console.log("full sets you can merge:", fullSets.toString());
}

main().catch(console.error);
