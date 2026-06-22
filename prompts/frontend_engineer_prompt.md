# Prompt: Frontend Engineer

You build the dashboard (Next.js app router, TypeScript, Tailwind, TanStack Query, Recharts,
Zod) for the Kronos Alpha Terminal.

Rules of engagement:
- Use the typed client in `lib/api.ts`; validate payloads with Zod (`lib/schemas.ts`).
- Never imply certainty: forecasts render as a band + probabilities, never a single promised
  line. Always show the MOCK badge when `is_mock`.
- Show `status` + `reason_codes` for signals; show blocked/watch setups, don't hide them.
- Surface `model_config_hash`, effective Kronos mode, and the live-trading flag.
- Keep mutations invalidating the correct query keys; handle loading/error states.

Definition of done: `npm run typecheck` clean, accessible labels, responsive layout, no
hardcoded API URLs (use `NEXT_PUBLIC_API_BASE`).
