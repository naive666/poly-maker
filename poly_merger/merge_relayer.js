// merge_relayer.js
const { ethers } = require("ethers");
const { Interface } = require("ethers/lib/utils");
const { resolve } = require('path');
const { existsSync } = require('fs');
const {
  RelayClient,
  OperationType,
} = require("@polymarket/builder-relayer-client");
const {
  BuilderConfig,
  BuilderApiKeyCreds,
} = require("@polymarket/builder-signing-sdk");
// Load environment variables
const localEnvPath = resolve(__dirname, '.env');
const parentEnvPath = resolve(__dirname, '../.env');
const envPath = existsSync(localEnvPath) ? localEnvPath : parentEnvPath;
require('dotenv').config({ path: envPath })

async function main() {
  // --- 1) Env + basic wiring ---
  const relayerUrl = process.env.RELAYER_URL || "https://relayer-v2.polymarket.com/";
  const chainId = Number(process.env.CHAIN_ID || 137);

  const provider = new ethers.providers.JsonRpcProvider(
    process.env.RPC_URL || "https://polygon-rpc.com"
  );
  const pk = process.env.PK || process.env.PRIVATE_KEY;
  console.log("Loaded PK (first 10 chars):", (pk || "").slice(0, 10));
  const wallet = new ethers.Wallet(pk, provider);
  console.log("Owner EOA (signer):", wallet.address); // should be 0x8A34...

  // Builder credentials
  const builderCreds = /** @type {BuilderApiKeyCreds} */ ({
    key: process.env.BUILDER_API_KEY,
    secret: process.env.BUILDER_SECRET,
    passphrase: process.env.BUILDER_PASS_PHRASE,
  });

  const builderConfig = new BuilderConfig({
    localBuilderCreds: builderCreds,
  });

  // Relayer client
  const client = new RelayClient(relayerUrl, chainId, wallet, builderConfig);

  // --- 2) Read CLI args ---
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: node merge_relayer.js <amount> <conditionId> [isNegRisk]");
    process.exit(1);
  }

  const amountToMergeRaw = args[0];             // e.g. "1000000" (1 USDC)
  const conditionId = args[1];                  // full 0x... bytes32
  const isNegRisk = args[2] === "true";         // for later if you want adapter flow

  console.log("amountToMerge:", amountToMergeRaw);
  console.log("conditionId  :", conditionId);
  console.log("isNegRisk    :", isNegRisk);

  // --- 3) CTF mergePositions call data ---
  const ctfAddress = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"; // mainnet CTF :contentReference[oaicite:5]{index=5}
  const usdcAddress = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"; // Polygon USDC :contentReference[oaicite:6]{index=6}

  const parentCollectionId = ethers.constants.HashZero; // top-level condition
  const partition = [1, 2]; // YES + NO

  const ctfInterface = new Interface([
    "function mergePositions(address collateralToken, bytes32 parentCollectionId, bytes32 conditionId, uint[] partition, uint amount)",
  ]);

  const data = ctfInterface.encodeFunctionData("mergePositions", [
    usdcAddress,
    parentCollectionId,
    conditionId,
    partition,
    amountToMergeRaw,
  ]);

  /** @type {import("@polymarket/builder-relayer-client").SafeTransaction} */
  const mergeTx = {
    to: ctfAddress,
    operation: OperationType.Call,
    data,
    value: "0",
  };

  // --- 4) Execute via relayer (proxy wallet does the actual call) ---
  console.log("Submitting merge via relayer…");

  const response = await client.execute(
    [mergeTx],
    "Merge CTF positions"
  );

  const result = await response.wait();

  if (!result) {
    console.error("Relayer tx failed or timed out");
    return;
  }

  console.log("Relayer tx state:", result.state);
  console.log("On-chain tx hash:", result.transactionHash);
  console.log("Proxy wallet used:", result.proxyAddress); // should be your 0x94d3...

  console.log("Done.");
}

main().catch((err) => {
  console.error("Error merging via relayer:", err);
  process.exit(1);
});
