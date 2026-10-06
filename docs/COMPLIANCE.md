# Compliance: before subscriptions or other users

TAA is run by its owner for their own trading. Selling access or giving trading advice to other people is a
different activity with legal duties in Thailand. This file lists what must be settled with counsel **before**
`SUBSCRIPTIONS_ENABLED` is turned on, and what the software already does. It is a checklist for the owner and
their lawyer, not legal advice.

The software enforces the gate: while `SUBSCRIPTIONS_ENABLED=false` (the default) every subscription and billing
route answers 404, and turning it on requires `SUBSCRIPTIONS_LEGAL_REVIEW` (a reference to the review, e.g.
"2027-01-15 counsel memo #12"). Linking engines for non-owner users stays off behind `MULTI_ENGINE_ENABLED=false`
for the same reason (PLAN R32, §A32).

## 1. Securities and derivatives advice (SEC Thailand)

Background (PLAN R32): giving advice on securities or **derivatives** (forex and CFDs included) to the public for
a fee is a licensed business. There are exemptions, for example advising at most 15 investors in 12 months
without holding out as an advisor, and the SEC has stated its position on foreign operators serving Thai
investors (2024).

Questions for counsel:

1. Do opportunity alerts, win probabilities, suitability rankings or entry plans count as "investment advice"
   (or "derivatives advice") when other users receive them? Does it matter whether they pay?
2. Which license would be needed (investment advisor, derivatives advisor, other), or does an exemption apply
   to a small closed group? How is the 15-investor count measured (users, accounts, 12-month window)?
3. Is it different if users only receive *market facts* (evidence, shadow statistics) and no sizing?
4. Do users who run their own engine on their own broker account (rev. 4, self-hosted) change the analysis,
   given that the cloud never trades for them?
5. Which disclaimers and risk warnings are required, in Thai and English, and where (push texts, app)?
6. Are hypothetical results (shadow trades, backtests) allowed to be shown, and with which labels? The product
   already marks them `hypothetical` and never claims profitability.
7. Does the FBS broker relationship (or any referral/affiliate arrangement) create additional duties?
8. Record-keeping: how long must alerts, the evidence behind them and user communications be kept?
9. AI-written text (TAA-1305): opinions and narratives produced by a third-party model are shown to users,
   labelled "AI opinion, not advice", and the opt-in filter can suppress alerts the AI disagreed with. Does
   that change questions 1–5, and is a disclosure of the model provider required?

## 2. Personal data (PDPA)

What the software does today:

| Duty | Implementation |
|---|---|
| Access / portability | `GET /api/v1/me/export`: everything stored about the user as JSON (no password hashes, TOTP secrets, push keys or engine secrets) |
| Erasure | `POST /api/v1/me/erase` (step-up, typed username), or by the owner on request: personal rows are deleted; the user row is pseudonymised (`deleted-<id>`) because revoked engines and the audit chains refer to it |
| Minimisation | push payloads hold no balances or logins; subscribers never receive the owner's account data |
| Security | argon2id passwords, mandatory TOTP, encrypted secrets, signed engine traffic, audit chains |

Open questions:

1. Lawful basis and notice for each data category (account, preferences, alert history, account profile figures,
   push subscriptions, logs). Which notice text, in which language, at sign-up?
2. Consent for marketing or analytics, if any is added later.
3. Retention periods: alert history, notifications, backtests, audit records. The append-only audit chains keep the
   original username in events written before an erasure; is pseudonymisation of the user row enough, or must
   those events be rewritten (which would break the hash chain)?
4. Cross-border transfer: the cloud runs on Railway (Singapore region) and Web Push goes through Google, Mozilla,
   Apple and Microsoft push services. Which safeguards and disclosures are needed?
5. Data processor agreements with Railway and any billing provider.
6. Breach notification process (72 hours to the PDPC where required) and who is responsible.
7. A data protection officer: required at this scale or not?

## 3. Payments

Background (PLAN R33): Stripe is available in Thailand, including recurring billing; PromptPay suits one-time or
prepaid periods only. The code has a `BillingProvider` interface, a stub that refuses checkout, Stripe-style
signed webhooks (timestamp + HMAC-SHA256, 5-minute tolerance, each event applied once) and subscription
states (ACTIVE, CANCELED, EXPIRED, PAST_DUE), see `app/web/billing.py`.

Questions: VAT registration and invoices (e-Tax invoice), consumer refund rules for digital subscriptions,
terms of service, and the provider's own restrictions on trading-signal businesses.

## 4. Before turning anything on

- [ ] Counsel's answers to sections 1–3, recorded and referenced in `SUBSCRIPTIONS_LEGAL_REVIEW`
- [ ] Terms of service, privacy notice and risk disclosures (TH/EN) in the PWA
- [ ] Plans priced and activated (`plans.active`), entitlements reviewed (`app/web/entitlements.py`)
- [ ] A real `BillingProvider` adapter and its webhook secret (`BILLING_WEBHOOK_SECRET`)
- [ ] `MULTI_ENGINE_ENABLED` decided separately (other users linking their own engines)
- [ ] Owner sign-off; then `SUBSCRIPTIONS_ENABLED=true` on the web service
