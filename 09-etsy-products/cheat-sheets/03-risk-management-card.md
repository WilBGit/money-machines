# 🤖 AI Jarvis Trading Desk
## Risk Management Card — Position Sizing & Stop Rules

### Position Sizing Formula

```
Position Size = (Account × Risk%) / (Option Price × Stop Loss%)
```

**Example:** $50,000 account, risk 1% per trade, option costs $5, 25% stop loss

- Max risk $ = $50,000 × 0.01 = **$500**
- Stop loss $ = $5.00 × 0.25 = **$1.25 per contract**
- Contracts = $500 / $1.25 = **4 contracts**

### Hard Limits — Never Exceed

| Rule | Limit | Notes |
|------|-------|-------|
| Max risk per trade | **1–2%** of account | 2% = aggressive; 1% = conservative |
| Max daily loss | **3%** of account | Hit it → stop trading for the day |
| Max weekly loss | **6%** of account | Hit it → reduce size 50% next week |
| Max open positions | **5** | Prevents overexposure |
| Max sector concentration | **30%** | Don't stack same sector |

### Stop-Loss Levels (3 Tiers)

| Stop Type | Trigger | Action |
|-----------|---------|--------|
| 🟡 **Soft Stop** | Option drops **25%** from entry | Evaluate — tighten or exit |
| 🔴 **Hard Stop** | Option drops **35%** from entry | Exit immediately — no exceptions |
| ⚫ **Underlying Stop** | Stock drops **0.15%** below key support | Exit the option regardless of P&L |

### Daily Loss Tracker

| Daily Loss | Action |
|-----------|--------|
| 0 – 1.5% | 🟢 Normal trading |
| 1.5 – 3% | 🟡 Reduce size 50%, no new positions |
| 3%+ | 🔴 **Stop trading today** |

### Risk Checklist (Pre-Trade)

- [ ] Risk per trade ≤ 2% of account?
- [ ] Daily loss limit not reached?
- [ ] Stop-loss level defined **before** entry?
- [ ] No more than 5 open positions?
- [ ] Sector not over-concentrated?
- [ ] Would this loss be survivable?

> **AI Jarvis Rule:** If you're debating whether to hold a losing position — you should already be out.

---

📥 **Get the full 5-sheet bundle:** https://example.com/products
