import { Router, type IRouter } from "express";
import { db } from "@workspace/db";
import { sessionsTable } from "@workspace/db/schema";
import { ListSessionsResponse } from "@workspace/api-zod";
import { logger } from "../lib/logger.js";
import { desc } from "drizzle-orm";

const router: IRouter = Router();

router.get("/", async (_req, res) => {
  try {
    const sessions = await db
      .select({
        sessionId: sessionsTable.sessionId,
        modelId: sessionsTable.modelId,
        provider: sessionsTable.provider,
        evalType: sessionsTable.evalType,
        status: sessionsTable.status,
        dis: sessionsTable.dis,
        composite: sessionsTable.composite,
        abi: sessionsTable.abi,
        archetype: sessionsTable.archetype,
        createdAt: sessionsTable.createdAt,
      })
      .from(sessionsTable)
      .orderBy(desc(sessionsTable.createdAt));

    const response = ListSessionsResponse.parse(
      sessions.map((s) => ({
        sessionId: s.sessionId,
        modelId: s.modelId,
        provider: s.provider,
        evalType: s.evalType,
        status: s.status,
        dis: s.dis ?? undefined,
        composite: s.composite ?? undefined,
        abi: s.abi ?? undefined,
        archetype: s.archetype ?? undefined,
        createdAt: s.createdAt,
      }))
    );

    return res.json(response);
  } catch (err) {
    logger.error({ err }, "Failed to list sessions");
    return res.status(500).json({ error: "server_error", message: String(err) });
  }
});

export default router;
