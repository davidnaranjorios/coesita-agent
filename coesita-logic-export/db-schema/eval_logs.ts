import { pgTable, text, serial, real, integer, boolean, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const evalLogsTable = pgTable("eval_logs", {
  id: serial("id").primaryKey(),
  sessionId: text("session_id").notNull(),
  scenarioId: text("scenario_id").notNull(),
  domain: text("domain").notNull(),
  condition: text("condition").notNull(),
  scheduleCategory: text("schedule_category").notNull(),
  turn: integer("turn").notNull(),
  channels: text("channels"),
  nActiveChannels: integer("n_active_channels"),
  optimal: text("optimal").notNull(),
  decision: text("decision"),
  confidence: integer("confidence"),
  reason: text("reason"),
  reasonClass: text("reason_class"),
  isCorrect: boolean("is_correct"),
  rawResponse: text("raw_response"),
  rawPrompt: text("raw_prompt"),
  latencyMs: integer("latency_ms"),
  tokensIn: integer("tokens_in"),
  tokensOut: integer("tokens_out"),
  error: text("error"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const insertEvalLogSchema = createInsertSchema(evalLogsTable).omit({ id: true });
export type InsertEvalLog = z.infer<typeof insertEvalLogSchema>;
export type EvalLog = typeof evalLogsTable.$inferSelect;
