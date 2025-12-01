const { ethers } = require("ethers");

const provider = new ethers.providers.JsonRpcProvider("https://polygon-rpc.com");

const WALLET = "0xe6BDb76eC8c480d373eE8d7BB48B31849f6FC9Cb";  // proxyWallet from relayer log

const CTF  = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045";
const USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174";

const ctfAbi = [
  "function getCollectionId(bytes32 parentCollectionId, bytes32 conditionId, uint256 indexSet) public pure returns (bytes32)",
  "function getPositionId(address collateralToken, bytes32 collectionId) public pure returns (uint256)",
  "function balanceOfBatch(address[] calldata accounts, uint256[] calldata ids) external view returns (uint256[] memory)"
];

const conditionId = "0x540778bdfe7f6b780c2a161e998ce66e5a68c73c2314671e3836f4b4538385aa";

async function main() {
  console.log("Checking balances for wallet:", WALLET);
  console.log("Condition:", conditionId);

  const ctf = new ethers.Contract(CTF, ctfAbi, provider);

  const parent = ethers.constants.HashZero;
  const idxYes = 1; // YES
  const idxNo  = 2; // NO

  const collYes = await ctf.getCollectionId(parent, conditionId, idxYes);
  const collNo  = await ctf.getCollectionId(parent, conditionId, idxNo);

  const posYes  = await ctf.getPositionId(USDC, collYes);
  const posNo   = await ctf.getPositionId(USDC, collNo);

  const [balYes, balNo] = await ctf.balanceOfBatch(
    [WALLET, WALLET],
    [posYes, posNo]
  );

  console.log("YES balance:", balYes.toString());
  console.log("NO  balance:", balNo.toString());

  const fullSets = balYes.lt(balNo) ? balYes : balNo;
  console.log("full sets you can merge:", fullSets.toString());
}

main().catch(console.error);
