const state = {
  config: null,
  samples: [],
  predictions: { agy: new Map(), jev: new Map() },
  summaries: { agy: null, jev: null },
  running: false,
  toastTimer: null
};

const elements = {
  systemStatus: document.querySelector("#system-status"),
  agyModel: document.querySelector("#agy-model"),
  batchSize: document.querySelector("#batch-size"),
  concurrency: document.querySelector("#concurrency"),
  runBoth: document.querySelector("#run-both"),
  runAgy: document.querySelector("#run-agy"),
  runJev: document.querySelector("#run-jev"),
  resultsBody: document.querySelector("#results-body"),
  toast: document.querySelector("#toast")
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message, isError = false) {
  clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.classList.add("show");
  state.toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 4500);
}

function predictionMarkup(method, id) {
  const prediction = state.predictions[method].get(id);
  if (!prediction) return '<span class="tag pending">대기</span>';
  const confidence = prediction.confidence == null ? "" : `<span class="prediction-meta">${(prediction.confidence * 100).toFixed(1)}%</span>`;
  return `<span class="tag ${prediction.prediction}">${escapeHtml(prediction.prediction)}</span>${confidence}`;
}

function routeMarkup(sample) {
  const jev = state.predictions.jev.get(sample.id);
  const agy = state.predictions.agy.get(sample.id);
  const route = jev?.route || agy?.route;
  if (!route) return '<span class="tag pending">—</span>';
  const labelClass = route === "allow" ? "none" : route === "review" ? "offensive" : "hate";
  return `<span class="tag ${labelClass}">${escapeHtml(route)}</span>`;
}

function renderRows() {
  elements.resultsBody.innerHTML = state.samples.map((sample) => `
    <tr data-id="${escapeHtml(sample.id)}">
      <td><span class="sample-id">${escapeHtml(sample.id)}</span></td>
      <td class="comment-cell">
        <span class="news-title">${escapeHtml(sample.news_title)}</span>
        ${escapeHtml(sample.comments)}
      </td>
      <td><span class="tag ${escapeHtml(sample.hate)}">${escapeHtml(sample.hate)}</span></td>
      <td data-cell="agy">${predictionMarkup("agy", sample.id)}</td>
      <td data-cell="jev">${predictionMarkup("jev", sample.id)}</td>
      <td data-cell="route">${routeMarkup(sample)}</td>
    </tr>
  `).join("");
}

function updateRow(id) {
  const row = elements.resultsBody.querySelector(`tr[data-id="${CSS.escape(id)}"]`);
  const sample = state.samples.find((item) => item.id === id);
  if (!row || !sample) return;
  row.querySelector('[data-cell="agy"]').innerHTML = predictionMarkup("agy", id);
  row.querySelector('[data-cell="jev"]').innerHTML = predictionMarkup("jev", id);
  row.querySelector('[data-cell="route"]').innerHTML = routeMarkup(sample);
}

function setMethodStatus(method, label, statusClass = "") {
  const element = document.querySelector(`#${method}-status`);
  element.textContent = label;
  element.className = `status-pill ${statusClass}`.trim();
}

function setProgress(method, completed, total = 100) {
  document.querySelector(`#${method}-progress`).style.width = `${Math.min(100, (completed / total) * 100)}%`;
}

function renderSummary(method, summary) {
  state.summaries[method] = summary;
  document.querySelector(`#${method}-time`).textContent = `${(summary.elapsedMs / 1000).toFixed(2)} s`;
  document.querySelector(`#${method}-throughput`).textContent = `${summary.itemsPerSecond.toFixed(2)} /s`;
  document.querySelector(`#${method}-accuracy`).textContent = `${(summary.accuracy * 100).toFixed(1)}%`;
  document.querySelector(`#${method}-f1`).textContent = summary.macroF1.toFixed(3);
  const routes = summary.routeCounts;
  document.querySelector(`#${method}-routes`).innerHTML = `
    <span class="allow">allow ${routes.allow}</span>
    <span class="review">review ${routes.review}</span>
    <span class="block">block ${routes.block}</span>
  `;
  renderComparison();
}

