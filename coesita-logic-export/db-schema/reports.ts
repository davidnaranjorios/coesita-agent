import { pgTable, text, serial, real, integer, timestamp, jsonb } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const reportsTable = pgTable("reports", {
  id: serial("id").primaryKey(),
  sessionId: text("session_id").notNull().unique(),
  modelId: text("model_id").notNull(),
  provider: text("provider").notNull(),

  // ── L1 Binary accuracy ──────────────────────────────────────────────────────
  stayAcc: real("stay_acc").notNull(),
  actAcc: real("act_acc").notNull(),
  dis: real("dis").notNull(),

  // ── ABI ─────────────────────────────────────────────────────────────────────
  abi: real("abi").notNull(),

  // ── Trajectory ───────────────────────────────────────────────────────────────
  pri: real("pri").notNull(),
  bp: integer("bp").notNull(),

  // ── Flip rates ───────────────────────────────────────────────────────────────
  frt: real("frt").notNull(),
  frErr: real("fr_err").notNull(),
  frRec: real("fr_rec").notNull(),

  // ── Conviction decay ─────────────────────────────────────────────────────────
  cdSlope: real("cd_slope").notNull(),
  cdDrop: real("cd_drop").notNull(),

  // ── Rationalization drift ────────────────────────────────────────────────────
  rdTotal: real("rd_total").notNull(),
  rdDiplo: real("rd_diplo").notNull(),
  rdPatho: real("rd_patho").notNull(),

  // ── Composite ────────────────────────────────────────────────────────────────
  composite: real("composite").notNull(),

  // ── Paper-aligned metrics (Naranjo, 2026) ────────────────────────────────────
  farpRate: real("farp_rate").notNull().default(0),
  inactionRate: real("inaction_rate").notNull().default(0),

  // ── FTM v10 extensions (Naranjo, 2026, FTM v2.2 paper v10) ───────────────────
  // Scalar variants for fast querying / dashboards
  farpStrict: real("farp_strict").default(0),
  farpInclusive: real("farp_inclusive").default(0),
  farpUnderPressure: real("farp_under_pressure").default(0),
  farpControl: real("farp_control").default(0),
  // Full v10 structured payload: btCohort, btPerScenario, parseFail,
  // farpByDomain, farpBySchedule, persistence, turnLevel, turnCountAvg,
  // bootstrap CIs, etc. See V10Metrics in eval-engine.ts.
  v10Metrics: jsonb("v10_metrics"),

  // ── Archetype ────────────────────────────────────────────────────────────────
  archetype: text("archetype").notNull(),
  archetypeRisk: text("archetype_risk").notNull(),
  archetypeDescription: text("archetype_description").notNull(),
  archetypeRecommendation: text("archetype_recommendation").notNull(),

  // ── JSON columns ─────────────────────────────────────────────────────────────
  stayAccByTurn: jsonb("stay_acc_by_turn").notNull(),
  stayAccBySchedule: jsonb("stay_acc_by_schedule").notNull(),
  domainScores: jsonb("domain_scores").notNull(),

  // ── Prompt optimization ──────────────────────────────────────────────────────
  originalPrompt: text("original_prompt"),
  optimizedPrompt: text("optimized_prompt").notNull(),
  promptImprovementComposite: real("prompt_improvement_composite").notNull(),

  // ── Business-facing fields ────────────────────────────────────────────────────
  farpIndex: real("farp_index"),
  systemPromptRecommendations: jsonb("system_prompt_recommendations").notNull().default([]),
  teaserExample: text("teaser_example"),

  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const insertReportSchema = createInsertSchema(reportsTable).omit({ id: true });
export type InsertReport = z.infer<typeof insertReportSchema>;
export type Report = typeof reportsTable.$inferSelect;
