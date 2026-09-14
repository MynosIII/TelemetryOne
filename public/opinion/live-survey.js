import { categoricalAssociation, correlationMatrix, surveyRecords, surveyVariables, weightedRanking } from "./survey.js";

const SURVEY_URL = "https://docs.google.com/spreadsheets/d/13p58SpkkGQqmZIS4VREej0Kqhi14y8rQmCkzGmx40QU/gviz/tq?tqx=out:csv&gid=1975671607";
const target = document.querySelector("#live-survey");
const voteFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
const percentFormat = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });
const currentDriverNames = [
  "Lando Norris", "Oscar Piastri", "Charles Leclerc", "Carlos Sainz", "George Russell",
  "Kimi Antonelli", "Pierre Gasly", "Esteban Ocon", "Yuki Tsunoda", "Liam Lawson",
  "Alexander Albon", "Lance Stroll", "Nico Hulkenberg", "Gabriel Bortoleto",
  "Oliver Bearman", "Isack Hadjar", "Franco Colapinto", "Jack Doohan"
];
const variableLabels = {
  country: "Country", gender: "Gender", age: "Age", follows: "Follows F1",
  discovery: "How they found F1", years: "Time as a fan", media: "Media used",
  otherSeries: "Other series", criteria: "GOAT criterion", carWeight: "Car vs. driver weight",
  fairness: "Are title comparisons unfair?", statistics: "Weight given to statistics"
};
const englishValues = new Map([
  ["Femenino", "Female"], ["Masculino", "Male"], ["Sí", "Yes"], ["Esporádicamente", "Occasionally"],
  ["No sigue / solo redes", "Does not follow / social media only"], ["Empezó este año", "Started this year"],
  ["El año pasado", "Last year"], ["2 a 4 años", "2 to 4 years"], ["5 años o más", "5 years or more"],
  ["Redes sociales / memes", "Social media / memes"], ["Piloto de su país", "A driver from their country"],
  ["Tradición familiar / amigos", "Family tradition / friends"], ["Siempre siguió el automovilismo", "Always followed motorsport"],
  ["Ninguna", "None"], ["Otras ocasionalmente", "Other series occasionally"],
  ["Resultados", "Results"], ["Talento más allá del auto", "Talent beyond the car"],
  ["Personalidad / carisma", "Personality / charisma"], ["Escudería / equipo", "Team"],
  ["50% auto / 50% piloto", "50% car / 50% driver"], ["Auto / tecnología", "Car / technology"],
  ["Piloto / talento", "Driver / talent"], ["Sí: el auto distorsiona", "Yes: the car distorts results"],
  ["No: las estadísticas son objetivas", "No: statistics are objective"], ["Casi nada", "Very little"]
]);

let records = [];
let activeVariables = ["age", "follows"];

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[character]);

function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') { field += '"'; index += 1; }
      else if (character === '"') quoted = false;
      else field += character;
    } else if (character === '"') quoted = true;
    else if (character === ",") { row.push(field.trim()); field = ""; }
    else if (character === "\n") { row.push(field.trim()); rows.push(row); row = []; field = ""; }
    else if (character !== "\r") field += character;
  }
  if (field || row.length) { row.push(field.trim()); rows.push(row); }
  return rows.filter((values) => values.some(Boolean));
}

function colorFor(value) {
  let hash = 0;
  for (const character of value) hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  return `hsl(${Math.abs(hash * 137.508) % 360} 72% 58%)`;
}

function translatedValue(value, language) {
  if (language !== "en") return value;
  return value.split(" + ").map((part) => englishValues.get(part) ?? part).join(" + ");
}

function associationLabel(value, language) {
  if (language === "es") return value < .1 ? "muy débil" : value < .3 ? "débil" : value < .5 ? "moderada" : "fuerte";
  return value < .1 ? "very weak" : value < .3 ? "weak" : value < .5 ? "moderate" : "strong";
}

function variableLabel(variable, language) {
  return language === "es" ? variable.label : variableLabels[variable.key];
}

function variableFor(key) {
  return surveyVariables.find((variable) => variable.key === key) ?? surveyVariables[0];
}

function heatStyle(value) {
  const alpha = value ? 0.08 + value * 0.72 : 0.02;
  return `background:rgba(199,243,107,${alpha.toFixed(3)});color:${alpha > 0.52 ? "#0f100e" : "#f3f4ee"}`;
}

