import { createEarthLaunchTrackerRuntime } from "../src/earth-launch-tracker/bootstrap.mjs";
import { sendNodeResponse, toWebRequest } from "../src/earth-launch-tracker/node-adapter.mjs";

const runtime = createEarthLaunchTrackerRuntime();

export default async function handler(req, res) {
  try {
    const response = await runtime.app(await toWebRequest(req));
    await sendNodeResponse(res, response);
  } catch (error) {
    const statusCode = Number(error?.statusCode) || 500;
    res.writeHead(statusCode, {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    });
    res.end(`${JSON.stringify({ error: error?.message || "Unexpected server error." }, null, 2)}\n`);
  }
}
