from __future__ import annotations

import json

from .provider_config import ui_chat_presets


def app_html() -> str:
    html = r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Survey Insight</title>
  <style>
    :root {
      --bg: #eef2f4;
      --surface: #ffffff;
      --surface-soft: #f7f9fb;
      --surface-tint: #f2f8f6;
      --line: #cdd6df;
      --line-strong: #aebbc8;
      --text: #17212b;
      --muted: #657384;
      --accent: #256b5f;
      --accent-dark: #174e47;
      --accent-soft: #e4f2ef;
      --coral: #c95445;
      --coral-soft: #fae8e4;
      --violet: #6557d2;
      --violet-soft: #eceafd;
      --gold: #b36b12;
      --gold-soft: #fff0d8;
      --ink: #17212b;
      --blue: #285f9f;
      --blue-soft: #e8f0fb;
      --green: #17725d;
      --amber: #9a6700;
      --danger: #b42318;
      --shadow: 0 12px 28px rgba(28, 39, 49, 0.08);
      --shadow-soft: 0 1px 2px rgba(28, 39, 49, 0.08);
      --focus: 0 0 0 3px rgba(37, 107, 95, 0.15);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background: linear-gradient(180deg, #eef2f4 0%, #f8f4ef 100%);
      color: var(--text);
      font-family: "Inter", "Segoe UI", Arial, "Malgun Gothic", sans-serif;
      letter-spacing: 0;
    }
    header {
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
      position: sticky;
      top: 0;
      z-index: 20;
      box-shadow: var(--shadow-soft);
      backdrop-filter: blur(14px);
    }
    .bar {
      max-width: 1360px;
      margin: 0 auto;
      padding: 13px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .brand-mark {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      background: linear-gradient(135deg, var(--ink), var(--accent-dark));
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 800;
      font-size: 13px;
      letter-spacing: 0;
      box-shadow: inset 0 -10px 20px rgba(255, 255, 255, 0.08);
      flex: 0 0 auto;
    }
    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.3;
      font-weight: 700;
    }
    .subtitle {
      margin: 2px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.3;
    }
    main {
      max-width: 1360px;
      margin: 0 auto;
      padding: 22px 28px 34px;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(300px, 372px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    section, aside {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    aside {
      position: sticky;
      top: 84px;
    }
    .panel-head {
      padding: 15px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-soft);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }
    .panel-head h2 {
      margin: 0;
      font-size: 14px;
      line-height: 1.3;
      font-weight: 700;
    }
    .panel-body { padding: 18px; }
    .stack { display: grid; gap: 13px; }
    .row {
      display: flex;
      gap: 9px;
      align-items: center;
      flex-wrap: wrap;
    }
    label {
      display: block;
      margin-bottom: 6px;
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
      letter-spacing: 0;
    }
    input[type="text"], input[type="password"], input[type="file"], select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font-size: 14px;
      padding: 10px 11px;
      min-height: 40px;
      transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
    }
    input[type="text"]:focus, input[type="password"]:focus, input[type="file"]:focus, select:focus {
      border-color: var(--accent);
      box-shadow: var(--focus);
      outline: none;
    }
    select[multiple] { min-height: 118px; }
    #providerSettings {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-tint);
      padding: 12px;
    }
    .check-option {
      display: grid;
      grid-template-columns: 18px minmax(0, 1fr);
      gap: 9px;
      align-items: start;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px;
      background: #fff;
    }
    .check-option input {
      width: 16px;
      height: 16px;
      margin: 2px 0 0;
      accent-color: var(--accent);
    }
    .check-option label {
      margin: 0 0 3px;
      color: var(--text);
      font-size: 13px;
    }
    .check-option p {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    button, .download-link {
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 10px 13px;
      font-size: 14px;
      font-weight: 700;
      line-height: 1.2;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      white-space: nowrap;
      transition: background-color 0.15s ease, border-color 0.15s ease, transform 0.12s ease;
    }
    button.primary {
      background: var(--accent-dark);
      color: #fff;
    }
    button.primary:hover:not(:disabled) {
      background: var(--accent);
      transform: translateY(-1px);
    }
    button.secondary, .download-link {
      background: #fff;
      color: var(--accent-dark);
      border-color: var(--line-strong);
    }
    button.secondary:hover:not(:disabled), .download-link:hover {
      border-color: var(--accent);
      background: var(--accent-soft);
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }
    .status {
      font-size: 12px;
      color: var(--muted);
      min-height: 18px;
      line-height: 1.45;
    }
    .status.error { color: var(--danger); }
    .status.ok { color: var(--green); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 11px;
      margin-bottom: 18px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px;
      background: var(--surface-soft);
      box-shadow: var(--shadow-soft);
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }
    .metric .value {
      font-size: 21px;
      font-weight: 700;
      line-height: 1.2;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px 9px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: #344054;
      background: #eef3f6;
      font-weight: 700;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    .table-wrap {
      max-height: 420px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
      background: var(--accent-soft);
      color: var(--accent-dark);
      line-height: 1.3;
    }
    .pill.warn {
      background: #fff4d6;
      color: var(--amber);
    }
    .tabs {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--line);
      padding: 10px 10px 0;
      background: var(--surface-soft);
      overflow-x: auto;
    }
    .tab {
      border: 1px solid transparent;
      background: transparent;
      color: var(--muted);
      border-radius: 6px 6px 0 0;
      min-height: 38px;
      padding: 9px 12px;
    }
    .tab.active {
      color: var(--text);
      background: #fff;
      border-color: var(--line);
      border-bottom-color: #fff;
    }
    .tab-panel { display: none; padding: 18px; }
    .tab-panel.active { display: block; }
    .topic-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 13px;
    }
    .topic {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fff;
      box-shadow: var(--shadow-soft);
      border-top: 3px solid var(--accent);
    }
    .topic h3 {
      margin: 0 0 8px;
      font-size: 15px;
      line-height: 1.3;
    }
    .topic p {
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .explain-box {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px;
      background: var(--surface-soft);
      margin-bottom: 12px;
    }
    .dashboard {
      display: grid;
      gap: 14px;
      margin-bottom: 16px;
    }
    .hero-insight {
      display: grid;
      grid-template-columns: minmax(220px, 0.8fr) minmax(0, 1.2fr);
      gap: 14px;
      border: 1px solid rgba(23, 33, 43, 0.12);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(23, 33, 43, 0.96) 0%, rgba(37, 107, 95, 0.94) 58%, rgba(179, 107, 18, 0.88) 100%);
      padding: 18px;
      box-shadow: 0 18px 36px rgba(23, 33, 43, 0.15);
      color: #fff;
    }
    .hero-insight .eyebrow,
    .dashboard-section .eyebrow {
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .hero-insight .eyebrow {
      color: rgba(255, 255, 255, 0.74);
    }
    .hero-number {
      display: flex;
      align-items: baseline;
      gap: 6px;
      margin: 0 0 8px;
      color: #fff;
    }
    .hero-number strong {
      font-size: 42px;
      line-height: 1;
      letter-spacing: 0;
    }
    .hero-number span {
      font-size: 18px;
      font-weight: 700;
    }
    .hero-copy {
      margin: 0;
      color: rgba(255, 255, 255, 0.86);
      font-size: 14px;
      line-height: 1.55;
    }
    .hero-insight .pill {
      background: rgba(255, 255, 255, 0.16);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.22);
    }
    .decision-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .decision-card,
    .dashboard-section,
    .priority-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: var(--shadow-soft);
    }
    .decision-card {
      padding: 12px;
      min-height: 128px;
      border-top: 4px solid var(--line-strong);
    }
    .decision-card.wide { border-top-color: var(--blue); }
    .decision-card.recommended {
      border-color: rgba(37, 107, 95, 0.38);
      background: var(--surface-tint);
      border-top-color: var(--accent);
    }
    .decision-card.detailed { border-top-color: var(--violet); }
    .decision-card h3,
    .dashboard-section h3 {
      margin: 0 0 7px;
      font-size: 14px;
      line-height: 1.3;
    }
    .decision-card p,
    .dashboard-section p,
    .priority-item p {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .dashboard-section {
      padding: 14px;
    }
    .score-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .score-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--surface-soft);
    }
    .score-card:nth-child(2) .bar-fill { background: var(--violet); }
    .score-card:nth-child(3) .bar-fill { background: var(--gold); }
    .score-card:nth-child(4) .bar-fill { background: var(--coral); }
    .score-card .score-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      color: #344054;
      font-size: 12px;
      font-weight: 700;
    }
    .bar-track {
      height: 7px;
      border-radius: 999px;
      background: #dfe7ee;
      overflow: hidden;
      margin-bottom: 7px;
    }
    .bar-fill {
      height: 100%;
      width: 0%;
      border-radius: inherit;
      background: var(--accent);
    }
    .priority-list {
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }
    .priority-item {
      padding: 12px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
      border-left: 4px solid var(--accent);
    }
    .priority-item.negative { border-left-color: var(--danger); }
    .priority-item.mixed { border-left-color: var(--amber); }
    .priority-item.positive { border-left-color: var(--green); }
    .priority-item.neutral { border-left-color: var(--violet); }
    .topic-table-wrap {
      overflow-x: auto;
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .topic-table {
      min-width: 860px;
      border-collapse: collapse;
      width: 100%;
      font-size: 13px;
    }
    .topic-table th {
      background: #17212b;
      color: #fff;
      font-weight: 700;
    }
    .topic-table th,
    .topic-table td {
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      line-height: 1.45;
    }
    .topic-table tr:last-child td { border-bottom: 0; }
    .topic-table .topic-name {
      color: #17212b;
      font-weight: 800;
      min-width: 170px;
    }
    .topic-table .topic-action {
      color: #344054;
      min-width: 260px;
    }
    .topic-table .topic-sentiment {
      min-width: 230px;
    }
    .topic-table .topic-evidence {
      color: var(--muted);
      min-width: 220px;
    }
    .sentiment-detail {
      display: grid;
      gap: 7px;
      padding: 9px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-soft);
    }
    .priority-item .sentiment-detail {
      background: #fff;
    }
    .sentiment-detail p {
      margin: 0;
      color: #344054;
      font-size: 12px;
      line-height: 1.45;
    }
    .sentiment-bars {
      display: grid;
      gap: 6px;
    }
    .sentiment-meter {
      display: grid;
      grid-template-columns: 62px 1fr minmax(78px, max-content);
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
    }
    .sentiment-meter-track {
      height: 6px;
      border-radius: 999px;
      background: #dfe7ee;
      overflow: hidden;
    }
    .sentiment-meter-fill {
      height: 100%;
      width: 0%;
      border-radius: inherit;
      background: var(--accent);
    }
    .sentiment-meter-fill.negative { background: var(--danger); }
    .sentiment-meter-fill.mixed { background: var(--amber); }
    .sentiment-meter-fill.positive { background: var(--green); }
    .sentiment-evidence {
      display: flex;
      gap: 5px;
      flex-wrap: wrap;
    }
    .priority-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
      flex-wrap: wrap;
    }
    .priority-body {
      display: grid;
      gap: 8px;
      min-width: 0;
    }
    .priority-head h4 {
      margin: 0;
      font-size: 14px;
      line-height: 1.3;
    }
    .meta-line {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .detail-panel summary {
      cursor: pointer;
      color: var(--accent-dark);
      font-size: 13px;
      font-weight: 700;
      padding: 4px 0;
    }
    .detail-panel[open] summary {
      margin-bottom: 8px;
    }
    .explain-box h3, .topic h4 {
      margin: 0 0 6px;
      font-size: 13px;
      line-height: 1.3;
      font-weight: 700;
    }
    .explain-box p, .topic .plain-note {
      margin: 0;
      color: #344054;
      font-size: 13px;
      line-height: 1.5;
    }
    .topic h4 {
      margin-top: 10px;
    }
    .tab-toolbar {
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .tab-title {
      margin: 0 0 4px;
      font-size: 14px;
      line-height: 1.3;
    }
    .history-list {
      display: grid;
      gap: 10px;
    }
    .history-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px;
      background: #fff;
      display: grid;
      gap: 8px;
      box-shadow: var(--shadow-soft);
    }
    .history-item h3 {
      margin: 0;
      font-size: 14px;
      line-height: 1.3;
    }
    .history-meta {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .history-summary {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .history-actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    button.danger {
      background: #fff;
      color: #b42318;
      border-color: #f0b4ad;
    }
    .trust-note {
      border: 1px solid #b8d6d1;
      border-radius: 8px;
      padding: 11px 12px;
      background: #f1faf8;
      color: #344054;
      font-size: 12px;
      line-height: 1.5;
    }
    .trust-note strong { color: var(--accent-dark); }
    .reps {
      margin: 8px 0 0;
      padding-left: 18px;
      color: #344054;
      font-size: 13px;
      line-height: 1.45;
    }
    .empty {
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 28px;
      text-align: center;
      color: var(--muted);
      background: var(--surface-soft);
    }
    @media (max-width: 860px) {
      .layout { grid-template-columns: 1fr; }
      aside { position: static; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .hero-insight { grid-template-columns: 1fr; }
      .decision-grid, .score-grid { grid-template-columns: 1fr; }
      main, .bar { padding-left: 14px; padding-right: 14px; }
    }
    @media (max-width: 520px) {
      .metrics { grid-template-columns: 1fr; }
      .row { align-items: stretch; }
      button, .download-link { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <div class="brand">
        <div class="brand-mark">AI</div>
        <div>
          <h1>AI Survey Insight</h1>
          <p class="subtitle">토픽모델링 · 감정 신호 · 보고서 자동화</p>
        </div>
      </div>
      <span id="apiState" class="pill">API 확인 중</span>
    </div>
  </header>
  <main>
    <div class="layout">
      <aside>
        <div class="panel-head"><h2>분석 입력</h2></div>
        <div class="panel-body stack">
          <div class="trust-note">
            <strong>로컬 기본 분석</strong>은 외부 AI로 텍스트를 보내지 않지만, 업로드 원본과 분석 결과는 기본적으로 로컬 <code>out/app.db</code>에 저장됩니다. 외부 AI를 선택하면 마스킹된 응답 또는 대표 의견이 provider로 전송될 수 있습니다. 결과와 처리 우선도는 자동 판정이 아니라 담당자 검토용 보조정보입니다.
          </div>
          <div>
            <label for="projectName">프로젝트명</label>
            <input id="projectName" type="text" value="Survey Insight Project" />
          </div>
          <div>
            <label for="fileInput">설문 파일</label>
            <input id="fileInput" type="file" accept=".xlsx,.xlsm,.csv" />
          </div>
          <button id="uploadBtn" class="primary">업로드</button>
          <div id="uploadStatus" class="status"></div>
          <div>
            <label for="textColumn">자유응답 컬럼</label>
            <select id="textColumn" disabled></select>
          </div>
          <div>
            <label for="groupColumns">그룹 컬럼</label>
            <select id="groupColumns" multiple disabled></select>
          </div>
          <div>
            <label for="llmProvider">선택적 외부 AI 보강</label>
            <select id="llmProvider">
              <option value="">사용 안 함</option>
              <option value="gemini">Gemini</option>
              <option value="claude">Claude</option>
              <option value="openai">OpenAI</option>
              <option value="azure_openai">Azure OpenAI</option>
              <option value="custom">OpenAI 호환 서버</option>
            </select>
          </div>
          <div id="providerSettings" class="stack">
            <div class="trust-note"><strong>외부 전송 안내</strong><br />아래 preset은 예시이며 현재 제공을 보장하지 않습니다. 직접 모델명을 입력할 수 있습니다. API 키는 요청 중에만 사용하고 저장하지 않으며, 호출 실패 시 로컬 분석으로 돌아갑니다.</div>
            <div class="trust-note">
              <label><input id="externalTransferConfirmed" type="checkbox" style="width:auto" /> 마스킹된 응답·대표 의견이 선택 provider로 전송될 수 있으며 조직의 위탁처리·국외 이전·보존 정책을 확인했습니다.</label>
            </div>
            <div id="baseUrlField">
              <label for="llmBaseUrl">Endpoint / Base URL</label>
              <input id="llmBaseUrl" type="text" autocomplete="off" placeholder="Azure: https://리소스.openai.azure.com / 호환 서버: https://host/v1" />
            </div>
            <div id="modelSelectField">
              <label for="llmModelSelect">세부 모델</label>
              <select id="llmModelSelect"></select>
            </div>
            <div id="llmModelCustomField">
              <label for="llmModel">직접 입력 모델명 또는 배포명</label>
              <input id="llmModel" type="text" autocomplete="off" placeholder="OpenAI: gpt-5.5 / Azure: chat deployment name" />
            </div>
            <div id="embeddingModelField">
              <label for="embeddingModel">Embedding 모델 또는 배포명</label>
              <input id="embeddingModel" type="text" autocomplete="off" placeholder="OpenAI: text-embedding-3-small / Azure: embedding deployment name" />
            </div>
            <div id="azureVersionField">
              <label for="azureApiVersion">Azure API Version</label>
              <input id="azureApiVersion" type="text" autocomplete="off" value="2024-10-21" />
            </div>
          </div>
          <div>
            <label for="llmApiKey">API Key</label>
            <input id="llmApiKey" type="password" autocomplete="off" placeholder="토픽 임베딩/감정/해석 실행 시에만 전송, 저장하지 않음" />
          </div>
          <button id="runBtn" class="primary" disabled>분석 실행</button>
          <div id="runStatus" class="status"></div>
          <div class="row">
            <button id="excelBtn" class="secondary" disabled>Excel 생성</button>
            <button id="wordBtn" class="secondary" disabled>Word 생성</button>
            <button id="powerpointBtn" class="secondary" disabled>PowerPoint 생성</button>
          </div>
          <div id="downloadLinks" class="row"></div>
          <button id="reviewBtn" class="secondary" disabled>담당자 검토 기록</button>
          <div id="reviewStatus" class="status">분석 후 담당자 검토를 기록하세요.</div>
        </div>
      </aside>
      <section>
        <div class="tabs">
          <button class="tab active" data-tab="profile">컬럼 프로파일</button>
          <button class="tab" data-tab="recommendation">토픽 권장안</button>
          <button class="tab" data-tab="topics">분석 결과</button>
          <button class="tab" data-tab="history">분석 이력</button>
        </div>
        <div id="profile" class="tab-panel active">
          <div id="profileSummary" class="metrics"></div>
          <div id="profileTable" class="empty">업로드된 데이터가 없습니다.</div>
        </div>
        <div id="recommendation" class="tab-panel">
          <div id="recommendationSummary" class="metrics"></div>
          <div id="recommendationExplanation"></div>
          <div id="candidateTable" class="empty">분석 결과가 없습니다.</div>
        </div>
        <div id="topics" class="tab-panel">
          <div id="topicList" class="empty">토픽 결과가 없습니다.</div>
        </div>
        <div id="history" class="tab-panel">
          <div class="row tab-toolbar">
            <div>
              <h2 class="tab-title">분석 이력</h2>
              <div id="historyStatus" class="status">최근 분석 이력을 확인 중입니다.</div>
            </div>
            <button id="historyRefreshBtn" class="secondary" type="button">새로고침</button>
          </div>
          <div class="trust-note">분석 결과 삭제 시 해당 run과 생성된 export 파일을 정리합니다. 원본 삭제는 연결된 모든 run과 export도 함께 삭제합니다. 내려받아 복사한 파일은 자동으로 삭제되지 않습니다.</div>
          <div id="historyList" class="empty">최근 분석 이력을 확인 중입니다.</div>
        </div>
      </section>
    </div>
  </main>
  <script>
    const state = { datasetId: null, profile: null, runId: null, recommendation: null, historyLoaded: false };
    const $ = (id) => document.getElementById(id);
    const fmt = (value) => value === null || value === undefined || value === "" ? "-" : String(value);
    const pct = (value) => `${Math.round((Number(value) || 0) * 100)}%`;
    const MODEL_OPTIONS = __MODEL_OPTIONS__;

    document.querySelectorAll(".tab").forEach((button) => {
      button.addEventListener("click", () => {
        activateTab(button.dataset.tab);
      });
    });

    $("uploadBtn").addEventListener("click", uploadDataset);
    $("runBtn").addEventListener("click", runAnalysis);
    $("excelBtn").addEventListener("click", () => createExport("excel"));
    $("wordBtn").addEventListener("click", () => createExport("word"));
    $("powerpointBtn").addEventListener("click", () => createExport("powerpoint"));
    $("reviewBtn").addEventListener("click", recordHumanReview);
    $("historyRefreshBtn").addEventListener("click", () => loadRecentProjects(true));
    $("llmProvider").addEventListener("change", updateProviderSettings);
    $("llmModelSelect").addEventListener("change", syncModelSelection);

    checkHealth();
    loadRecentProjects();
    updateProviderSettings();

    async function checkHealth() {
      try {
        const res = await fetch("/health");
        if (!res.ok) throw new Error("health failed");
        $("apiState").textContent = "API 정상";
        $("apiState").className = "pill";
      } catch (err) {
        $("apiState").textContent = "API 오류";
        $("apiState").className = "pill warn";
      }
    }

    async function loadRecentProjects(force = false) {
      if (state.historyLoaded && !force) return;
      state.historyLoaded = true;
      setBusy("historyRefreshBtn", true);
      setStatus("historyStatus", "최근 분석 이력 확인 중", "");
      setHistoryEmpty("최근 분석 이력을 확인 중입니다.");
      try {
        const res = await fetch("/projects/recent");
        if (res.status === 404) {
          setStatus("historyStatus", "이력 API가 아직 연결되지 않았습니다.", "");
          setHistoryEmpty("최근 분석 이력이 없습니다.");
          return;
        }
        const payload = await readJson(res);
        const projects = normalizeRecentProjects(payload);
        renderHistory(projects);
        setStatus("historyStatus", projects.length ? `${projects.length}건의 최근 분석` : "최근 분석 이력이 없습니다.", projects.length ? "ok" : "");
      } catch (err) {
        setStatus("historyStatus", "최근 분석 이력을 불러올 수 없습니다.", "");
        setHistoryEmpty("최근 분석 이력이 없습니다.");
      } finally {
        setBusy("historyRefreshBtn", false);
      }
    }

    async function uploadDataset() {
      const file = $("fileInput").files[0];
      if (!file) return setStatus("uploadStatus", "파일을 선택하세요.", "error");
      setBusy("uploadBtn", true);
      setStatus("uploadStatus", "업로드 중", "");
      try {
        const url = `/datasets/upload?filename=${encodeURIComponent(file.name)}`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": file.type || "application/octet-stream" },
          body: file
        });
        const payload = await readJson(res);
        state.datasetId = payload.dataset_id;
        state.profile = payload.profile;
        state.runId = null;
        state.recommendation = null;
        renderProfile(payload.profile);
        setStatus("uploadStatus", `업로드 완료: ${payload.profile.row_count}행, ${payload.profile.column_count}컬럼`, "ok");
        $("runBtn").disabled = false;
        $("excelBtn").disabled = true;
        $("wordBtn").disabled = true;
        $("powerpointBtn").disabled = true;
        $("reviewBtn").disabled = true;
        setStatus("reviewStatus", "분석 후 담당자 검토를 기록하세요.", "");
        $("downloadLinks").innerHTML = "";
      } catch (err) {
        setStatus("uploadStatus", err.message, "error");
      } finally {
        setBusy("uploadBtn", false);
      }
    }

    async function runAnalysis() {
      if (!state.datasetId) return;
      const selectedProvider = $("llmProvider").value;
      if (selectedProvider && !$("externalTransferConfirmed").checked) {
        return setStatus("runStatus", "외부 AI로 전송될 수 있는 데이터와 조직 정책을 확인한 뒤 체크해 주세요.", "error");
      }
      setBusy("runBtn", true);
      setStatus("runStatus", "분석 중", "");
      try {
        const body = {
          dataset_id: state.datasetId,
          project_name: $("projectName").value || "Survey Insight Project",
          text_column: $("textColumn").value || null,
          group_columns: Array.from($("groupColumns").selectedOptions).map((option) => option.value),
          llm_provider: selectedProvider || null,
          llm_api_key: $("llmApiKey").value || null,
          llm_base_url: $("llmBaseUrl").value || null,
          llm_model: selectedChatModel(),
          embedding_model: $("llmProvider").value === "claude" ? null : $("embeddingModel").value || null,
          azure_api_version: $("azureApiVersion").value || null,
          external_transfer_confirmed: selectedProvider ? $("externalTransferConfirmed").checked : null,
        };
        $("llmApiKey").value = "";
        const res = await fetch("/model-runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        const payload = await readJson(res);
        state.runId = payload.run_id;
        state.recommendation = payload.recommendation;
        renderRecommendation(payload.recommendation);
        renderTopics(payload.recommendation.recommended.topics || []);
        activateTab("recommendation");
        const privacyCount = Number(payload.privacy_review_flag_count || 0);
        const privacyMessage = privacyCount ? ` · 개인정보 문맥 검토 필요 ${privacyCount}건` : "";
        setStatus("runStatus", `분석 완료: ${payload.recommendation.mode}, N=${payload.recommendation.valid_response_count}${privacyMessage}`, "ok");
        $("excelBtn").disabled = false;
        $("wordBtn").disabled = false;
        $("powerpointBtn").disabled = false;
        $("reviewBtn").disabled = false;
        setStatus("reviewStatus", "아직 담당자 검토가 기록되지 않았습니다.", "");
      } catch (err) {
        setStatus("runStatus", err.message, "error");
      } finally {
        setBusy("runBtn", false);
      }
    }

    async function createExport(type) {
      if (!state.runId) return;
      const button = type === "excel" ? $("excelBtn") : type === "word" ? $("wordBtn") : $("powerpointBtn");
      setBusy(button.id, true);
      try {
        const res = await fetch("/exports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ run_id: state.runId, type })
        });
        const payload = await readJson(res);
        const a = document.createElement("a");
        a.className = "download-link";
        a.href = payload.download_url;
        a.textContent = type === "excel" ? "Excel 다운로드" : type === "word" ? "Word 다운로드" : "PowerPoint 다운로드";
        $("downloadLinks").appendChild(a);
      } catch (err) {
        setStatus("runStatus", err.message, "error");
      } finally {
        setBusy(button.id, false);
      }
    }

    function renderProfile(profile) {
      $("profileSummary").innerHTML = [
        metric("행", profile.row_count),
        metric("컬럼", profile.column_count),
        metric("헤더 행", Number(profile.header_row_index) + 1),
        metric("자유응답 후보", profile.recommended_text_columns.length)
      ].join("");
      const textSelect = $("textColumn");
      textSelect.innerHTML = "";
      const textCandidates = profile.recommended_text_columns.length ? profile.recommended_text_columns : profile.columns;
      textCandidates.forEach((column) => textSelect.appendChild(new Option(`${column.column_name} (${column.text_score})`, column.column_name)));
      textSelect.disabled = false;
      const groupSelect = $("groupColumns");
      groupSelect.innerHTML = "";
      profile.columns
        .filter((column) => column.detected_type === "Categorical Metadata")
        .slice(0, 12)
        .forEach((column) => {
          const option = new Option(column.column_name, column.column_name);
          option.selected = groupSelect.options.length < 3;
          groupSelect.appendChild(option);
        });
      groupSelect.disabled = groupSelect.options.length === 0;
      const rows = profile.columns.map((column) => `
        <tr>
          <td>${escapeHtml(column.column_name)}</td>
          <td>${escapeHtml(column.detected_type)}</td>
          <td>${column.confidence}</td>
          <td>${column.text_score}</td>
          <td>${pct(column.missing_rate)}</td>
          <td>${escapeHtml((column.reasons || []).join(" "))}</td>
        </tr>
      `).join("");
      $("profileTable").className = "table-wrap";
      $("profileTable").innerHTML = `
        <table>
          <thead><tr><th>컬럼</th><th>타입</th><th>신뢰도</th><th>TextScore</th><th>결측</th><th>근거</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    async function recordHumanReview() {
      if (!state.runId) return;
      const reviewer = window.prompt("검토자 이름 또는 내부 식별자를 입력하세요.", "");
      if (!reviewer || !reviewer.trim()) return;
      const notes = window.prompt("검토 메모를 입력하세요. 자동 라벨·대표 응답·개인정보를 확인했는지 기록하세요.", "") || "";
      const confirmed = window.confirm("현재 권장 토픽 수, 라벨, 대표 응답과 개인정보 표시를 검토 완료로 기록할까요?");
      if (!confirmed) return;
      setBusy("reviewBtn", true);
      try {
        const res = await fetch(`/model-runs/${encodeURIComponent(state.runId)}/edits`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            edit_type: "record_review",
            user_id: reviewer.trim(),
            payload: { decision: "approved", notes }
          })
        });
        const payload = await readJson(res);
        const review = payload.human_review || {};
        setStatus("reviewStatus", `검토 기록 완료: ${review.reviewer || reviewer.trim()}`, "ok");
      } catch (err) {
        setStatus("reviewStatus", `검토 기록 실패: ${err.message}`, "error");
      } finally {
        setBusy("reviewBtn", false);
      }
    }

    function activateTab(tabName) {
      document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item.dataset.tab === tabName));
      document.querySelectorAll(".tab-panel").forEach((item) => item.classList.toggle("active", item.id === tabName));
      if (tabName === "history" && !state.historyLoaded) loadRecentProjects();
    }

    function updateProviderSettings() {
      const provider = $("llmProvider").value;
      $("externalTransferConfirmed").checked = false;
      $("providerSettings").style.display = provider ? "grid" : "none";
      $("baseUrlField").style.display = provider === "azure_openai" || provider === "custom" ? "block" : "none";
      $("azureVersionField").style.display = provider === "azure_openai" ? "block" : "none";
      $("embeddingModelField").style.display = provider === "claude" ? "none" : "block";
      populateModelOptions(provider);
      if (provider === "openai") {
        $("llmModel").placeholder = "gpt-5.5";
        $("embeddingModel").placeholder = "text-embedding-3-small";
      } else if (provider === "gemini") {
        $("llmModel").placeholder = "gemini-3.5-flash";
        $("embeddingModel").placeholder = "gemini-embedding-001";
      } else if (provider === "claude") {
        $("llmModel").placeholder = "claude-sonnet-5";
      } else if (provider === "azure_openai") {
        $("llmModel").placeholder = "Azure chat deployment name";
        $("embeddingModel").placeholder = "Azure embedding deployment name";
      } else if (provider === "custom") {
        $("llmModel").placeholder = "OpenAI-compatible chat model";
        $("embeddingModel").placeholder = "OpenAI-compatible embedding model";
      }
    }

    function populateModelOptions(provider) {
      const options = MODEL_OPTIONS[provider] || [];
      $("modelSelectField").style.display = options.length ? "block" : "none";
      $("llmModelSelect").innerHTML = "";
      options.forEach(([value, label]) => {
        $("llmModelSelect").appendChild(new Option(label, value));
      });
      if (options.length) {
        $("llmModelSelect").appendChild(new Option("직접 입력", "__custom"));
        $("llmModelSelect").value = options[0][0];
      }
      syncModelSelection();
    }

    function syncModelSelection() {
      const provider = $("llmProvider").value;
      const hasPreset = Boolean(MODEL_OPTIONS[provider]);
      const useCustom = !hasPreset || $("llmModelSelect").value === "__custom";
      $("llmModelCustomField").style.display = provider && useCustom ? "block" : "none";
      if (hasPreset && !useCustom) $("llmModel").value = "";
    }

    function selectedChatModel() {
      const provider = $("llmProvider").value;
      if (MODEL_OPTIONS[provider] && $("llmModelSelect").value !== "__custom") {
        return $("llmModelSelect").value || null;
      }
      return $("llmModel").value || null;
    }

    function renderRecommendation(rec) {
      const wider = rec.wider ? `${rec.wider.topic_count}개` : "-";
      const detailed = rec.detailed ? `${rec.detailed.topic_count}개` : "-";
      $("recommendationSummary").innerHTML = [
        metric("모드", rec.mode),
        metric("유효 응답", rec.valid_response_count),
        metric("권장 토픽 수", `${rec.recommended.topic_count}개`),
        metric("대안", `${wider} / ${detailed}`)
      ].join("");
      renderRecommendationExplanation(rec);
      const rows = (rec.candidates || []).map((candidate) => `
        <tr>
          <td>${candidate.rank}</td>
          <td>${candidate.topic_count}</td>
          <td>${candidate.score}</td>
          <td>${escapeHtml(candidate.params.engine)}</td>
          <td>${candidate.params.quality_gate_passed === true ? "통과" : (candidate.params.quality_gate_passed === false ? `보류: ${escapeHtml((candidate.params.quality_gate_reasons || []).join(" · "))}` : "이전 결과")}</td>
          <td>${candidate.metrics.stability}</td>
          <td>${candidate.metrics.coherence}</td>
          <td>${candidate.metrics.semantic_quality}</td>
          <td>${candidate.metrics.coverage}</td>
        </tr>
      `).join("");
      const warnings = [...(rec.warnings || []), ...(rec.quality_warnings || [])]
        .map((warning) => `<span class="pill warn">${escapeHtml(warning)}</span>`)
        .join(" ");
      $("candidateTable").className = "stack";
      $("candidateTable").innerHTML = `
        <details class="detail-panel">
          <summary>전문가용 세부 근거 보기</summary>
          <div class="row">${warnings}</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>순위</th><th>토픽 수</th><th>복합 평가</th><th>엔진</th><th>구조 관문</th><th>군집 품질 종합점수</th><th>토픽 해석 가능성 점수</th><th>군집 분리도</th><th>분석 포함률</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </details>
      `;
    }

    function renderRecommendationExplanation(rec) {
      const recommended = rec.recommended || {};
      const topicCount = recommended.topic_count || 0;
      const summary = firstValue(rec, ["plain_language_summary", "summary_plain_language"], firstValue(recommended, ["plain_language_summary", "summary_plain_language"], ""));
      const reason = firstValue(rec, ["topic_count_explanation", "recommendation_reason", "topic_count_reason", "why_recommended"], firstValue(recommended, ["recommendation_reason", "topic_count_reason", "why_recommended"], ""));
      const warnings = [...(rec.warnings || []), ...(rec.quality_warnings || [])].filter(Boolean);
      const topics = recommended.topics || [];
      const metrics = recommended.metrics || {};
      const engine = engineLabel((recommended.params || {}).engine || "unknown");
      const priorityTopics = [...topics]
        .sort((a, b) => priorityScore(b) - priorityScore(a));
      $("recommendationExplanation").innerHTML = `
        <div class="dashboard">
          <section class="hero-insight">
            <div>
              <p class="eyebrow">담당자가 먼저 볼 결론</p>
              <div class="hero-number"><strong>${escapeHtml(topicCount)}</strong><span>개 토픽</span></div>
              <div class="meta-line">
                <span class="pill">유효 응답 ${escapeHtml(rec.valid_response_count)}건</span>
                <span class="pill">${escapeHtml(engine)}</span>
                <span class="pill">권장 범위 ${escapeHtml((rec.allowed_topic_range || []).join("-"))}개</span>
              </div>
            </div>
            <div>
              <p class="eyebrow">한 줄 해석</p>
              <p class="hero-copy">${escapeHtml(summary || `${topicCount}개로 나누면 담당자가 읽고 대응하기 가장 무난합니다.`)}</p>
            </div>
          </section>

          <section class="decision-grid">
            ${decisionCard("wide", "더 적게 묶으면", rec.wider ? `${rec.wider.topic_count}개 대안` : "대안 없음", "서로 다른 의견이 한 바구니에 섞일 수 있어 담당 부서와 조치 방향을 나누기 어렵습니다.")}
            ${decisionCard("recommended", "권장안", `${topicCount}개`, "응답끼리는 비슷하게 묶이고 토픽끼리는 비교적 구분되어 담당자가 이름을 붙이고 읽기 쉬운 균형점입니다.")}
            ${decisionCard("detailed", "더 잘게 나누면", rec.detailed ? `${rec.detailed.topic_count}개 대안` : "대안 없음", "세부 차이는 더 보이지만 비슷한 이야기가 쪼개져 전체 흐름을 파악하기 어려울 수 있습니다.")}
          </section>

          <section class="dashboard-section">
            <p class="eyebrow">토픽 수를 정한 이유</p>
            <h3>구조 관문·복합 평가와 별도 안정성 진단을 함께 봤습니다</h3>
            <p>${escapeHtml(reason)}</p>
            <div class="score-grid">
              ${scoreCard("군집 품질 종합점수", metrics.stability, "분리도·키워드 동시출현·크기 균형을 결합한 휴리스틱이며 통계적 안정성이 아닙니다")}
              ${scoreCard("토픽 해석 가능성 점수", metrics.coherence, "상위 키워드가 같은 문서에서 함께 나타나는 정도를 이용한 UMass 방식의 휴리스틱")}
              ${scoreCard("군집 분리도", metrics.semantic_quality, "노이즈 응답을 제외한 cosine silhouette의 음수를 0으로 제한한 값")}
              ${scoreCard("분석 포함률", metrics.coverage, "노이즈로 제외되지 않고 토픽에 배정된 유효 응답 비율")}
              ${scoreCard("토픽 키워드 다양성", metrics.diversity, "토픽별 상위 키워드가 서로 중복되지 않는 정도")}
              ${scoreCard("라벨 해석 가능성", metrics.labelability, "키워드와 대표 응답이 라벨 검토에 충분한지 보는 휴리스틱")}
              ${scoreCard("토픽 크기 균형", metrics.balance, "한 토픽의 과도한 지배 여부를 엔트로피 기반으로 점검한 값")}
              ${metrics.resampling_stability !== undefined ? scoreCard("부분표본 일치도", metrics.resampling_stability, "선정 후보를 80% 층화 부분표본으로 3회 다시 적합한 ARI 평균이며 권장 점수에는 포함되지 않습니다") : ""}
            </div>
          </section>

          <section class="dashboard-section">
            <p class="eyebrow">우선 확인할 토픽</p>
            <h3>전체 토픽을 처리 우선도 신호순으로 정렬</h3>
            <div class="priority-list">
              ${priorityTopics.length ? priorityTopics.map(priorityCard).join("") : `<div class="empty">표시할 토픽이 없습니다.</div>`}
            </div>
          </section>

          <section class="dashboard-section">
            <p class="eyebrow">전체 토픽 표</p>
            <h3>권장안의 모든 토픽</h3>
            <p>위 카드와 같은 토픽을 표 형태로 다시 정리했습니다. 빠르게 비교할 때 사용하세요.</p>
            ${topicTable(topics)}
          </section>

          ${warnings.length ? `
            <section class="dashboard-section">
              <p class="eyebrow">읽을 때 주의할 점</p>
              <div class="meta-line">${warnings.map((warning) => `<span class="pill warn">${escapeHtml(warning)}</span>`).join("")}</div>
            </section>
          ` : ""}
        </div>
      `;
    }

    function decisionCard(kind, label, value, text) {
      return `
        <article class="decision-card ${kind}">
          <p class="eyebrow">${escapeHtml(label)}</p>
          <h3>${escapeHtml(value)}</h3>
          <p>${escapeHtml(text)}</p>
        </article>
      `;
    }

    function scoreCard(label, value, description) {
      const score = Math.max(0, Math.min(1, Number(value) || 0));
      return `
        <article class="score-card">
          <div class="score-head"><span>${escapeHtml(label)}</span><span>${score.toFixed(2)}</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:${Math.round(score * 100)}%"></div></div>
          <p>${escapeHtml(description)}</p>
        </article>
      `;
    }

    function priorityCard(topic) {
      const tone = sentimentTone(topic.sentiment_label);
      const rep = (topic.representative_responses || [])[0] || "";
      return `
        <article class="priority-item ${tone}">
          <div class="priority-body">
            <div class="priority-head">
              <h4>${escapeHtml(topic.topic_id)} ${escapeHtml(topic.label)}</h4>
              <div class="meta-line">
                <span class="pill">${escapeHtml(topic.count)}건 · ${pct(topic.share)}</span>
                <span class="pill ${tone === "negative" ? "warn" : ""}">${escapeHtml(sentimentLabel(topic.sentiment_label))} · 처리 우선도 ${Number(topic.urgency_score || 0).toFixed(2)}</span>
              </div>
            </div>
            <p>${escapeHtml(topic.plain_language_summary || topic.summary || "")}</p>
            ${sentimentDetail(topic)}
            ${topic.suggested_action ? `<p><strong>다음 행동:</strong> ${escapeHtml(topic.suggested_action)}</p>` : ""}
            ${rep ? `<p><strong>대표 의견:</strong> ${escapeHtml(shorten(rep, 120))}</p>` : ""}
          </div>
        </article>
      `;
    }

    function sentimentDetail(topic, compact = false) {
      const tone = sentimentTone(topic.sentiment_label);
      const score = Number(topic.sentiment_score || 0);
      const urgency = Math.max(0, Math.min(1, Number(topic.urgency_score || 0)));
      const strength = Math.round(Math.abs(score) * 100);
      const urgencyWidth = Math.round(urgency * 100);
      const evidence = (topic.sentiment_evidence || []).slice(0, compact ? 4 : 6);
      const plain = topic.sentiment_plain_language || sentimentFallback(topic);
      const scoreText = score > 0.05 ? `긍정 어휘 신호 ${score.toFixed(2)}` : score < -0.05 ? `부정 어휘 신호 ${score.toFixed(2)}` : `중립 신호 ${score.toFixed(2)}`;
      return `
        <div class="sentiment-detail">
          <div class="meta-line">
            <span class="pill ${tone === "negative" ? "warn" : ""}">${escapeHtml(sentimentLabel(topic.sentiment_label))}</span>
            <span class="pill">${escapeHtml(sentimentMethodLabel(topic.sentiment_method))}</span>
          </div>
          <p>${escapeHtml(plain)}</p>
          <div class="sentiment-bars">
            <div class="sentiment-meter">
              <span>어휘 극성 신호</span>
              <div class="sentiment-meter-track"><div class="sentiment-meter-fill ${tone}" style="width:${strength}%"></div></div>
              <span>${escapeHtml(scoreText)}</span>
            </div>
            <div class="sentiment-meter">
              <span>처리 우선도</span>
              <div class="sentiment-meter-track"><div class="sentiment-meter-fill ${urgency >= 0.5 ? "negative" : tone}" style="width:${urgencyWidth}%"></div></div>
              <span>${urgency.toFixed(2)}</span>
            </div>
          </div>
          ${evidence.length ? `<div class="sentiment-evidence">${evidence.map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join("")}</div>` : ""}
        </div>
      `;
    }

    function topicTable(topics) {
      if (!topics.length) return `<div class="empty">표시할 토픽이 없습니다.</div>`;
      const rows = topics.map((topic) => {
        const tone = sentimentTone(topic.sentiment_label);
        const rep = (topic.representative_responses || [])[0] || "";
        const managerText = topic.plain_language_summary || topic.summary || "";
        const action = topic.suggested_action || "";
        const keywords = (topic.keywords || []).slice(0, 5).join(", ");
        return `
          <tr>
            <td class="topic-name">
              ${escapeHtml(topic.topic_id)} ${escapeHtml(topic.label)}
              <div class="meta-line">
                <span class="pill">${escapeHtml(topic.count)}건 · ${pct(topic.share)}</span>
                <span class="pill ${tone === "negative" ? "warn" : ""}">${escapeHtml(sentimentLabel(topic.sentiment_label))}</span>
              </div>
            </td>
            <td>${escapeHtml(keywords || "-")}</td>
            <td class="topic-sentiment">${sentimentDetail(topic, true)}</td>
            <td class="topic-action">
              <strong>해석</strong><br>${escapeHtml(managerText || "-")}
              ${action ? `<br><strong>다음 행동</strong><br>${escapeHtml(action)}` : ""}
            </td>
            <td class="topic-evidence">${rep ? escapeHtml(shorten(rep, 140)) : "-"}</td>
          </tr>
        `;
      }).join("");
      return `
        <div class="topic-table-wrap">
          <table class="topic-table">
            <thead>
              <tr>
                <th>분야</th>
                <th>핵심어</th>
                <th>감정 신호 상세</th>
                <th>담당자용 설명</th>
                <th>대표 의견</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
    }

    function priorityScore(topic) {
      return (Number(topic.urgency_score || 0) * 0.55) + (Number(topic.share || 0) * 0.45);
    }

    function sentimentFallback(topic) {
      const label = sentimentLabel(topic.sentiment_label);
      const evidence = (topic.sentiment_evidence || []).slice(0, 3).join(", ");
      const suffix = evidence ? ` 근거 표현은 ${evidence}입니다.` : " 뚜렷한 근거 표현은 많지 않습니다.";
      return `${label} 방향으로 분류했고 처리 우선도는 ${Number(topic.urgency_score || 0).toFixed(2)}입니다.${suffix}`;
    }

    function sentimentMethodLabel(method) {
      const value = String(method || "").toLowerCase();
      if (value.includes("openai")) return "OpenAI 근거 보강";
      if (value.includes("gemini")) return "Gemini 근거 보강";
      if (value.includes("claude")) return "Claude 근거 보강";
      if (value.includes("rule")) return "규칙·어휘 기반 신호";
      return value || "분석 방식 미상";
    }

    function sentimentTone(label) {
      const value = String(label || "neutral").toLowerCase();
      return ["positive", "negative", "mixed"].includes(value) ? value : "neutral";
    }

    function sentimentLabel(label) {
      return {
        positive: "긍정",
        negative: "개선 필요",
        mixed: "긍정/부정 혼재",
        neutral: "중립",
      }[String(label || "neutral").toLowerCase()] || "중립";
    }

    function engineLabel(engine) {
      return {
        dbscan_lsa_natural: "자연 군집 탐색",
        kmeans: "KMeans 군집",
        agglomerative: "계층 군집",
        nmf: "NMF 토픽모델",
        lda: "LDA 토픽모델",
        openai_embedding_kmeans: "OpenAI 의미 임베딩",
        openai_embedding_agglomerative: "OpenAI 의미 임베딩",
        openai_embedding_dbscan: "OpenAI 의미 임베딩",
        gemini_embedding_kmeans: "Gemini 의미 임베딩",
        gemini_embedding_agglomerative: "Gemini 의미 임베딩",
        gemini_embedding_dbscan: "Gemini 의미 임베딩",
        azure_openai_embedding_kmeans: "Azure OpenAI 의미 임베딩",
        azure_openai_embedding_agglomerative: "Azure OpenAI 의미 임베딩",
        azure_openai_embedding_dbscan: "Azure OpenAI 의미 임베딩",
      }[String(engine || "")] || String(engine || "모델 비교");
    }

    function renderTopics(topics) {
      if (!topics.length) {
        $("topicList").className = "empty";
        $("topicList").textContent = "토픽 결과가 없습니다.";
        return;
      }
      $("topicList").className = "topic-grid";
      $("topicList").innerHTML = topics.map((topic) => `
        <article class="topic">
          <div class="row">
            <h3>${escapeHtml(topic.topic_id)} ${escapeHtml(topic.label)}</h3>
            <span class="pill">${topic.count}건 · ${pct(topic.share)}</span>
            <span class="pill ${topic.sentiment_label === "negative" ? "warn" : ""}">${escapeHtml(topic.sentiment_label || "neutral")} · 처리 우선도 ${Number(topic.urgency_score || 0).toFixed(2)}</span>
            <span class="pill">${escapeHtml(topic.sentiment_method || "unknown")}</span>
          </div>
          <p>${escapeHtml(topic.summary)}</p>
          ${topic.plain_language_summary ? `<h4>쉽게 읽는 해석</h4><p class="plain-note">${escapeHtml(topic.plain_language_summary)}</p>` : ""}
          ${topic.suggested_action ? `<h4>대응 방안</h4><p class="plain-note">${escapeHtml(topic.suggested_action)}</p>` : ""}
          ${topic.sentiment_plain_language ? `<h4>감정 해석</h4><p class="plain-note">${escapeHtml(topic.sentiment_plain_language)}</p>` : ""}
          <p>${escapeHtml((topic.keywords || []).join(", "))}</p>
          ${topic.sentiment_evidence && topic.sentiment_evidence.length ? `<p>감정 근거: ${escapeHtml(topic.sentiment_evidence.join(", "))}</p>` : ""}
          <ol class="reps">${(topic.representative_responses || []).map((rep) => `<li>${escapeHtml(rep)}</li>`).join("")}</ol>
        </article>
      `).join("");
    }

    function normalizeRecentProjects(payload) {
      const projects = Array.isArray(payload)
        ? payload
        : (payload.projects || payload.items || payload.recent || []);
      return Array.isArray(projects) ? projects : [];
    }

    function renderHistory(projects) {
      if (!projects.length) {
        setHistoryEmpty("최근 분석 이력이 없습니다.");
        return;
      }
      $("historyList").className = "history-list";
      $("historyList").innerHTML = projects.map((project) => {
        const record = project || {};
        const title = firstValue(record, ["project_name", "name", "title"], record.project?.name || "이름 없는 분석");
        const createdAt = firstValue(record, ["created_at", "createdAt", "updated_at"], null);
        const mode = firstValue(record, ["mode"], record.recommendation?.mode || null);
        const validCount = firstValue(record, ["valid_response_count"], record.recommendation?.valid_response_count || null);
        const topicCount = firstValue(record, ["topic_count", "recommended_topic_count"], record.recommendation?.recommended?.topic_count || null);
        const reviewStatus = firstValue(record, ["human_review_status"], "not_reviewed");
        const runId = firstValue(record, ["run_id", "id"], null);
        const datasetName = firstValue(record, ["dataset_name", "source_name", "filename"], null);
        const summary = firstValue(record, ["summary", "description"], "");
        const meta = [
          formatDate(createdAt),
          datasetName,
          mode ? `모드 ${mode}` : null,
          validCount !== null ? `N=${validCount}` : null,
          topicCount !== null ? `토픽 ${topicCount}` : null,
          `검토 ${reviewStatus}`,
          runId ? `Run ${runId}` : null
        ].filter(Boolean);
        return `
          <article class="history-item">
            <h3>${escapeHtml(title)}</h3>
            <div class="history-meta">${meta.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
            ${summary ? `<p class="history-summary">${escapeHtml(summary)}</p>` : ""}
            <div class="history-actions">
              ${runId ? `<button class="secondary" type="button" data-delete-run="${escapeAttr(runId)}" data-delete-title="${escapeAttr(title)}">분석 결과 삭제</button>` : ""}
              ${record.dataset_id ? `<button class="danger" type="button" data-delete-dataset="${escapeAttr(record.dataset_id)}" data-delete-title="${escapeAttr(title)}">원본·연결 분석 삭제</button>` : ""}
            </div>
          </article>
        `;
      }).join("");
      document.querySelectorAll("[data-delete-run]").forEach((button) => {
        button.addEventListener("click", () => deleteRun(button.dataset.deleteRun, button.dataset.deleteTitle));
      });
      document.querySelectorAll("[data-delete-dataset]").forEach((button) => {
        button.addEventListener("click", () => deleteDatasetWithRuns(button.dataset.deleteDataset, button.dataset.deleteTitle));
      });
    }

    async function deleteRun(runId, title) {
      if (!runId) return;
      const confirmed = window.confirm(`'${title || "이 분석"}'의 분석 결과와 서버가 생성한 export 파일을 삭제할까요? 업로드 원본은 남습니다. 이 작업은 되돌릴 수 없습니다.`);
      if (!confirmed) return;
      try {
        await readJson(await fetch(`/model-runs/${encodeURIComponent(runId)}`, { method: "DELETE" }));
        if (state.runId === runId) clearCurrentRun();
        state.historyLoaded = false;
        await loadRecentProjects(true);
        setStatus("historyStatus", "분석 결과와 연결된 export 파일을 삭제했습니다.", "ok");
      } catch (err) {
        setStatus("historyStatus", `삭제하지 못했습니다. ${err.message}`, "error");
      }
    }

    async function deleteDatasetWithRuns(datasetId, title) {
      if (!datasetId) return;
      const confirmed = window.confirm(`'${title || "이 프로젝트"}'의 업로드 원본, 연결된 모든 분석 결과와 서버 export 파일을 함께 삭제할까요? 내려받은 파일은 삭제되지 않으며 이 작업은 되돌릴 수 없습니다.`);
      if (!confirmed) return;
      try {
        await readJson(await fetch(`/datasets/${encodeURIComponent(datasetId)}?delete_runs=true`, { method: "DELETE" }));
        if (state.datasetId === datasetId) {
          state.datasetId = null;
          state.profile = null;
          clearCurrentRun();
          $("runBtn").disabled = true;
          setStatus("uploadStatus", "업로드 원본과 연결 분석을 삭제했습니다.", "ok");
        }
        state.historyLoaded = false;
        await loadRecentProjects(true);
        setStatus("historyStatus", "업로드 원본과 연결된 분석·export 파일을 삭제했습니다.", "ok");
      } catch (err) {
        setStatus("historyStatus", `삭제하지 못했습니다. ${err.message}`, "error");
      }
    }

    function clearCurrentRun() {
      state.runId = null;
      state.recommendation = null;
      $("excelBtn").disabled = true;
      $("wordBtn").disabled = true;
      $("powerpointBtn").disabled = true;
      $("reviewBtn").disabled = true;
      $("downloadLinks").innerHTML = "";
      setStatus("reviewStatus", "분석 후 담당자 검토를 기록하세요.", "");
    }

    function setHistoryEmpty(message) {
      $("historyList").className = "empty";
      $("historyList").textContent = message;
    }

    function firstValue(record, keys, fallback = null) {
      for (const key of keys) {
        if (!record || record[key] === undefined || record[key] === null || record[key] === "") {
          continue;
        }
        if (Array.isArray(record[key]) && record[key].length === 0) {
          continue;
        }
        {
          return record[key];
        }
      }
      return fallback;
    }

    function formatDate(value) {
      if (!value) return null;
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString("ko-KR");
    }

    function metric(label, value) {
      return `<div class="metric"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div></div>`;
    }

    function setBusy(id, busy) {
      const el = $(id);
      el.disabled = busy;
    }

    function setStatus(id, message, kind) {
      const el = $(id);
      el.textContent = message;
      el.className = `status ${kind || ""}`;
    }

    async function readJson(res) {
      const text = await res.text();
      let payload = {};
      try { payload = text ? JSON.parse(text) : {}; } catch (_) {}
      if (!res.ok) {
        const detail = typeof payload.detail === "object" ? payload.detail?.message : payload.detail;
        const safeMessage = res.status === 404
          ? "요청한 데이터를 찾을 수 없습니다."
          : res.status === 409
            ? (detail || "연결된 데이터가 있어 현재 요청을 완료할 수 없습니다.")
            : "요청을 처리하지 못했습니다. 입력과 설정을 확인해 주세요.";
        throw new Error(safeMessage);
      }
      return payload;
    }

    function escapeHtml(value) {
      return fmt(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll("`", "&#096;");
    }

    function shorten(value, limit) {
      const text = fmt(value).replace(/\s+/g, " ").trim();
      if (text.length <= limit) return text;
      return `${text.slice(0, Math.max(0, limit - 3)).trim()}...`;
    }
  </script>
</body>
</html>"""
    return html.replace("__MODEL_OPTIONS__", json.dumps(ui_chat_presets(), ensure_ascii=False))