function renderCorrelation(language) {
  const correlation = document.querySelector("#survey-correlation");
  const firstVariable = variableFor(activeVariables[0]);
  const secondVariable = variableFor(activeVariables[1]);
  const association = categoricalAssociation(records, firstVariable.key, secondVariable.key);
  if (!association.sampleSize || !association.rowLabels.length || !association.columnLabels.length) {
    correlation.innerHTML = `<p class="survey-empty">${language === "es" ? "No hay suficientes respuestas completas para este cruce." : "There are not enough complete responses for this comparison."}</p>`;
    return;
  }
  const rowTotals = association.table.map((row) => row.reduce((sum, count) => sum + count, 0));
  const completeLabel = language === "es" ? "RESPUESTAS COMPLETAS" : "COMPLETE RESPONSES";
  correlation.innerHTML = `<div class="survey-association"><div><span>${language === "es" ? "ASOCIACIÓN EXPLORATORIA" : "EXPLORATORY ASSOCIATION"} · ${association.sampleSize} ${completeLabel}</span><strong>Cramér's V ${association.value.toFixed(2)} · ${associationLabel(association.value, language)}</strong></div><p>${language === "es" ? `Distribución de <strong>${escapeHtml(variableLabel(secondVariable, language))}</strong> dentro de cada respuesta de <strong>${escapeHtml(variableLabel(firstVariable, language))}</strong>.` : `Distribution of <strong>${escapeHtml(variableLabel(secondVariable, language))}</strong> within each <strong>${escapeHtml(variableLabel(firstVariable, language))}</strong> response.`}</p></div><div class="survey-table-scroll"><table class="survey-cross-table"><thead><tr><th scope="col">${escapeHtml(variableLabel(firstVariable, language))} ↓ / ${escapeHtml(variableLabel(secondVariable, language))} →</th>${association.columnLabels.map((label) => `<th scope="col">${escapeHtml(translatedValue(label, language))}</th>`).join("")}</tr></thead><tbody>${association.rowLabels.map((rowLabel, rowIndex) => `<tr><th scope="row">${escapeHtml(translatedValue(rowLabel, language))}<span>n=${rowTotals[rowIndex]}</span></th>${association.columnLabels.map((columnLabel, columnIndex) => {
    const count = association.table[rowIndex][columnIndex];
    const share = rowTotals[rowIndex] ? count / rowTotals[rowIndex] : 0;
    return `<td style="${heatStyle(share)}" title="${escapeHtml(translatedValue(rowLabel, language))} × ${escapeHtml(translatedValue(columnLabel, language))}: ${count} (${percentFormat.format(share)})"><strong>${count}</strong><span>${percentFormat.format(share)}</span></td>`;
  }).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function syncSelectors(firstSelect, secondSelect, changedSelect = null) {
  if (firstSelect.value === secondSelect.value) {
    const replacement = surveyVariables.find((variable) => variable.key !== firstSelect.value)?.key;
    if (changedSelect === firstSelect) secondSelect.value = replacement;
    else firstSelect.value = replacement;
  }
  [...firstSelect.options].forEach((option) => { option.disabled = option.value === secondSelect.value; });
  [...secondSelect.options].forEach((option) => { option.disabled = option.value === firstSelect.value; });
  activeVariables = [firstSelect.value, secondSelect.value];
}

function renderMatrix(language, firstSelect, secondSelect) {
  const matrixTarget = document.querySelector("#survey-matrix");
  const matrix = correlationMatrix(records);
  matrixTarget.innerHTML = `<div class="survey-matrix-head"><div><span>${language === "es" ? "MAPA GENERAL" : "OVERVIEW"}</span><h3>${language === "es" ? "Matriz de correlaciones entre preguntas" : "Correlation matrix across questions"}</h3></div><p>${language === "es" ? "V de Cramér va de 0 a 1 y no implica causalidad." : "Cramér's V ranges from 0 to 1 and does not imply causation."}</p></div><div class="survey-matrix-scroll"><table class="survey-matrix-table"><thead><tr><th scope="col">${language === "es" ? "Pregunta" : "Question"}</th>${surveyVariables.map((variable) => `<th scope="col" title="${escapeHtml(variableLabel(variable, language))}">${escapeHtml(variableLabel(variable, language))}</th>`).join("")}</tr></thead><tbody>${surveyVariables.map((rowVariable, rowIndex) => `<tr><th scope="row">${escapeHtml(variableLabel(rowVariable, language))}</th>${surveyVariables.map((columnVariable, columnIndex) => {
    const cell = matrix[rowIndex][columnIndex];
    if (cell.value === null) return `<td class="survey-matrix-diagonal" aria-label="${escapeHtml(variableLabel(rowVariable, language))}">—</td>`;
    return `<td style="${heatStyle(cell.value)}"><button type="button" data-matrix-row="${rowVariable.key}" data-matrix-column="${columnVariable.key}" title="${escapeHtml(variableLabel(rowVariable, language))} × ${escapeHtml(variableLabel(columnVariable, language))}: V=${cell.value.toFixed(2)}; n=${cell.sampleSize}">${cell.value.toFixed(2)}</button></td>`;
  }).join("")}</tr>`).join("")}</tbody></table></div><p class="survey-matrix-note">${language === "es" ? "Se excluyen respuestas faltantes en cada par. Las selecciones múltiples se comparan como la combinación completa elegida por cada persona." : "Missing responses are excluded pair by pair. Multiple selections are compared as each respondent's complete selected combination."}</p>`;
  matrixTarget.querySelectorAll("[data-matrix-row]").forEach((button) => button.addEventListener("click", () => {
    firstSelect.value = button.dataset.matrixRow;
    secondSelect.value = button.dataset.matrixColumn;
    syncSelectors(firstSelect, secondSelect);
    renderCorrelation(language);
    document.querySelector("#survey-correlation").scrollIntoView({ behavior: "smooth", block: "start" });
  }));
}

function render() {
  if (!records.length) return;
  const language = document.documentElement.lang === "es" ? "es" : "en";
  const ranking = weightedRanking(records);
  const leaderCount = ranking[0]?.[1] || 1;
  const options = surveyVariables.map((variable) => `<option value="${variable.key}">${escapeHtml(variableLabel(variable, language))}</option>`).join("");
  target.innerHTML = `<div class="survey-summary"><div class="survey-total"><strong>${records.length}</strong><span>${language === "es" ? "personas · 1 voto total por persona" : "respondents · 1 total vote per person"}</span></div><div class="survey-ranking">${ranking.map(([driver, count], index) => `<div class="survey-rank-row"><span>${index + 1}</span><strong>${escapeHtml(driver)}</strong><div class="survey-track"><i style="width:${count / leaderCount * 100}%;background:${colorFor(driver)}"></i></div><b>${voteFormat.format(count)}</b><em>${percentFormat.format(count / records.length)}</em></div>`).join("")}</div></div><div class="survey-control"><div class="survey-control-copy"><strong>${language === "es" ? "Comparar dos preguntas" : "Compare two questions"}</strong><span>${language === "es" ? "Elegí dos variables distintas para explorar su asociación." : "Choose two different variables to explore their association."}</span></div><div class="survey-selectors"><label for="survey-variable-a"><span>${language === "es" ? "Variable A" : "Variable A"}</span><select id="survey-variable-a">${options}</select></label><b aria-hidden="true">×</b><label for="survey-variable-b"><span>${language === "es" ? "Variable B" : "Variable B"}</span><select id="survey-variable-b">${options}</select></label></div></div><div id="survey-correlation"></div><div id="survey-matrix"></div>`;
  const firstSelect = document.querySelector("#survey-variable-a");
  const secondSelect = document.querySelector("#survey-variable-b");
  firstSelect.value = activeVariables[0];
  secondSelect.value = activeVariables[1];
  syncSelectors(firstSelect, secondSelect);
  const update = (changedSelect) => {
    syncSelectors(firstSelect, secondSelect, changedSelect);
    renderCorrelation(language);
  };
  firstSelect.addEventListener("change", () => update(firstSelect));
  secondSelect.addEventListener("change", () => update(secondSelect));
  renderCorrelation(language);
  renderMatrix(language, firstSelect, secondSelect);
}

async function loadSurvey() {
  try {
    const [surveyResponse, opinionResponse] = await Promise.all([
      fetch(`${SURVEY_URL}&_=${Date.now()}`, { cache: "no-store" }),
      fetch("../data/opinion-ranking.json")
    ]);
    if (!surveyResponse.ok || !opinionResponse.ok) throw new Error("HTTP error");
    const opinion = await opinionResponse.json();
    const driverNames = [...new Set([...opinion.ranking.map((driver) => driver.name), ...currentDriverNames])];
    records = surveyRecords(parseCsv(await surveyResponse.text()), driverNames);
    render();
  } catch {
    target.innerHTML = `<div class="status error">${document.documentElement.lang === "es" ? "No se pudieron cargar las respuestas en vivo." : "The live survey responses could not be loaded."}</div>`;
  }
}

document.querySelectorAll("[data-lang]").forEach((button) => button.addEventListener("click", () => queueMicrotask(render)));
loadSurvey();
window.setInterval(loadSurvey, 60000);
