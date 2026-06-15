import { config as loadEnv } from "dotenv";
import { resolve } from "path";
loadEnv({ path: resolve(process.cwd(), ".env") });
loadEnv({ path: resolve(process.cwd(), "voice_agent/.env") });

function required(key: string): string {
  const val = process.env[key];
  if (!val) throw new Error(`Missing required env var: ${key}`);
  return val;
}

const resolvedPublicUrl =
  process.env.PUBLIC_URL ??
  (process.env.RAILWAY_PUBLIC_DOMAIN ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}` : "");

export const config = {
  PORT: parseInt(process.env.PORT ?? "3001"),
  NODE_ENV: process.env.NODE_ENV ?? "development",

  // Twilio (optional at startup — required for live calls)
  TWILIO_ACCOUNT_SID: process.env.TWILIO_ACCOUNT_SID ?? "",
  TWILIO_AUTH_TOKEN: process.env.TWILIO_AUTH_TOKEN ?? "",
  TWILIO_PHONE_NUMBER: process.env.TWILIO_PHONE_NUMBER ?? "",
  TWILIO_PHONE_NUMBER_SID: process.env.TWILIO_PHONE_NUMBER_SID ?? "",
  PUBLIC_URL: resolvedPublicUrl,

  // LLM provider
  VOICE_PROVIDER: (process.env.VOICE_PROVIDER ?? "gemini") as "gemini",
  GEMINI_API_KEY: required("GEMINI_API_KEY"),
  GEMINI_MODEL: process.env.GEMINI_MODEL ?? "gemini-3.1-flash-live-preview",
  GEMINI_VOICE: process.env.GEMINI_VOICE ?? "Aoede",

  // VAD
  GEMINI_VAD_START_SENSITIVITY: process.env.GEMINI_VAD_START_SENSITIVITY ?? "START_SENSITIVITY_LOW",
  GEMINI_VAD_END_SENSITIVITY: process.env.GEMINI_VAD_END_SENSITIVITY ?? "END_SENSITIVITY_LOW",
  GEMINI_VAD_PREFIX_PADDING_MS: parseInt(process.env.GEMINI_VAD_PREFIX_PADDING_MS ?? "20"),
  GEMINI_VAD_SILENCE_DURATION_MS: parseInt(process.env.GEMINI_VAD_SILENCE_DURATION_MS ?? "300"),

  // Webhook + signature
  TWILIO_WEBHOOK_BASE: process.env.TWILIO_WEBHOOK_BASE ?? resolvedPublicUrl,
  DISABLE_TWILIO_SIGNATURE_VALIDATION: process.env.DISABLE_TWILIO_SIGNATURE_VALIDATION === "true",

  // CORS
  CORS_ORIGIN: process.env.CORS_ORIGIN ?? "*",

  // Firm branding
  FIRM_NAME: process.env.FIRM_NAME ?? "Donna & Associates",
  AGENT_NAME: process.env.AGENT_NAME ?? "Donna",
  ATTORNEY_EMAIL: process.env.ATTORNEY_EMAIL ?? "",
  ATTORNEY_NAME: process.env.ATTORNEY_NAME ?? "Counselor",
  // Attorney's personal cell — calls from this number get attorney-portal mode
  // (case lookup, lead list, calendar). All other inbound numbers get intake mode.
  ATTORNEY_PHONE: process.env.ATTORNEY_PHONE ?? "",
  TWILIO_TRANSFER_NUMBER: process.env.TWILIO_TRANSFER_NUMBER ?? "",

  // Donna bridges
  DONNA_DB_PATH: process.env.DONNA_DB_PATH ?? "./voice_agent.sqlite",
  DONNA_DRAFTS_DIR: process.env.DONNA_DRAFTS_DIR ?? "./drafts",
  DONNA_EMAIL_SERVER_URL: process.env.DONNA_EMAIL_SERVER_URL ?? "",

  // Internal API auth — shared secret for /api/calls/outbound. Required in prod.
  DONNA_API_KEY: process.env.DONNA_API_KEY ?? "",

  // Call duration limit (advisory)
  MAX_CALL_DURATION_SECONDS: parseInt(process.env.MAX_CALL_DURATION_SECONDS ?? "600"),
} as const;
