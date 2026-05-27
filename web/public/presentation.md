---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');

  * { box-sizing: border-box; }

  section {
    font-family: 'Inter', sans-serif;
    background:
      url('/TCS-logo-white.svg') no-repeat bottom 18px right 24px / 84px auto,
      #0f172a;
    color: #e2e8f0;
    padding: 56px 72px 64px 72px;
    font-size: 20px;
    line-height: 1.6;
  }

  h1 {
    font-size: 52px;
    font-weight: 900;
    letter-spacing: -1.5px;
    line-height: 1.1;
    color: #f8fafc;
    margin-bottom: 8px;
  }

  h2 {
    font-size: 36px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #f8fafc;
    margin-bottom: 24px;
    border-bottom: 2px solid #334155;
    padding-bottom: 12px;
  }

  h3 {
    font-size: 22px;
    font-weight: 600;
    color: #38bdf8;
    margin-bottom: 10px;
  }

  p { color: #cbd5e1; margin-bottom: 12px; }

  strong { color: #f8fafc; font-weight: 600; }

  em { color: #38bdf8; font-style: normal; font-weight: 600; }

  a { color: #38bdf8; text-decoration: none; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 16px;
    margin-top: 16px;
  }

  th {
    background: #1e293b;
    color: #38bdf8;
    font-weight: 600;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 2px solid #334155;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  td {
    padding: 10px 14px;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
    vertical-align: top;
    background: transparent;
  }

  /* Override Marp's default light zebra-striping so dark theme stays legible. */
  tbody tr { background: transparent; }
  tbody tr:nth-child(even) td { background: rgba(30, 41, 59, 0.55); }
  tbody tr:nth-child(odd)  td { background: transparent; }
  tbody tr:hover td { background: #1e293b; color: #f8fafc; }

  code {
    background: #1e293b;
    color: #7dd3fc;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 15px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
  }

  pre {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 20px;
    font-size: 13px;
    line-height: 1.5;
    overflow: hidden;
  }

  pre code {
    background: none;
    padding: 0;
    color: #e2e8f0;
  }

  ul { padding-left: 20px; }
  li { margin-bottom: 8px; color: #cbd5e1; }
  li::marker { color: #38bdf8; }

  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }
  .cols3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }

  .card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 24px;
  }

  .card-accent {
    background: linear-gradient(135deg, #0f2744 0%, #1e293b 100%);
    border: 1px solid #38bdf8;
    border-radius: 12px;
    padding: 24px;
  }

  .pill {
    display: inline-block;
    background: #0c4a6e;
    color: #38bdf8;
    border: 1px solid #0369a1;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 600;
    margin: 3px;
  }

  .pill-green {
    background: #052e16;
    color: #4ade80;
    border-color: #166534;
  }

  .pill-amber {
    background: #451a03;
    color: #fb923c;
    border-color: #7c2d12;
  }

  .pill-purple {
    background: #2e1065;
    color: #c084fc;
    border-color: #6b21a8;
  }

  .stat {
    text-align: center;
    padding: 20px;
    background: #1e293b;
    border-radius: 12px;
    border: 1px solid #334155;
  }

  .stat-number {
    font-size: 42px;
    font-weight: 900;
    color: #38bdf8;
    line-height: 1;
    display: block;
  }

  .stat-label {
    font-size: 13px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 6px;
    display: block;
  }

  .flow-step {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px 20px;
    position: relative;
  }

  .flow-num {
    display: inline-block;
    background: #0369a1;
    color: #fff;
    border-radius: 50%;
    width: 28px;
    height: 28px;
    text-align: center;
    line-height: 28px;
    font-size: 13px;
    font-weight: 700;
    margin-right: 10px;
  }

  .highlight-box {
    background: linear-gradient(135deg, #0c4a6e22, #0f172a);
    border-left: 4px solid #38bdf8;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin: 12px 0;
  }

  .tag-row { margin-bottom: 12px; }

  header, footer { display: none; }

  section.title-slide {
    background:
      url('/TCS-logo-white.svg') no-repeat bottom 18px right 24px / 84px auto,
      linear-gradient(135deg, #0f172a 0%, #0c1a2e 50%, #0f172a 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .divider {
    width: 60px;
    height: 4px;
    background: linear-gradient(90deg, #38bdf8, #818cf8);
    border-radius: 2px;
    margin: 16px 0 24px 0;
  }

  /* --- Slide entrance animations --- */
  @keyframes fadeInUp {
    from { opacity: 0; transform: translate3d(0, 14px, 0); }
    to   { opacity: 1; transform: translate3d(0, 0, 0); }
  }
  @keyframes slideInRight {
    from { opacity: 0; transform: translate3d(-18px, 0, 0); }
    to   { opacity: 1; transform: translate3d(0, 0, 0); }
  }
  @keyframes glowPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
    50%      { box-shadow: 0 0 0 6px rgba(56, 189, 248, 0.18); }
  }

  /* Animate when the slide becomes active (Bespoke.js adds bespoke-active) */
  section.bespoke-active h2,
  section.bespoke-active h3,
  section.bespoke-active p,
  section.bespoke-active ul,
  section.bespoke-active .highlight-box {
    animation: fadeInUp 0.45s cubic-bezier(0.22, 1, 0.36, 1) backwards;
  }
  section.bespoke-active h2 { animation-delay: 0.05s; }
  section.bespoke-active h3 { animation-delay: 0.15s; }
  section.bespoke-active p,
  section.bespoke-active ul,
  section.bespoke-active .highlight-box { animation-delay: 0.22s; }

  section.bespoke-active .flow-step,
  section.bespoke-active .card,
  section.bespoke-active .card-accent,
  section.bespoke-active .stat {
    animation: slideInRight 0.5s cubic-bezier(0.22, 1, 0.36, 1) backwards;
  }
  section.bespoke-active .flow-step:nth-of-type(1),
  section.bespoke-active .card:nth-of-type(1),
  section.bespoke-active .stat:nth-of-type(1) { animation-delay: 0.18s; }
  section.bespoke-active .flow-step:nth-of-type(2),
  section.bespoke-active .card:nth-of-type(2),
  section.bespoke-active .stat:nth-of-type(2) { animation-delay: 0.28s; }
  section.bespoke-active .flow-step:nth-of-type(3),
  section.bespoke-active .card:nth-of-type(3),
  section.bespoke-active .stat:nth-of-type(3) { animation-delay: 0.38s; }
  section.bespoke-active .flow-step:nth-of-type(4) { animation-delay: 0.48s; }
  section.bespoke-active .flow-step:nth-of-type(5) { animation-delay: 0.58s; }

  /* Hover lift + glow on flow steps */
  .flow-step {
    transition: transform 0.18s ease-out, border-color 0.18s ease-out, box-shadow 0.18s ease-out;
  }
  .flow-step:hover {
    transform: translateY(-2px);
    border-color: #38bdf8;
    box-shadow: 0 8px 24px -12px rgba(56, 189, 248, 0.45);
  }
  .flow-step:hover .flow-num {
    background: linear-gradient(135deg, #38bdf8, #0369a1);
    animation: glowPulse 1.6s ease-out infinite;
  }

  /* Pull the highlight-box gradient out a touch */
  .highlight-box {
    transition: border-left-width 0.18s ease-out;
  }
  .highlight-box:hover { border-left-width: 6px; }

  /* Bigger, friendlier flow-step variant for the dedicated capabilities slide */
  .flow-step.flow-step-lg {
    padding: 20px 24px;
    font-size: 19px;
  }
  .flow-step.flow-step-lg .flow-num {
    width: 34px;
    height: 34px;
    line-height: 34px;
    font-size: 15px;
    margin-right: 14px;
  }
  .flow-step.flow-step-lg .flow-desc {
    display: block;
    margin-top: 4px;
    margin-left: 48px;
    color: #94a3b8;
    font-size: 14px;
    font-weight: 400;
  }

  /* --- PowerPoint-style flow diagram (boxes + solid arrows) --- */
  .ppt-flow {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    margin-top: 4px;
  }
  .ppt-flow-row {
    display: flex;
    gap: 12px;
    align-items: stretch;
    width: 100%;
    justify-content: center;
  }
  .ppt-box {
    background: #1e293b;
    border: 1.5px solid #334155;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: center;
    color: #f8fafc;
    font-size: 13px;
    font-weight: 600;
    min-width: 130px;
    box-shadow: 0 4px 14px -8px rgba(0, 0, 0, 0.6);
  }
  .ppt-box .ppt-sub {
    display: block;
    margin-top: 4px;
    font-size: 11px;
    font-weight: 400;
    color: #94a3b8;
    line-height: 1.35;
  }
  .ppt-box.ppt-src      { border-color: #38bdf8; }
  .ppt-box.ppt-engine   { background: linear-gradient(135deg, #0c4a6e, #0369a1); border-color: #38bdf8; padding: 10px 16px; font-size: 14px; }
  .ppt-box.ppt-data     { background: #052e16; border-color: #4ade80; color: #4ade80; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
  .ppt-box.ppt-claude   { background: linear-gradient(135deg, #2e1065, #6b21a8); border-color: #c084fc; padding: 10px 16px; }

  .ppt-arrow-down {
    width: 3px;
    background: #38bdf8;
    position: relative;
    margin: 2px 0 8px 0;
    flex: 0 0 16px;
    align-self: center;
  }
  .ppt-arrow-down::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 7px solid transparent;
    border-right: 7px solid transparent;
    border-top: 9px solid #38bdf8;
  }

  /* Wide horizontal "tier" box for stacked architecture layers. */
  .ppt-box.ppt-tier {
    text-align: left;
    padding: 8px 16px;
    font-size: 14px;
    background: linear-gradient(180deg, #1e293b 0%, #172033 100%);
  }
  .ppt-box.ppt-tier strong { color: #38bdf8; font-size: 15px; }
  .ppt-box.ppt-tier .ppt-sub {
    margin-top: 3px;
    font-size: 11px;
    color: #cbd5e1;
    line-height: 1.35;
  }
  /* Branching arrows: a single trunk drops from the parent, fans out into a
     horizontal bar, and two arrows descend into the child boxes. Kept
     intentionally compact so the slide fits the bottom summary row too. */
  .ppt-branch {
    position: relative;
    width: 70%;
    height: 32px;
    align-self: center;
    margin: 6px 0 2px 0;
  }
  .ppt-branch::before {
    content: '';
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 3px;
    height: 10px;
    background: #38bdf8;
  }
  .ppt-branch::after {
    content: '';
    position: absolute;
    top: 10px;
    left: 25%;
    right: 25%;
    height: 3px;
    background: #38bdf8;
  }
  .ppt-branch-left,
  .ppt-branch-right {
    position: absolute;
    top: 10px;
    width: 3px;
    height: 22px;
    background: #38bdf8;
  }
  .ppt-branch-left  { left: 25%; }
  .ppt-branch-right { right: 25%; }
  .ppt-branch-left::after,
  .ppt-branch-right::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 8px solid #38bdf8;
  }
---

<!-- _class: title-slide -->

<div style="margin-bottom: 8px;">
  <span class="pill">Enterprise Finance Automation</span>
  <span class="pill pill-purple">AI-Powered</span>
</div>

# Intelligent Accrual Engine
## Automating Month-End Close with Claude AI + SAP BTP

<div class="divider"></div>

<p style="font-size: 22px; color: #94a3b8; max-width: 700px;">
An AI agent that replaces manual accrual extraction, anomaly detection, and posting workflows — connected to live SAP data.
</p>

<div style="margin-top: 40px; display: flex; gap: 48px;">
  <div><span class="stat-number" style="font-size: 28px;">14</span><span class="stat-label">Live Accruals from BTP</span></div>
  <div><span class="stat-number" style="font-size: 28px;">118</span><span class="stat-label">Pharma Batches Tracked</span></div>
  <div><span class="stat-number" style="font-size: 28px;">$12.8M</span><span class="stat-label">Writedown Exposure</span></div>
  <div><span class="stat-number" style="font-size: 28px;">~22s</span><span class="stat-label">End-to-End Pipeline</span></div>
</div>

---

## Introduction

### What is this?

An **AI-powered finance operations platform** that connects directly to SAP S/4HANA data sources and uses Claude to automate the most labor-intensive parts of month-end close.

<div class="highlight-box">
Finance teams interact in <strong>plain English</strong>. The agent queries SAP in real time, reasons over the data, and returns structured, auditable answers.
</div>

### Who is it for?

<div class="cols3" style="margin-top: 18px;">
  <div class="card">
    <h3 style="margin-bottom: 6px; font-size: 18px;">Controllers & Finance Managers</h3>
    <p style="margin: 0; font-size: 15px; color: #94a3b8;">Month-end close acceleration, fewer manual touchpoints.</p>
  </div>
  <div class="card">
    <h3 style="margin-bottom: 6px; font-size: 18px;">Auditors</h3>
    <p style="margin: 0; font-size: 15px; color: #94a3b8;">Full traceability from answer → data → API call.</p>
  </div>
  <div class="card">
    <h3 style="margin-bottom: 6px; font-size: 18px;">SAP Architects</h3>
    <p style="margin: 0; font-size: 15px; color: #94a3b8;">Reference implementation for AI + BTP integration.</p>
  </div>
</div>

---

## Capabilities at a Glance

<p style="color: #94a3b8; font-size: 17px; max-width: 780px; margin-bottom: 28px;">
Five connected stages take a finance question all the way to a posted, auditable journal entry — without a controller leaving the chat.
</p>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px 18px;">
  <div class="flow-step flow-step-lg">
    <span class="flow-num">1</span> <strong>Query</strong>
    <span class="flow-desc">Ask about accruals, POs, inventory in plain English.</span>
  </div>
  <div class="flow-step flow-step-lg">
    <span class="flow-num">2</span> <strong>Detect</strong>
    <span class="flow-desc">AI flags stale POs, duplicates, and anomalies automatically.</span>
  </div>
  <div class="flow-step flow-step-lg">
    <span class="flow-num">3</span> <strong>Review</strong>
    <span class="flow-desc">Finance team reviews flagged items with full context.</span>
  </div>
  <div class="flow-step flow-step-lg">
    <span class="flow-num">4</span> <strong>Post</strong>
    <span class="flow-desc">Approved accruals batched into a single BlackLine JE → SAP.</span>
  </div>
  <div class="flow-step flow-step-lg" style="grid-column: span 2;">
    <span class="flow-num">5</span> <strong>Audit</strong>
    <span class="flow-desc">Every decision persisted with snapshot for compliance — every step replayable.</span>
  </div>
</div>

---

## How Close Works Today

<div class="cols3" style="margin-bottom: 28px;">
<div class="stat">
  <span class="stat-number">3–5</span>
  <span class="stat-label">Days lost per month-end close</span>
</div>
<div class="stat">
  <span class="stat-number">40%</span>
  <span class="stat-label">Of accruals require manual rework</span>
</div>
<div class="stat">
  <span class="stat-number">$12.8M</span>
  <span class="stat-label">Pharma writedown exposure undetected</span>
</div>
</div>

<h3 style="margin-top: 12px;">The manual process today</h3>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px 18px; margin-top: 12px;">
  <div class="flow-step">
    <span class="flow-num">1</span> <strong>Extract</strong> FI journal entries, MM purchase orders, CO cost centers from separate SAP transactions
  </div>
  <div class="flow-step">
    <span class="flow-num">2</span> <strong>Cross-reference</strong> PO status — is the GR done? Is it invoiced? Is the accrual stale?
  </div>
  <div class="flow-step">
    <span class="flow-num">3</span> <strong>Identify duplicates</strong> — same vendor, same amount, same CC posted twice
  </div>
  <div class="flow-step">
    <span class="flow-num">4</span> <strong>Review pharma inventory</strong> — expired batches, quarantined lots, slow-moving SKUs across 5 plants
  </div>
  <div class="flow-step" style="grid-column: span 2;">
    <span class="flow-num">5</span> <strong>Post</strong> approved accruals one-by-one to S/4 via manual journal entry
  </div>
</div>

---

## Why This Breaks at Scale

<p style="color: #94a3b8; font-size: 17px; max-width: 800px; margin-bottom: 24px;">
The manual process limps along at small scale, but three failure modes get more expensive every period — and they're the ones auditors find first.
</p>

<div class="cols3">
  <div class="card" style="border-color: #fb923c; background: linear-gradient(135deg, #1f1108 0%, #1e293b 100%);">
    <h3 style="color: #fb923c; font-size: 18px; margin-bottom: 8px;">Stale PO accruals</h3>
    <p style="margin: 0; font-size: 15px; color: #cbd5e1;">PO goods receipt happened months ago, invoice never arrived. The accrual sits on the books indefinitely, distorting expense recognition.</p>
  </div>
  <div class="card" style="border-color: #fb923c; background: linear-gradient(135deg, #1f1108 0%, #1e293b 100%);">
    <h3 style="color: #fb923c; font-size: 18px; margin-bottom: 8px;">Duplicate postings</h3>
    <p style="margin: 0; font-size: 15px; color: #cbd5e1;">Same vendor + amount + cost center posted twice in the same period. Caught only at reconciliation — well after the close window.</p>
  </div>
  <div class="card" style="border-color: #fb923c; background: linear-gradient(135deg, #1f1108 0%, #1e293b 100%);">
    <h3 style="color: #fb923c; font-size: 18px; margin-bottom: 8px;">Pharma compliance risk</h3>
    <p style="margin: 0; font-size: 15px; color: #cbd5e1;">Expired or quarantined inventory not written down in time creates regulatory exposure across all five plants.</p>
  </div>
</div>

<div class="highlight-box" style="margin-top: 28px; border-color: #38bdf8;">
<strong>The result:</strong> close runs late, audit findings pile up, and finance teams patch the same issues every period because no system is built to detect them upfront.
</div>

---

## Architecture — Data Sources

<div class="cols">
<div>

### Where the data comes from

<div class="card-accent" style="margin-bottom: 12px; padding: 14px 18px;">
  <h3 style="margin-bottom: 4px; font-size: 20px;">☁️ SAP BTP CAP Service</h3>
  <p style="margin: 0; font-size: 14px; color: #94a3b8;">af3d148dtrial.cfapps.us10-001.hana.ondemand.com</p>
  <p style="margin: 8px 0 4px 0; font-size: 14px; color: #cbd5e1;"><strong style="color: #38bdf8;">FI / MM / CO:</strong> <code style="font-size: 13px; padding: 1px 5px;">OPLACCTGDOCITEMCUBE</code> · <code style="font-size: 13px; padding: 1px 5px;">PURCHASEORDER_PROCESS</code> · <code style="font-size: 13px; padding: 1px 5px;">COSTCENTER</code></p>
  <p style="margin: 4px 0; font-size: 14px; color: #cbd5e1;"><strong style="color: #4ade80;">Inventory:</strong> <code style="font-size: 13px; padding: 1px 5px;">BATCH</code> · <code style="font-size: 13px; padding: 1px 5px;">STOCK_OVERVIEW</code> · <code style="font-size: 13px; padding: 1px 5px;">MATERIAL_VALUATION</code></p>
  <p style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;">6 OData v2 services in one CAP app · 125 pharma batches · 5 plants</p>
</div>

<div class="card-accent" style="margin-bottom: 12px; padding: 14px 18px;">
  <h3 style="margin-bottom: 4px; font-size: 20px;">🏢 Workday Global Payroll</h3>
  <p style="margin: 0; font-size: 14px; color: #94a3b8;">SOAP · WS-Security UsernameToken</p>
  <p style="margin: 8px 0 4px 0; font-size: 14px; color: #cbd5e1;"><strong style="color: #c084fc;">Operations:</strong> <code style="font-size: 13px; padding: 1px 5px;">Get_Payroll_Results</code> · <code style="font-size: 13px; padding: 1px 5px;">PECI FI lines</code></p>
  <p style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;">Live path stubbed → demo fixtures (no Workday tenant)</p>
</div>

<p style="font-size: 13px; color: #64748b; margin-top: 6px;">
<strong style="color: #94a3b8;">Alt:</strong> sandbox.api.sap.com is a drop-in for the CAP source via <code style="font-size: 12px; padding: 1px 5px;">SAP_SANDBOX_BASE_URL</code>.
</p>

</div>
<div>

### Data flow

<div class="ppt-flow">
  <div class="ppt-flow-row">
    <div class="ppt-box ppt-src">SAP BTP CAP<span class="ppt-sub">FI · MM · CO ·<br>Batch · Stock · Valuation</span></div>
    <div class="ppt-box ppt-src">Workday SOAP<span class="ppt-sub">Get_Payroll_Results<br>PECI FI lines</span></div>
  </div>
  <div class="ppt-arrow-down"></div>
  <div class="ppt-box ppt-engine">FastAPI Backend<span class="ppt-sub" style="color: #bae6fd;">async fetchers · normalize() · join FI + MM + CO</span></div>
  <div class="ppt-arrow-down"></div>
  <div class="ppt-flow-row">
    <div class="ppt-box ppt-data">AccrualObject[]</div>
    <div class="ppt-box ppt-data">PayrollReconciliation[]</div>
  </div>
  <div class="ppt-arrow-down"></div>
  <div class="ppt-box ppt-claude">Claude AI Analysis<span class="ppt-sub" style="color: #e9d5ff;">tool-use → flag / approve / post</span></div>
</div>

</div>
</div>

---

## Technical Architecture

<div class="ppt-flow" style="gap: 0;">

  <div class="ppt-box ppt-tier" style="width: 78%;">
    <strong>Browser</strong> — React 19 · Next.js client
    <span class="ppt-sub">Chat UI · Streaming SSE · Tool-call badges · Posting workflow stepper</span>
  </div>

  <div class="ppt-arrow-down"></div>

  <div class="ppt-box ppt-tier" style="width: 78%;">
    <strong>Vercel Functions</strong> — Next.js 16 App Router
    <span class="ppt-sub">AI SDK v6 ToolLoopAgent · Server Actions · Vercel Workflow DevKit · LRU response cache (30 min) · Anthropic prompt-cache breakpoint (~90% token discount)</span>
  </div>

  <div class="ppt-branch">
    <div class="ppt-branch-left"></div>
    <div class="ppt-branch-right"></div>
  </div>

  <div class="ppt-flow-row" style="align-items: stretch; gap: 18px; width: 70%;">
    <div class="ppt-box ppt-claude" style="flex: 1 1 0;">
      <strong>Anthropic API</strong>
      <span class="ppt-sub" style="color: #e9d5ff;">Claude Sonnet 4.6 · tool-use<br>getAccruals · getBatches · detectIrregularities<br>createPosting · listPostings · postApprovedAccruals</span>
    </div>
    <div class="ppt-box ppt-engine" style="flex: 1 1 0;">
      <strong>Vercel Functions</strong> — FastAPI · Python 3.12
      <span class="ppt-sub" style="color: #bae6fd;">/accruals · /inventory/batches · /runs · /postings · /postback/* · /blackline/* · /payroll/results · /plan<br>httpx.AsyncClient · asyncio.gather · Pydantic v2 · SQLAlchemy 2.0 · structlog · Jinja2</span>
    </div>
  </div>

  <div class="ppt-arrow-down"></div>

  <div class="ppt-flow-row" style="gap: 18px;">
    <div class="ppt-box ppt-src">
      <strong>SAP BTP CAP</strong>
      <span class="ppt-sub">af3d148dtrial.cfapps.us10-001.hana.ondemand.com<br>FI · MM · CO · Batch · Stock · Valuation (6 OData v2 services)</span>
    </div>
    <div class="ppt-box ppt-src" style="border-color: #c084fc;">
      <strong style="color: #f8fafc;">Workday SOAP</strong>
      <span class="ppt-sub">Get_Payroll_Results · PECI FI lines<br>Stubbed → demo fixtures</span>
    </div>
  </div>

</div>

<div class="cols3" style="margin-top: 12px;">
  <div class="card" style="padding: 8px 12px;">
    <strong style="font-size: 14px;">50 tests passing</strong>
    <span style="display: block; color: #64748b; font-size: 11px; margin-top: 2px;">pytest · mypy strict · TypeScript strict</span>
  </div>
  <div class="card" style="padding: 8px 12px;">
    <strong style="font-size: 14px;">2-layer caching</strong>
    <span style="display: block; color: #64748b; font-size: 11px; margin-top: 2px;">Anthropic prompt cache + Next.js LRU (30 min)</span>
  </div>
  <div class="card" style="padding: 8px 12px;">
    <strong style="font-size: 14px;">Durable workflows</strong>
    <span style="display: block; color: #64748b; font-size: 11px; margin-top: 2px;">Workflow DevKit · approval hook · BlackLine + CAP postback</span>
  </div>
</div>

---

## Pharma Reserve Workflow — Inventory Write-Down to SAP

<div class="cols">
<div>

### The problem

Pharma companies hold **$12.8M+** in distressed inventory across 5 distribution centers. Without automation, write-downs are identified manually at quarter-end — too late for accurate period reporting.

### Distress signals tracked

| Signal | Threshold | Write-down % |
|---|---|---|
| **Expired** | SLED < today | 100% |
| **Marked for deletion** | SAP flag set | 100% |
| **Quarantine** | Restricted use | 50% |
| **Near expiry** | SLED < 90 days | 25% |
| **Slow-moving** | No GR in 365d | 30% |

</div>
<div>

### Automated workflow

<div class="flow-step" style="margin-bottom: 8px;">
  <span class="flow-num">1</span> <strong>Extract</strong> — Agent calls <code>getWritedownExtract</code> → joins MB52 + MBEW from BTP CAP
</div>
<div class="flow-step" style="margin-bottom: 8px;">
  <span class="flow-num">2</span> <strong>Draft JE</strong> — <code>draftWriteoffJE(reason="expired")</code> builds BlackLine-format JE: DR Inventory Write-off Expense / CR Accrued Inventory Write-off
</div>
<div class="flow-step" style="margin-bottom: 8px;">
  <span class="flow-num">3</span> <strong>Review</strong> — Agent shows full JE table (lines + per-plant breakdown + batch detail). Finance team approves in chat.
</div>
<div class="flow-step" style="margin-bottom: 8px;">
  <span class="flow-num">4</span> <strong>Post</strong> — <code>POST /blackline/post</code> → validates balance → simulates <code>BAPI_ACC_DOCUMENT_POST</code> → returns SAP document number
</div>
<div class="flow-step">
  <span class="flow-num">5</span> <strong>Audit</strong> — SAP doc number + per-batch supporting detail stored for compliance
</div>

<div class="highlight-box" style="margin-top: 12px;">
One <strong>single balanced JE file</strong> sent to BlackLine — not 118 individual postings
</div>

</div>
</div>

---

## Workday & PO Expense Accruals — Sending to SAP

<div class="cols">
<div>

### Purchase Order Accruals

**14 live accruals from BTP CAP · 12 PO-backed**

The pipeline runs Claude over FI + MM + CO data to detect:

<div class="card" style="margin-bottom: 10px; padding: 14px;">
  <span class="pill pill-amber">Stale PO</span>
  <p style="margin: 8px 0 0 0; font-size: 15px;">PO 4500000006 — Meridian Engineering, GR Nov 2025 (>180 days), not invoiced. €22,000 sitting on books.</p>
</div>

<div class="card" style="margin-bottom: 10px; padding: 14px;">
  <span class="pill pill-amber">Duplicate</span>
  <p style="margin: 8px 0 0 0; font-size: 15px;">Docs 0100000002 + 0100000003 — Brightside Marketing, $12,500 USD, same CC, 1 day apart.</p>
</div>

<div class="card" style="padding: 14px;">
  <span class="pill pill-green">Approved</span>
  <p style="margin: 8px 0 0 0; font-size: 15px;">Clean accruals batched into one BlackLine JE → single POST to SAP.</p>
</div>

</div>
<div>

### Workday Payroll Accruals

**40 reconciliation rows · 6 anomalies seeded**

Workday PECI delivers payroll into SAP FI. The agent reconciles both sides:

| Anomaly | Employee | Severity |
|---|---|---|
| Wrong cost center | EMP-1005 | Medium |
| Wrong GL account | EMP-1007 | Medium |
| Missing FI posting | EMP-1012 | **High** |
| Duplicate FI posting | EMP-1017 | **High** |
| FICA under-posted $75 | EMP-1019 | Low |
| Phantom worker in FI | EMP-9999 | Medium |

<div class="highlight-box" style="margin-top: 12px;">
Period 2 (pay date Jun 5) is <strong>unposted</strong> — <code>accrual_variance_to_post</code> per row = the accrual the close team books
</div>

</div>
</div>

---

## What the Agent Can Answer

<div class="cols">
<div>

### Example Queries

<div class="flow-step" style="margin-bottom: 6px; padding: 8px 12px;">
  <strong style="font-size: 14px;">💬 "Show me current PO-backed accruals"</strong>
  <p style="margin: 2px 0 0 0; font-size: 12px; color: #64748b;"><code style="font-size: 11px;">getAccruals</code> → FI+MM+CO join → 13-column table</p>
</div>
<div class="flow-step" style="margin-bottom: 6px; padding: 8px 12px;">
  <strong style="font-size: 14px;">💬 "Find duplicate or stale accruals"</strong>
  <p style="margin: 2px 0 0 0; font-size: 12px; color: #64748b;"><code style="font-size: 11px;">detectIrregularities</code> → Claude flags + persisted run</p>
</div>
<div class="flow-step" style="margin-bottom: 6px; padding: 8px 12px;">
  <strong style="font-size: 14px;">💬 "Compare Apr 2026 actuals vs plan for IT"</strong>
  <p style="margin: 2px 0 0 0; font-size: 12px; color: #64748b;"><code style="font-size: 11px;">getAccruals</code> + <code style="font-size: 11px;">getPlan</code> → variance inline</p>
</div>
<div class="flow-step" style="margin-bottom: 6px; padding: 8px 12px;">
  <strong style="font-size: 14px;">💬 "Show distressed pharma inventory"</strong>
  <p style="margin: 2px 0 0 0; font-size: 12px; color: #64748b;"><code style="font-size: 11px;">getWritedownExtract</code> → MB52+MBEW · $12.8M total</p>
</div>
<div class="flow-step" style="margin-bottom: 6px; padding: 8px 12px;">
  <strong style="font-size: 14px;">💬 "Initiate write-off for expired batches"</strong>
  <p style="margin: 2px 0 0 0; font-size: 12px; color: #64748b;"><code style="font-size: 11px;">draftWriteoffJE</code> → approve → <code style="font-size: 11px;">postWriteoffJE</code></p>
</div>
<div class="flow-step" style="padding: 8px 12px;">
  <strong style="font-size: 14px;">💬 "Did EMP-1010 get prorated correctly?"</strong>
  <p style="margin: 2px 0 0 0; font-size: 12px; color: #64748b;"><code style="font-size: 11px;">getPayrollResults(worker_id=&quot;EMP-1010&quot;)</code></p>
</div>

</div>
<div>

### Response format — always 3 sections

<div class="card-accent" style="margin-bottom: 8px; padding: 10px 14px;">
  <h3 style="margin-bottom: 2px; font-size: 14px;">## How I answered this</h3>
  <p style="margin: 0; font-size: 12px; color: #94a3b8;">Which tools called, what filters, why, how many records returned — auditable without raw output.</p>
</div>

<div class="card-accent" style="margin-bottom: 8px; padding: 10px 14px;">
  <h3 style="margin-bottom: 2px; font-size: 14px;">## Data</h3>
  <p style="margin: 0; font-size: 12px; color: #94a3b8;">Full Markdown table · no silent truncation · all key IDs included. Expandable tool-call badges show raw JSON.</p>
</div>

<div class="card-accent" style="padding: 10px 14px;">
  <h3 style="margin-bottom: 2px; font-size: 14px;">## Findings / Recommendation</h3>
  <p style="margin: 0; font-size: 12px; color: #94a3b8;">Analysis citing specific rows by ID, ending with a concrete next action for the finance team.</p>
</div>

<div class="highlight-box" style="margin-top: 10px; padding: 10px 14px; font-size: 12px;">
Every claim → data → tool call → SAP API request. Fully traceable end-to-end.
</div>

</div>
</div>

---

## System URLs & Infrastructure

<div class="cols">
<div>

### Vercel Deployments

<div class="card" style="margin-bottom: 8px; padding: 10px 14px;">
  <h3 style="margin-bottom: 4px; font-size: 15px;">🌐 Frontend — Next.js 16</h3>
  <a href="https://accuralsap.vercel.app" style="color: #38bdf8; font-size: 13px; font-weight: 600;">accuralsap.vercel.app</a>
  <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;">React 19 · AI SDK v6 · Tailwind · shadcn/ui · <code style="font-size: 11px;">accural_sap_frontend</code></p>
</div>

<div class="card" style="margin-bottom: 8px; padding: 10px 14px;">
  <h3 style="margin-bottom: 4px; font-size: 15px;">⚙️ Backend — FastAPI Python</h3>
  <a href="https://accrualsap.vercel.app" style="color: #38bdf8; font-size: 13px; font-weight: 600;">accrualsap.vercel.app</a>
  <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;">Python 3.12 · FastAPI · SQLAlchemy 2.0 · structlog · <code style="font-size: 11px;">accrual_sap_backend</code></p>
</div>

<div class="card" style="padding: 10px 14px;">
  <h3 style="margin-bottom: 4px; font-size: 15px;">☁️ SAP BTP CAP — Mock SAP Services</h3>
  <p style="margin: 0; font-size: 12px; color: #38bdf8; word-break: break-all;">af3d148dtrial-dev-mocksap-srv.cfapps.us10-001.hana.ondemand.com</p>
  <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;">All 6 OData services · 125 pharma batches · MB52 · MBEW · Batch SRV</p>
</div>

</div>
<div>

### SAP & AI Services

<div class="card" style="margin-bottom: 8px; padding: 10px 14px;">
  <h3 style="margin-bottom: 4px; font-size: 15px;">🔌 SAP Business Accelerator Hub</h3>
  <a href="https://sandbox.api.sap.com" style="color: #38bdf8; font-size: 13px;">sandbox.api.sap.com</a>
  <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;">Free tier · APIKey auth · drop-in alt for FI / MM / CO via <code style="font-size: 11px;">SAP_SANDBOX_BASE_URL</code></p>
</div>

<div class="card" style="margin-bottom: 8px; padding: 10px 14px;">
  <h3 style="margin-bottom: 4px; font-size: 15px;">🤖 Anthropic — Claude Sonnet 4.6</h3>
  <a href="https://console.anthropic.com" style="color: #38bdf8; font-size: 13px;">console.anthropic.com</a>
  <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;"><code style="font-size: 11px;">claude-sonnet-4-6</code> · max-tokens 4096 / 16384 · prompt-cache breakpoint (~90% discount)</p>
</div>

<div class="card" style="padding: 10px 14px;">
  <h3 style="margin-bottom: 4px; font-size: 15px;">🗄️ Local Persistence — SQLite</h3>
  <p style="margin: 0; font-size: 12px; color: #64748b;">SQLAlchemy 2.0 · 5 tables: <code style="font-size: 11px;">run_metadata</code> · <code style="font-size: 11px;">flagged_items</code> · <code style="font-size: 11px;">approved_items</code> · <code style="font-size: 11px;">postings</code> · <code style="font-size: 11px;">posting_events</code></p>
  <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;">Full audit snapshots frozen at decision time. Vercel: <code style="font-size: 11px;">/tmp/accrual.db</code></p>
</div>

</div>
</div>

---

<!-- _class: title-slide -->

<div style="text-align: center; padding-top: 140px;">

# Questions?

<p style="font-size: 24px; color: #94a3b8; margin-top: 28px;">
Thank you for your time
</p>

</div>