function renderComparison() {
  const { agy, jev } = state.summaries;
  if (!agy || !jev) return;
  const speedup = agy.elapsedMs / jev.elapsedMs;
  const accuracyDelta = (jev.accuracy - agy.accuracy) * 100;
  const accuracyText = `${accuracyDelta >= 0 ? "+" : ""}${accuracyDelta.toFixed(1)}%p`;
  document.querySelector("#comparison-banner strong").textContent =
    `JEV ${speedup.toFixed(1)}× 빠름 · 정확도 차이 ${accuracyText} · 100개 / batch 10 / concurrency 1`;
}

function setControlsDisabled(disabled) {
  state.running = disabled;
  for (const element of [elements.runBoth, elements.runAgy, elements.runJev, elements.agyModel, elements.batchSize, elements.concurrency]) {
    element.disabled = disabled;
  }
}

function runMethod(method) {
  return new Promise((resolve, reject) => {
    state.predictions[method].clear();
    renderRows();
    setMethodStatus(method, "실행 중", "running");
    setProgress(method, 0);

    const params = new URLSearchParams({
      batchSize: elements.batchSize.value,
      concurrency: elements.concurrency.value,
      model: elements.agyModel.value
    });
    const source = new EventSource(`/api/benchmark/${method}/stream?${params}`);

    source.addEventListener("start", () => {
      setMethodStatus(method, "실행 중", "running");
    });

    source.addEventListener("batch", (event) => {
      const payload = JSON.parse(event.data);
      for (const result of payload.results) {
        state.predictions[method].set(result.id, result);
        updateRow(result.id);
      }
      setProgress(method, payload.completed, payload.total);
      setMethodStatus(method, `${payload.completed}/${payload.total}`, "running");
    });

    source.addEventListener("complete", (event) => {
      const payload = JSON.parse(event.data);
      source.close();
      renderSummary(method, payload.summary);
      setProgress(method, 100);
      setMethodStatus(method, "완료", "complete");
      resolve(payload.summary);
    });

    source.addEventListener("failure", (event) => {
      const payload = JSON.parse(event.data);
      source.close();
      setMethodStatus(method, "실패", "failed");
      reject(new Error(payload.message));
    });

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) return;
      source.close();
      setMethodStatus(method, "연결 오류", "failed");
      reject(new Error(`${method.toUpperCase()} 스트림 연결이 끊어졌습니다.`));
    };
  });
}

async function execute(methods) {
  if (state.running) return;
  setControlsDisabled(true);
  try {
    for (const method of methods) {
      await runMethod(method);
    }
    showToast(methods.length === 2 ? "두 벤치마크가 완료되었습니다." : `${methods[0].toUpperCase()} 벤치마크가 완료되었습니다.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setControlsDisabled(false);
  }
}

async function initialize() {
  try {
    const [configResponse, samplesResponse, baselineResponse] = await Promise.all([
      fetch("/api/config"),
      fetch("/api/samples"),
      fetch("/api/baseline")
    ]);
    if (!configResponse.ok || !samplesResponse.ok || !baselineResponse.ok) throw new Error("백엔드 초기화 정보를 가져오지 못했습니다.");
    state.config = await configResponse.json();
    const bundle = await samplesResponse.json();
    const baseline = await baselineResponse.json();
    state.samples = bundle.samples;

    elements.agyModel.innerHTML = state.config.agyModels.map((model) =>
      `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`
    ).join("");
    renderRows();
    renderSummary("agy", baseline.agy);
    renderSummary("jev", baseline.jev);
    setProgress("agy", 100);
    setProgress("jev", 100);
    setMethodStatus("agy", "기준 실행", "complete");
    setMethodStatus("jev", "기준 실행", "complete");

    const services = [
      state.config.agyAvailable ? "AGY ready" : "AGY unavailable",
      state.config.openRouterConfigured ? "JEV ready" : "JEV key missing"
    ];
    elements.systemStatus.textContent = services.join(" · ");
    document.body.classList.add(state.config.agyAvailable && state.config.openRouterConfigured ? "ready" : "error");
    elements.runAgy.disabled = !state.config.agyAvailable;
    elements.runJev.disabled = !state.config.openRouterConfigured;
    elements.runBoth.disabled = !state.config.agyAvailable || !state.config.openRouterConfigured;
  } catch (error) {
    document.body.classList.add("error");
    elements.systemStatus.textContent = "백엔드 연결 실패";
    showToast(error.message, true);
  }
}

elements.runBoth.addEventListener("click", () => execute(["agy", "jev"]));
elements.runAgy.addEventListener("click", () => execute(["agy"]));
elements.runJev.addEventListener("click", () => execute(["jev"]));

initialize();
