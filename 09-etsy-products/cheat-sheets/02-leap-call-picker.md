# 🤖 AI Jarvis Trading Desk
## LEAP Call Picker — Strikes, Deltas & Breakevens

### Strike Selection at a Glance

| Type | Delta Range | Cost | Breakeven | Best For |
|------|------------|------|-----------|----------|
| **Deep ITM** | 0.80–0.90 | High | Close to current price | Conservative / stock replacement |
| **ITM** | 0.60–0.79 | Medium | Modest move needed | Balanced risk/reward |
| **ATM** | 0.45–0.55 | Moderate | Strike + premium | Directional with leverage |
| **OTM** | 0.30–0.44 | Low | Significant move needed | Speculative / high leverage |
| **Far OTM** | 0.10–0.29 | Very low | Large move required | Lottery ticket — avoid |

### LEAP Call Selection Rules

1. **Minimum Delta:** ≥ 0.60 (ITM preferred for LEAPs)
2. **Minimum DTE:** 6–12 months (LEAP = 1yr+ ideal)
3. **IV Percentile:** Buy when IV < 50th pct (cheaper premium)
4. **Breakeven must be reachable** — compare to 52-week range

### Breakeven Math

```
Breakeven = Strike Price + Premium Paid
```

**Example:** Buy $150 strike call for $12.50
- Breakeven = $150 + $12.50 = **$162.50**
- Stock must exceed $162.50 by expiration to profit

### ITM vs OTM — When to Choose What

| Situation | Choose | Why |
|-----------|--------|-----|
| High conviction, long timeframe | Deep ITM (Δ 0.80+) | Higher Δ = moves like stock, less theta decay |
| Moderate conviction, balanced | ITM (Δ 0.60–0.79) | Good leverage without excessive premium |
| Speculative, short timeframe | ATM/OTM (Δ 0.30–0.55) | Cheaper but needs bigger move |
| IV is elevated | Deeper ITM | Less extrinsic value to decay |

### Delta & Probability Cheat

| Delta | ≈ Probability of Finishing ITM |
|-------|-------------------------------|
| 0.80 | 80% |
| 0.70 | 70% |
| 0.50 | 50% |
| 0.30 | 30% |
| 0.20 | 20% |

> **AI Jarvis Tip:** For LEAPs, prioritize **0.65–0.80 delta**. You want the option to behave like the stock while still getting leverage.

---

📥 **Get the full 5-sheet bundle:** https://example.com/products
