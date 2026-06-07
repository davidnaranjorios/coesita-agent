import { pgTable, text, serial, real, integer, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const sessionsTable = pgTable("sessions", {
  id: serial("id").primaryKey(),
  sessionId: text("session_id").notNull().unique(),
  modelId: text("model_id").notNull(),
  provider: text("provider").notNull(),
  baseUrl: text("base_url"),
  systemPrompt: text("system_prompt"),
  apiKeyHash: text("api_key_hash"),
  evalType: text("eval_type").notNull().default("demo"),
  status: text("status").notNull().default("pending"),
  nScenarios: integer("n_scenarios").notNull().default(30),
  progress: real("progress").notNull().default(0),
  currentScenario: integer("current_scenario").notNull().default(0),
  currentDomain: text("current_domain"),
  webhookUrl: text("webhook_url"),
  dis: real("dis"),
  composite: real("composite"),
  abi: real("abi"),
  archetype: text("archetype"),
  overallAccuracy: real("overall_accuracy"),
  apiCostUsd: real("api_cost_usd").notNull().default(0),
  startedAt: timestamp("started_at").notNull().defaultNow(),
  completedAt: timestamp("completed_at"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const insertSessionSchema = createInsertSchema(sessionsTable).omit({ id: true });
export type InsertSession = z.infer<typeof insertSessionSchema>;
export type Session = typeof sessionsTable.$inferSelect;
