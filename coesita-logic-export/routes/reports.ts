import { Router, type IRouter } from "express";
import { db } from "@workspace/db";
import { reportsTable, evalLogsTable, usersTable } from "@workspace/db/schema";
import { eq } from "drizzle-orm";
import { GetReportParams, GetReportResponse } from "@workspace/api-zod";
import { logger } from "../lib/logger.js";

const router: IRouter = Router();

router.get("/:sessionId", async (req, res) => {
  try {
    const params = GetReportParams.parse(req.params);
    const [report] = await db
      .select()
      .from(reportsTable)
      .where(eq(reportsTable.sessionId, params.sessionId));

    if (!report) {
      return res.status(404).json({ error: "not_found", message: "Report not found" });
    }

    const response = GetReportResponse.parse({
      sessionId: report.sessionId,
      modelId: report.modelId,
      provider: report.provider,
      stayAcc: report.stayAcc,
      actAcc: report.actAcc,
      dis: report.dis,
      abi: report.abi,
      pri: report.pri,
      bp: report.bp,
      frt: report.frt,
      frErr: report.frErr,
      frRec: report.frRec,
      cdSlope: report.cdSlope,
      cdDrop: report.cdDrop,
      rdTotal: report.rdTotal,
      rdDiplo: report.rdDiplo,
      rdPatho: report.rdPatho,
      composite: report.composite,
      farpRate: report.farpRate ?? 0,
      inactionRate: report.inactionRate ?? 0,
      stayAccByTurn: report.stayAccByTurn,
      stayAccBySchedule: report.stayAccBySchedule,
      domainScores: report.domainScores,
      archetype: {
        name: report.archetype,
        risk: report.archetypeRisk,
        description: report.archetypeDescription,
        recommendation: report.archetypeRecommendation,
      },
      optimizedPrompt: report.optimizedPrompt,
      promptImprovementComposite: report.promptImprovementComposite,
      farpIndex: (report.farpIndex != null && report.farpIndex > 0)
        ? report.farpIndex
        : Math.round((1 - (report.composite as number)) * 100) / 10,
      systemPromptRecommendations: (report.systemPromptRecommendations as string[]) ?? [],
      teaserExample: report.teaserExample ?? undefined,
      createdAt: report.createdAt ?? undefined,
    });

    return res.json(response);
  } catch (err) {
    logger.error({ err }, "Failed to get report");
    return res.status(500).json({ error: "server_error", message: String(err) });
  }
});

// ── Admin-only: detailed eval logs per session ────────────────────────────────
router.get("/:sessionId/logs", async (req, res) => {
  try {
    // Only admins can access raw turn-by-turn logs
    if (!req.isAuthenticated()) {
      return res.status(401).json({ error: "unauthorized", message: "Authentication required." });
    }
    const userId = (req.user as { id: string }).id;
    const [user] = await db.select().from(usersTable).where(eq(usersTable.id, userId));
    if (!user?.isAdmin) {
      return res.status(403).json({ error: "forbidden", message: "Admin access required." });
    }

    const sessionId = req.params.sessionId;
    const logs = await db
      .select()
      .from(evalLogsTable)
      .where(eq(evalLogsTable.sessionId, sessionId))
      .orderBy(evalLogsTable.scenarioId, evalLogsTable.turn);

    return res.json({ logs });
  } catch (err) {
    logger.error({ err }, "Failed to get eval logs");
    return res.status(500).json({ error: "server_error", message: String(err) });
  }
});

export default router;
